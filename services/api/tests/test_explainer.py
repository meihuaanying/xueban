"""Explainer 交互讲解测试（P1 / §5）。

三层：
1. 消毒器（``explainer_sanitize``）——纯函数，重点验证「联网/注入一律拦死」；
2. 服务（``explainer_service``）——生成、降级、缓存键、每日限额、反馈；
3. 路由（``routes/explainer.py``）——§5.5 四个端点的状态码契约。
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, settings
from app.data.curriculum import find_point
from app.errors import LlmError, NotFoundError, RateLimitedError
from app.models import (
    ExplainerContent,
    ExplainerJob,
    ExplainerMode,
    ExplainerStatus,
    User,
    UserRole,
)
from app.services import explainer_service
from app.services.auth_service import issue_token_pair
from app.services.explainer_sanitize import (
    ALLOWED_TAGS,
    find_network_violation,
    sanitize_explainer_html,
)
from app.services.security import hash_password
from tests.conftest import auth_headers, next_phone
from tests.helpers import register_user

MAX_BYTES = 500 * 1024
POINT_CODE = "g1m-add-within-10"
OTHER_POINT_CODE = "g1m-add-within-20-carry"


# --------------------------------------------------------------- 消毒器


def _page(body: str, *, head: str = "<style>b{color:red}</style>") -> str:
    return f'<!DOCTYPE html><html lang="zh-CN"><head>{head}</head><body>{body}</body></html>'


def _good_page() -> str:
    return _page("<h1>凑十法</h1><script>var n = 1 + 1;</script>")


def _settings() -> Settings:
    return Settings(
        content_generation_model="stub",
        explainer_style_version="v-test",
        explainer_daily_quota=2,
    )


def test_good_page_passes_and_gets_csp() -> None:
    result = sanitize_explainer_html(_good_page(), max_bytes=MAX_BYTES)
    assert result.ok is True
    assert "default-src 'none'" in result.html
    assert "script-src 'unsafe-inline'" in result.html
    assert "connect-src 'none'" in result.html
    assert result.byte_size == len(result.html.encode("utf-8"))


def test_csp_is_injected_before_any_content() -> None:
    """CSP meta 必须早于所有内容，否则约束不到后面的资源。"""
    result = sanitize_explainer_html(_good_page(), max_bytes=MAX_BYTES)
    assert result.html.index("Content-Security-Policy") < result.html.index("<h1")


@pytest.mark.parametrize(
    "body",
    [
        '<script>fetch("https://evil.test/x")</script>',
        '<script>var w = new WebSocket("wss://a.test")</script>',
        '<script>navigator.sendBeacon("/collect")</script>',
        '<img src="https://cdn.test/a.png">',
        '<link rel="stylesheet" href="https://cdn.test/a.css">',
        '<script src="https://cdn.test/a.js"></script>',
        '<div style="background:url(https://cdn.test/a.png)">x</div>',
        "<a href='//evil.test'>点我</a>",
    ],
)
def test_network_egress_is_rejected(body: str) -> None:
    """§5.4：禁止任何网络出站。整篇判不合格，而不是清洗后放行。"""
    result = sanitize_explainer_html(_page(body), max_bytes=MAX_BYTES)
    assert result.ok is False
    assert result.html == ""
    assert result.reason is not None


@pytest.mark.parametrize(
    "body",
    [
        '<script>eval("1+1")</script>',
        '<script>document.write("hi")</script>',
        '<script>setTimeout("alert(1)", 100)</script>',
    ],
)
def test_dynamic_code_is_rejected(body: str) -> None:
    result = sanitize_explainer_html(_page(body), max_bytes=MAX_BYTES)
    assert result.ok is False
    assert "动态代码" in (result.reason or "")


def test_event_handlers_are_stripped_even_though_csp_allows_inline_script() -> None:
    """CSP 的 'unsafe-inline' 会放行 on*=，所以只能靠白名单剔除。"""
    result = sanitize_explainer_html(
        _page('<button onclick="steal()">点</button><script>var n=1;</script>'),
        max_bytes=MAX_BYTES,
    )
    assert result.ok is True
    assert "onclick" not in result.html.lower()
    assert "steal()" not in result.html


def test_dangerous_tags_are_stripped() -> None:
    """不带外链的恶意标签只是被剥掉（内容继续可用），带外链的整篇判不合格。"""
    result = sanitize_explainer_html(
        _page(
            '<object data="x"></object><embed src="local.swf">'
            '<form action="/x"><input name="a"></form><script>var n=1;</script>'
        ),
        max_bytes=MAX_BYTES,
    )
    assert result.ok is True
    lowered = result.html.lower()
    for tag in ("<object", "<embed", "<form", "<input"):
        assert tag not in lowered


def test_data_uri_css_is_allowed() -> None:
    """data: 不是网络出站，内联 SVG 当背景图是允许的。"""
    result = sanitize_explainer_html(
        _page(
            '<div style="background:url(data:image/svg+xml;base64,PHN2Zz48L3N2Zz4-)">x</div>'
            "<script>var n=1;</script>"
        ),
        max_bytes=MAX_BYTES,
    )
    assert result.ok is True
    assert "data:image/svg+xml" in result.html


def test_inline_svg_namespace_is_not_treated_as_external_url() -> None:
    """xmlns 是命名空间标识，浏览器从不去取，不能当外链拦掉。"""
    result = sanitize_explainer_html(
        _page(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            '<circle cx="5" cy="5" r="4" fill="red"></circle></svg>'
            "<script>var n=1;</script>"
        ),
        max_bytes=MAX_BYTES,
    )
    assert result.ok is True
    assert "<circle" in result.html


def test_oversize_is_rejected() -> None:
    """§5.4：体积上限 500KB。padding 用可见文本，HTML 注释会被剥掉不算数。"""
    result = sanitize_explainer_html(
        _page("<p>" + "字" * 5000 + "</p><script>var n=1;</script>"), max_bytes=1000
    )
    assert result.ok is False
    assert "超过" in (result.reason or "")


def test_static_page_without_script_is_rejected() -> None:
    """§5.2 交付的是交互页；纯静态文本说明这次生成失败了。"""
    result = sanitize_explainer_html(_page("<h1>只有文字</h1>", head=""), max_bytes=MAX_BYTES)
    assert result.ok is False
    assert "不是交互讲解页" in (result.reason or "")


def test_empty_input_is_rejected() -> None:
    assert sanitize_explainer_html("   ", max_bytes=MAX_BYTES).ok is False


def test_find_network_violation_reports_label() -> None:
    assert find_network_violation("<p>ok</p>") is None
    violation = find_network_violation('<script>fetch("/x")</script>')
    assert violation is not None
    assert "网络 API" in violation


def test_allowed_tags_exclude_network_bearing_elements() -> None:
    for tag in ("iframe", "img", "link", "object", "embed", "form", "input", "meta", "base"):
        assert tag not in ALLOWED_TAGS


# --------------------------------------------------------------- 服务：纯函数


def test_cache_key_is_stable_and_sensitive_to_style_version() -> None:
    a = explainer_service.cache_key("math.add", "grade1_2", "v1")
    assert a == explainer_service.cache_key("math.add", "grade1_2", "v1")
    assert a != explainer_service.cache_key("math.add", "grade1_2", "v2"), "换风格必须换键"
    assert a != explainer_service.cache_key("math.add", "junior", "v1"), "换学段必须换键"
    assert len(a) == 64


def test_extract_html_document_strips_fence_and_preamble() -> None:
    raw = "好的，这是页面：\n```html\n<!DOCTYPE html><html><body>hi</body></html>\n```"
    assert explainer_service.extract_html_document(raw).startswith("<!DOCTYPE html>")


def test_extract_html_document_rejects_non_html() -> None:
    with pytest.raises(explainer_service.ExplainerError):
        explainer_service.extract_html_document("我做不到")


def test_strip_html_text_removes_script_and_style() -> None:
    text = explainer_service.strip_html_text(
        "<style>b{}</style><script>var secret=1</script><p>你好</p>"
    )
    assert "secret" not in text
    assert "你好" in text


def test_degraded_html_is_itself_sanitizable() -> None:
    """降级产物也要过同一道闸：降级路径必须比交互页更可靠。"""
    html = explainer_service.render_degraded_html(
        title="凑十法",
        script={
            "hook": "看小猴子分桃",
            "acts": [
                {"name": "拆解", "narration": "9 凑成 10", "interaction": {"prompt": "点一点"}}
            ],
            "checkpoint": "9 加几得 10？",
        },
    )
    result = sanitize_explainer_html(html, max_bytes=MAX_BYTES)
    assert result.ok is True
    assert "凑十法" in result.html
    assert "default-src 'none'" in result.html


def test_degraded_html_escapes_script_like_text() -> None:
    html = explainer_service.render_degraded_html(
        title="t", script={"acts": [{"narration": "<script>alert(1)</script>"}]}
    )
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html


async def test_design_script_caps_act_count() -> None:
    """§5.2 ①：教学脚本 ≤4 幕，超出的部分必须裁掉。"""
    point = find_point(POINT_CODE)
    assert point is not None
    llm = _StubLlm(['{"title":"t","acts":[' + ",".join(['{"name":"n"}'] * 9) + "]}"])
    script = await explainer_service.design_script(
        llm=llm,  # type: ignore[arg-type]
        point=point,
        profile="- 当前掌握度：30%\n- 近期错误：暂无记录",
        settings=_settings(),
    )
    assert len(script["acts"]) == _settings().explainer_max_acts


async def test_design_script_rejects_script_without_acts() -> None:
    point = find_point(POINT_CODE)
    assert point is not None
    with pytest.raises(explainer_service.ExplainerError):
        await explainer_service.design_script(
            llm=_StubLlm(['{"title":"t"}']),  # type: ignore[arg-type]
            point=point,
            profile="- 当前掌握度：30%\n- 近期错误：暂无记录",
            settings=_settings(),
        )


# --------------------------------------------------------------- 服务：LLM 替身


class _StubLlm:
    """按调用顺序回放预设回复的 LlmClient 替身。"""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    async def complete(self, messages: list[dict[str, str]], **_: Any) -> SimpleNamespace:
        self.calls.append(messages)
        if not self._replies:
            raise AssertionError("预设回复已用尽")
        return SimpleNamespace(content=self._replies.pop(0))

    async def aclose(self) -> None:
        return None


_SCRIPT_JSON = (
    '{"title":"凑十法","hook":"9 变 10 更快",'
    '"acts":[{"name":"拆解","goal":"看懂","narration":"9 加 1 得 10",'
    '"interaction":{"kind":"tap","prompt":"点一点","options":["10","11"],"answer":"10"}}]}'
)


@pytest_asyncio.fixture()
async def student(sessionmaker: async_sessionmaker[AsyncSession]) -> tuple[uuid.UUID, str]:
    """建一个学生并签发访问令牌。"""
    async with sessionmaker() as session:
        user = User(
            phone=next_phone(),
            role=UserRole.STUDENT,
            password_hash=hash_password("pw-123456"),
            nickname="讲解测试",
        )
        session.add(user)
        await session.flush()
        pair = await issue_token_pair(session, user)
        await session.commit()
        return user.id, pair.access_token


@pytest_asyncio.fixture()
async def student_token(sessionmaker: async_sessionmaker[AsyncSession]) -> str:
    """只要访问令牌（路由用例用，不关心 user_id）。"""
    async with sessionmaker() as session:
        user = User(
            phone=next_phone(),
            role=UserRole.STUDENT,
            password_hash=hash_password("pw-123456"),
            nickname="讲解路由测试",
        )
        session.add(user)
        await session.flush()
        pair = await issue_token_pair(session, user)
        await session.commit()
        return pair.access_token


@pytest_asyncio.fixture()
async def pending_content(
    sessionmaker: async_sessionmaker[AsyncSession], student: tuple[uuid.UUID, str]
) -> ExplainerContent:
    """一个「待生成」的讲解内容行。

    缓存键用**全局** settings 的风格版本：路由用例走的就是全局配置，写死
    "v-test" 会让缓存查询永远对不上（这正是风格版本进键的意义）。
    """
    point = find_point(POINT_CODE)
    assert point is not None
    async with sessionmaker() as session:
        kp_id = await explainer_service.ensure_knowledge_point(
            session, point, stage=explainer_service.ELEMENTARY_STAGE, sort_order=1
        )
        content = ExplainerContent(
            knowledge_point_id=kp_id,
            stage=explainer_service.ELEMENTARY_STAGE,
            mode=ExplainerMode.INTERACTIVE,
            style_version=settings.explainer_style_version,
            cache_key=explainer_service.cache_key(
                point.id, explainer_service.ELEMENTARY_STAGE, settings.explainer_style_version
            ),
            title=point.name,
        )
        session.add(content)
        await session.commit()
        return content


async def test_generate_content_happy_path(
    sessionmaker: async_sessionmaker[AsyncSession],
    student: tuple[uuid.UUID, str],
    pending_content: ExplainerContent,
) -> None:
    user_id, _ = student
    llm = _StubLlm([_SCRIPT_JSON, _good_page()])
    async with sessionmaker() as session:
        result = await explainer_service.generate_content(
            session,
            content_id=pending_content.id,
            llm=llm,  # type: ignore[arg-type]
            settings=_settings(),
            user_id=user_id,
        )
        assert result.status is ExplainerStatus.READY
        assert result.degraded is False
        assert "default-src 'none'" in (result.html or "")
        assert result.script["title"] == "凑十法"
        assert result.byte_size > 0
    assert len(llm.calls) == 2, "教学设计与网页生成是两次独立调用"


async def test_generate_content_degrades_when_sanitize_fails(
    sessionmaker: async_sessionmaker[AsyncSession],
    student: tuple[uuid.UUID, str],
    pending_content: ExplainerContent,
) -> None:
    """§5.4：交互页不合格必须降级成图文分步讲解，且状态仍是 ready（前端永不白屏）。"""
    user_id, _ = student
    llm = _StubLlm([_SCRIPT_JSON, '<script>fetch("https://evil.test")</script>'])
    async with sessionmaker() as session:
        result = await explainer_service.generate_content(
            session,
            content_id=pending_content.id,
            llm=llm,  # type: ignore[arg-type]
            settings=_settings(),
            user_id=user_id,
        )
        assert result.status is ExplainerStatus.READY
        assert result.degraded is True
        assert "fetch" not in (result.html or "")
        assert "第1步" in (result.html or ""), "降级页要有一幕一幕的图文步骤"
        assert result.error is not None and "网络" in result.error


async def test_generate_content_degrades_on_llm_failure(
    sessionmaker: async_sessionmaker[AsyncSession],
    student: tuple[uuid.UUID, str],
    pending_content: ExplainerContent,
) -> None:
    user_id, _ = student

    class _Boom(_StubLlm):
        async def complete(self, messages: list[dict[str, str]], **kw: Any) -> SimpleNamespace:
            raise LlmError("上游挂了", code="LLM_ERROR", status_code=502)

    async with sessionmaker() as session:
        result = await explainer_service.generate_content(
            session,
            content_id=pending_content.id,
            llm=_Boom([]),  # type: ignore[arg-type]
            settings=_settings(),
            user_id=user_id,
        )
        assert result.status is ExplainerStatus.READY
        assert result.degraded is True
        assert "上游挂了" in (result.error or "")


async def test_generate_content_is_idempotent(
    sessionmaker: async_sessionmaker[AsyncSession],
    student: tuple[uuid.UUID, str],
    pending_content: ExplainerContent,
) -> None:
    user_id, _ = student
    async with sessionmaker() as session:
        await explainer_service.generate_content(
            session,
            content_id=pending_content.id,
            llm=_StubLlm([_SCRIPT_JSON, _good_page()]),  # type: ignore[arg-type]
            settings=_settings(),
            user_id=user_id,
        )
        await session.commit()
    async with sessionmaker() as session:
        again = await explainer_service.generate_content(
            session,
            content_id=pending_content.id,
            llm=_StubLlm([]),  # type: ignore[arg-type]
            settings=_settings(),
            user_id=user_id,
        )
        assert again.degraded is False
        assert again.html is not None


async def test_resolve_point_rejects_unknown_code(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with sessionmaker() as session:
        with pytest.raises(NotFoundError) as excinfo:
            await explainer_service.resolve_point(session, "g1m.不存在", settings=_settings())
        assert excinfo.value.code == "CURRICULUM_POINT_NOT_FOUND"


async def test_resolve_point_rejects_unknown_uuid(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with sessionmaker() as session:
        with pytest.raises(NotFoundError) as excinfo:
            await explainer_service.resolve_point(session, str(uuid.uuid4()), settings=_settings())
        assert excinfo.value.code == "KNOWLEDGE_POINT_NOT_FOUND"


async def test_resolve_point_accepts_uuid(
    sessionmaker: async_sessionmaker[AsyncSession], pending_content: ExplainerContent
) -> None:
    async with sessionmaker() as session:
        record, point = await explainer_service.resolve_point(
            session, pending_content.knowledge_point_id.hex, settings=_settings()
        )
        assert record.code == point.id
        assert point.subject == "math"


async def test_daily_usage_counts_recent_jobs(
    sessionmaker: async_sessionmaker[AsyncSession], student: tuple[uuid.UUID, str]
) -> None:
    user_id, _ = student
    async with sessionmaker() as session:
        assert await explainer_service.daily_usage(session, user_id) == 0
        for _ in range(2):
            session.add(
                ExplainerJob(
                    user_id=user_id,
                    mode=ExplainerMode.INTERACTIVE,
                    status=ExplainerStatus.GENERATING,
                    cache_hit=False,
                )
            )
        await session.commit()
        assert await explainer_service.daily_usage(session, user_id) == 2


async def test_record_feedback_rejects_missing_content(
    sessionmaker: async_sessionmaker[AsyncSession], student: tuple[uuid.UUID, str]
) -> None:
    user_id, _ = student
    async with sessionmaker() as session:
        with pytest.raises(NotFoundError):
            await explainer_service.record_feedback(
                session, user_id=user_id, content_id=uuid.uuid4(), understood=True, note=None
            )


async def test_request_explainer_enforces_daily_quota(
    sessionmaker: async_sessionmaker[AsyncSession], student: tuple[uuid.UUID, str]
) -> None:
    """§5.4：每用户每日 20 次（测试里设为 2），超限报 429。"""
    user_id, _ = student
    async with sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        for _ in range(2):
            session.add(
                ExplainerJob(
                    user_id=user.id,
                    mode=ExplainerMode.INTERACTIVE,
                    status=ExplainerStatus.GENERATING,
                    cache_hit=False,
                )
            )
        await session.commit()
        with pytest.raises(RateLimitedError) as excinfo:
            await explainer_service.request_explainer(
                session,
                user=user,
                knowledge_id=OTHER_POINT_CODE,
                mode=ExplainerMode.INTERACTIVE,
                settings=_settings(),
                enqueue=False,
            )
        assert excinfo.value.code == "EXPLAINER_QUOTA_EXCEEDED"


# --------------------------------------------------------------- 路由


async def test_generate_returns_202_then_poll_and_content(
    client: AsyncClient, student_token: str, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """§5.5：未命中缓存 → 202 + job_id，轮询与内容端点都能取到。"""
    headers = auth_headers(student_token)
    response = await client.post(
        "/v1/explainer/generate",
        json={"knowledge_id": POINT_CODE, "mode": "interactive"},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["cache_hit"] is False
    assert body["content"] is None

    poll = await client.get(f"/v1/explainer/{body['job_id']}", headers=headers)
    assert poll.status_code == 200
    assert poll.json()["job_id"] == body["job_id"]

    async with sessionmaker() as session:
        job = (
            await session.execute(
                select(ExplainerJob).where(ExplainerJob.id == uuid.UUID(body["job_id"]))
            )
        ).scalar_one()
        content_id = job.content_id
    assert content_id is not None

    async with sessionmaker() as session:
        content = (
            await session.execute(select(ExplainerContent).where(ExplainerContent.id == content_id))
        ).scalar_one()
        # 走真实消毒路径，不往库里塞没消毒过的 HTML
        clean = sanitize_explainer_html(_good_page(), max_bytes=MAX_BYTES)
        assert clean.ok is True
        content.status = ExplainerStatus.READY
        content.html = clean.html
        content.byte_size = clean.byte_size
        await session.commit()

    detail = await client.get(f"/v1/explainer/content/{content_id}", headers=headers)
    assert detail.status_code == 200
    assert "default-src 'none'" in detail.json()["content"]["html"]

    poll2 = await client.get(f"/v1/explainer/{body['job_id']}", headers=headers)
    assert poll2.json()["content"]["html"]


async def test_generate_hits_cache_with_200(
    client: AsyncClient,
    student_token: str,
    sessionmaker: async_sessionmaker[AsyncSession],
    pending_content: ExplainerContent,
) -> None:
    """§5.5：缓存命中直接 200 返回内容，不进轮询。"""
    async with sessionmaker() as session:
        row = (
            await session.execute(
                select(ExplainerContent).where(ExplainerContent.id == pending_content.id)
            )
        ).scalar_one()
        clean = sanitize_explainer_html(_good_page(), max_bytes=MAX_BYTES)
        assert clean.ok is True
        row.status = ExplainerStatus.READY
        row.html = clean.html
        row.byte_size = clean.byte_size
        await session.commit()

    response = await client.post(
        "/v1/explainer/generate",
        json={"knowledge_id": POINT_CODE, "mode": "interactive"},
        headers=auth_headers(student_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cache_hit"] is True
    assert "<h1>" in body["content"]["html"]


async def test_generate_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/v1/explainer/generate", json={"knowledge_id": POINT_CODE})
    assert response.status_code == 401


async def test_unknown_knowledge_point_returns_404(client: AsyncClient, student_token: str) -> None:
    response = await client.post(
        "/v1/explainer/generate",
        json={"knowledge_id": "g1m.并不存在"},
        headers=auth_headers(student_token),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "CURRICULUM_POINT_NOT_FOUND"


async def test_job_of_other_user_is_404(client: AsyncClient, student_token: str) -> None:
    """不区分「不存在」与「不是你的」，避免用 job_id 探测他人数据。"""
    response = await client.post(
        "/v1/explainer/generate",
        json={"knowledge_id": POINT_CODE},
        headers=auth_headers(student_token),
    )
    job_id = response.json()["job_id"]
    other = await register_user(client, nickname="另一个人")
    poll = await client.get(f"/v1/explainer/{job_id}", headers=auth_headers(other["access_token"]))
    assert poll.status_code == 404
    assert poll.json()["code"] == "EXPLAINER_JOB_NOT_FOUND"


async def test_quota_returns_429(
    client: AsyncClient,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """§5.4：每用户每日上限用全局 settings（20 次），超限报 429。"""
    tokens = await register_user(client, nickname="限额测试")
    user_id = uuid.UUID(tokens["id"])
    limit = settings.explainer_daily_quota
    async with sessionmaker() as session:
        for _ in range(limit):
            session.add(
                ExplainerJob(
                    user_id=user_id,
                    mode=ExplainerMode.INTERACTIVE,
                    status=ExplainerStatus.GENERATING,
                    cache_hit=False,
                )
            )
        await session.commit()

    response = await client.post(
        "/v1/explainer/generate",
        json={"knowledge_id": OTHER_POINT_CODE},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 429
    assert response.json()["code"] == "EXPLAINER_QUOTA_EXCEEDED"


async def test_feedback_endpoint_aggregates(
    client: AsyncClient, student_token: str, pending_content: ExplainerContent
) -> None:
    headers = auth_headers(student_token)
    first = await client.post(
        "/v1/explainer/feedback",
        json={"content_id": str(pending_content.id), "understood": True},
        headers=headers,
    )
    assert first.status_code == 201
    assert first.json()["understood_count"] == 1
    assert first.json()["confused_count"] == 0

    second = await client.post(
        "/v1/explainer/feedback",
        json={"content_id": str(pending_content.id), "understood": False, "note": "还是不会"},
        headers=headers,
    )
    assert second.status_code == 201
    payload = second.json()
    assert payload["understood"] is False
    assert payload["understood_count"] == 1
    assert payload["confused_count"] == 1


async def test_feedback_rejects_unknown_content(client: AsyncClient, student_token: str) -> None:
    response = await client.post(
        "/v1/explainer/feedback",
        json={"content_id": str(uuid.uuid4()), "understood": True},
        headers=auth_headers(student_token),
    )
    assert response.status_code == 404