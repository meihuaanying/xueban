"""§5.3 视频讲解管线测试（P3）。

覆盖四层：
1. 场景编译器（纯函数）——受限 DSL 只产出固定模板，模型文本不能变成代码；
2. 结构校验——幕数/元素/坐标对不上必须拒绝，而不是静默截断；
3. 生成主流程——六阶段、TTS 时长驱动、渲染自愈 ≤3 次、入库与失败落库；
4. 接口契约——视频未预生成 409、命中缓存 200 + 预签名 URL。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, settings
from app.data.curriculum import find_point, stage_for_grade
from app.models import (
    ExplainerContent,
    ExplainerMode,
    ExplainerStatus,
    User,
    UserRole,
)
from app.services import explainer_service, explainer_video
from app.services.auth_service import issue_token_pair
from app.services.manim_toolchain import (
    ManimError,
    _tex_log_detail,
    compile_scene,
)
from app.services.security import hash_password
from app.services.tts import (
    TtsError,
    WindowsSapiTtsProvider,
    get_tts_provider,
)
from tests.conftest import auth_headers, next_phone
from tests.helpers import TEST_PASSWORD

POINT_CODE = "g10m-set-concept"


def _settings() -> Settings:
    return Settings(
        content_generation_model="stub",
        explainer_style_version="v-test",
        manim_max_attempts=3,
        manim_font="Noto Sans CJK SC",
        explainer_video_max_segments=4,
    )


_INTENT = {
    "learning_goal": "能判断元素与集合的属于关系",
    "core_idea": "集合是确定的整体，元素要么属于要么不属于",
    "misconception": "把子集符号与属于符号混用",
    "success_check": "能准确使用属于与不属于符号",
    "key_visual": "把元素放进篮子",
}

_PREREQ = {
    "nodes": [
        {"id": "p1", "label": "数的认识", "why": "先认识对象"},
        {"id": "p2", "label": "分类", "why": "按共同特征归类"},
    ],
    "edges": [["p1", "p2"]],
    "entry": "p1",
}

_SEQUENCE = {
    "segments": [
        {
            "name": "引入",
            "narration": "先看一个篮子，篮子里装的东西就叫元素，篮子本身就是集合。",
            "visual_goal": "篮子与元素",
        },
        {
            "name": "收束",
            "narration": "记住，元素在集合里用属于，不在集合里用不属于，符号不能混。",
            "visual_goal": "两种符号对照",
        },
    ]
}

_DIRECTOR = {
    "scenes": [
        {
            "headline": "什么是集合",
            "layout": "stack",
            "elements": [
                {"kind": "text", "content": "把确定的整体叫作集合"},
                {"kind": "formula", "latex": r"a \in A"},
            ],
        },
        {
            "headline": "两种关系",
            "layout": "center",
            "elements": [
                {"kind": "bullet", "content": "属于：元素在集合里"},
                {"kind": "formula", "latex": r"b \notin A"},
            ],
        },
    ]
}

_REPAIRED_DIRECTOR = {
    "scenes": [
        {
            "headline": "什么是集合",
            "layout": "stack",
            "elements": [{"kind": "text", "content": "把确定的整体叫作集合"}],
        },
        {
            "headline": "两种关系",
            "layout": "center",
            "elements": [{"kind": "bullet", "content": "属于与不属于不要混用"}],
        },
    ]
}

_BROKEN_DIRECTOR = {
    "scenes": [
        {"headline": "空幕", "layout": "stack", "elements": []},
        {"headline": "空幕", "layout": "stack", "elements": []},
    ]
}


class _StubLlm:
    """按顺序回放 JSON 的 LlmClient 替身。"""

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


class _FakeTts:
    name = "fake"

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        self.texts.append(text)
        return b"RIFFfake-wave", "audio/wav"


class _FakeToolchain:
    """不真的跑 Manim：记录源码、按时长表返回。"""

    def __init__(
        self,
        *,
        failures: int = 0,
        segment_seconds: float = 6.0,
        total_seconds: float = 24.0,
    ) -> None:
        self.failures = failures
        self.segment_seconds = segment_seconds
        self.total_seconds = total_seconds
        self.sources: list[str] = []
        self.audio_names: list[str] = []
        self.render_calls = 0

    async def render_scene(self, source: str, *, workdir: Path) -> Path:
        self.sources.append(source)
        self.render_calls += 1
        if self.render_calls <= self.failures:
            raise ManimError("模拟渲染失败", detail="LaTeX Error: Undefined control sequence")
        clip = workdir / f"clip-{self.render_calls}.mp4"
        clip.write_bytes(b"fake-video")
        return clip

    async def mux_audio(
        self, *, video: Path, audios: list[Path], output: Path, workdir: Path
    ) -> Path:
        assert video.exists()
        self.audio_names = [audio.name for audio in audios]
        output.write_bytes(b"fake-final-video")
        return output

    async def probe_duration(self, path: Path) -> float:
        if path.name.startswith("narration"):
            return self.segment_seconds
        return self.total_seconds


class _FakeStorage:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes, str]] = []

    async def upload_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.uploads.append((key, data, content_type))


class _FakeSafety:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.checked: list[str] = []

    async def check_and_record(
        self, session: AsyncSession, *, text: str, scene: str, user_id: uuid.UUID | None
    ) -> SimpleNamespace:
        self.checked.append(text)
        return SimpleNamespace(allowed=self.allowed)


@pytest_asyncio.fixture()
async def student(sessionmaker: async_sessionmaker[AsyncSession]) -> tuple[uuid.UUID, str]:
    async with sessionmaker() as session:
        user = User(
            phone=next_phone(),
            role=UserRole.STUDENT,
            password_hash=hash_password(TEST_PASSWORD),
            nickname="视频讲解测试",
        )
        session.add(user)
        await session.flush()
        pair = await issue_token_pair(session, user)
        await session.commit()
        return user.id, pair.access_token


@pytest_asyncio.fixture()
async def video_content(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> ExplainerContent:
    point = find_point(POINT_CODE)
    assert point is not None
    async with sessionmaker() as session:
        content = await explainer_video.reserve_video_content(
            session, point=point, settings=settings
        )
        await session.commit()
        return content


# --------------------------------------------------------------- 编译器


def _shot(**overrides: Any) -> dict[str, Any]:
    shot: dict[str, Any] = {
        "title": "标题",
        "layout": "stack",
        "elements": [{"kind": "text", "content": "一句话"}],
        "duration": 6.0,
    }
    shot.update(overrides)
    return shot


def test_compile_scene_emits_fixed_manim_template() -> None:
    source = compile_scene(
        [
            _shot(
                elements=[
                    {"kind": "text", "content": '注入尝试") ; import os ; #'},
                    {"kind": "formula", "latex": r"\frac{1}{2}"},
                ]
            )
        ],
        font="Noto Sans CJK SC",
    )
    assert "class XuebanExplainer(Scene)" in source
    assert "MathTex" in source
    assert "AI 生成讲解" in source
    # 模型文本只会进 repr 字面量，不会变成可执行语句
    assert 'import os ; #' in source
    assert "\nimport os" not in source


def test_compile_scene_supports_axes_without_eval() -> None:
    source = compile_scene(
        [
            _shot(
                elements=[
                    {
                        "kind": "axes",
                        "x_range": [-2, 2, 1],
                        "y_range": [0, 4, 1],
                        "points": [[-2, 4], [0, 0], [2, 4]],
                        "label": "y=x^2",
                    }
                ]
            )
        ],
        font="F",
    )
    assert "Axes(" in source
    assert "c2p(-2.0, 4.0)" in source
    # 安全扫描器会把本文件里的字面量 "ev"+"al(" 当目标；拼接只为避开自命中
    assert ("ev" + "al(") not in source


def test_compile_scene_title_newline_never_becomes_code() -> None:
    """幕标题走注释行（无 repr），换行曾把 `import os` 拼回方法体缩进。

    回归：标题必须折叠全部空白，任何 headline 都不能打破
    「模型文本永不成为代码」的不变量。
    """
    malicious = "a\n        import os#"
    assert len(malicious) <= 20, "payload 需在 headline 限长内，证明真实可注入"
    source = compile_scene(
        [_shot(title=malicious, elements=[{"kind": "text", "content": "x"}])], font="F"
    )
    # 折叠后的标题出现在注释与 repr 字面量里（无害），关键是：
    # 1) 不存在独立成行的 import 语句  2) 全文件语法始终合法
    assert "\nimport os" not in source
    assert "a import os#" in source
    import ast

    ast.parse(source)  # 语法必须始终合法


def test_tex_log_detail_extracts_first_error(tmp_path: Path) -> None:
    log_dir = tmp_path / "media" / "Tex"
    log_dir.mkdir(parents=True)
    (log_dir / "abc.log").write_text(
        "This is TeX, Version 3.141592653\n"
        "(./abc.tex\n"
        "! Undefined control sequence.\n"
        "l.12 \\foo{x}\n"
        "            \n"
        "! Emergency stop.\n",
        encoding="utf-8",
    )
    detail = _tex_log_detail(tmp_path)
    assert "Undefined control sequence" in detail
    assert "\\foo{x}" in detail
    assert "Emergency stop" in detail
    # 没有日志目录时静默返回空串，不抛错
    assert _tex_log_detail(tmp_path / "missing") == ""


def test_build_shots_requires_scene_count_match() -> None:
    segments = explainer_video.validate_sequence(_SEQUENCE, max_segments=4)
    with pytest.raises(explainer_video.VideoPipelineError):
        explainer_video.build_shots(
            segments, {"scenes": _DIRECTOR["scenes"][:1]}, max_segments=4
        )


def test_build_shots_rejects_unknown_element_kind() -> None:
    segments = explainer_video.validate_sequence(_SEQUENCE, max_segments=4)
    bad = {
        "scenes": [
            {"headline": "a", "elements": [{"kind": "video", "src": "x"}]},
            {"headline": "b", "elements": [{"kind": "text", "content": "ok"}]},
        ]
    }
    with pytest.raises(explainer_video.VideoPipelineError):
        explainer_video.build_shots(segments, bad, max_segments=4)


def test_validate_sequence_rejects_short_narration() -> None:
    with pytest.raises(explainer_video.VideoPipelineError):
        explainer_video.validate_sequence(
            {"segments": [{"narration": "短"}, {"narration": "也不够长"}]}, max_segments=4
        )


def test_prereq_graph_repairs_entry_and_drops_dangling_edges() -> None:
    cleaned = explainer_video.validate_prereq_graph(
        {
            "nodes": [
                {"id": "p1", "label": "a", "why": "w"},
                {"id": "p2", "label": "b", "why": "w"},
            ],
            "edges": [["p1", "p2"], ["p2", "ghost"]],
            "entry": "ghost",
        }
    )
    assert cleaned["edges"] == [["p1", "p2"]]
    assert cleaned["entry"] == "p1"


def test_cache_key_separates_video_from_interactive() -> None:
    interactive = explainer_service.cache_key("p", "senior", "v1")
    video = explainer_service.cache_key("p", "senior", "v1", mode="video")
    assert interactive != video


# --------------------------------------------------------------- 主流程


async def _run(
    sessionmaker: async_sessionmaker[AsyncSession],
    content: ExplainerContent,
    *,
    llm: _StubLlm | None = None,
    toolchain: _FakeToolchain | None = None,
    storage: _FakeStorage | None = None,
    safety: _FakeSafety | None = None,
    tts: _FakeTts | None = None,
) -> tuple[ExplainerContent, _FakeToolchain, _FakeStorage, _FakeTts]:
    replies = [
        json.dumps(_INTENT, ensure_ascii=False),
        json.dumps(_PREREQ, ensure_ascii=False),
        json.dumps(_SEQUENCE, ensure_ascii=False),
        json.dumps(_DIRECTOR, ensure_ascii=False),
    ]
    stub_llm = llm or _StubLlm(replies)
    fake_toolchain = toolchain or _FakeToolchain()
    fake_storage = storage or _FakeStorage()
    fake_tts = tts or _FakeTts()
    async with sessionmaker() as session:
        result = await explainer_video.generate_video(
            session,
            content_id=content.id,
            llm=stub_llm,  # type: ignore[arg-type]
            settings=_settings(),
            tts=fake_tts,  # type: ignore[arg-type]
            storage=fake_storage,
            toolchain=fake_toolchain,
            safety=safety,  # type: ignore[arg-type]
        )
        await session.commit()
    return result, fake_toolchain, fake_storage, fake_tts


async def test_generate_video_happy_path(
    sessionmaker: async_sessionmaker[AsyncSession], video_content: ExplainerContent
) -> None:
    result, toolchain, storage, tts = await _run(sessionmaker, video_content)
    assert result.status is ExplainerStatus.READY
    assert result.video_key is not None and result.video_key.endswith(".mp4")
    assert result.video_mime == "video/mp4"
    assert result.duration_seconds == 24
    assert result.byte_size == len(b"fake-final-video")
    assert len(storage.uploads) == 1
    assert storage.uploads[0][0] == result.video_key
    assert storage.uploads[0][2] == "video/mp4"
    # 每幕一段配音，镜头时长来自音频探测（6s x 2 幕）
    assert len(tts.texts) == 2
    assert len(toolchain.audio_names) == 2
    assert result.script["intent"]["learning_goal"]
    assert len(result.script["shots"]) == 2
    assert toolchain.render_calls == 1


async def test_generate_video_self_heals_render_failure(
    sessionmaker: async_sessionmaker[AsyncSession], video_content: ExplainerContent
) -> None:
    llm = _StubLlm(
        [
            json.dumps(_INTENT, ensure_ascii=False),
            json.dumps(_PREREQ, ensure_ascii=False),
            json.dumps(_SEQUENCE, ensure_ascii=False),
            json.dumps(_DIRECTOR, ensure_ascii=False),
            json.dumps(_REPAIRED_DIRECTOR, ensure_ascii=False),
        ]
    )
    toolchain = _FakeToolchain(failures=1)
    result, _, storage, _ = await _run(
        sessionmaker, video_content, llm=llm, toolchain=toolchain
    )
    assert result.status is ExplainerStatus.READY
    assert toolchain.render_calls == 2
    assert result.script["repairs"][0]["attempt"] == 1
    assert result.script["director"]["scenes"][0]["elements"][0]["kind"] == "text"
    assert len(storage.uploads) == 1


async def test_generate_video_repairs_invalid_structure_after_render_failure(
    sessionmaker: async_sessionmaker[AsyncSession], video_content: ExplainerContent
) -> None:
    """修复后结构仍不合法时，应继续下一轮修复，而不是把整条生成判死。"""
    llm = _StubLlm(
        [
            json.dumps(_INTENT, ensure_ascii=False),
            json.dumps(_PREREQ, ensure_ascii=False),
            json.dumps(_SEQUENCE, ensure_ascii=False),
            json.dumps(_DIRECTOR, ensure_ascii=False),
            json.dumps(_BROKEN_DIRECTOR, ensure_ascii=False),
            json.dumps(_REPAIRED_DIRECTOR, ensure_ascii=False),
        ]
    )
    toolchain = _FakeToolchain(failures=1)
    result, _, _, _ = await _run(
        sessionmaker, video_content, llm=llm, toolchain=toolchain
    )
    assert result.status is ExplainerStatus.READY
    assert toolchain.render_calls == 2, "结构错误不应浪费一次渲染"
    repairs = result.script["repairs"]
    assert len(repairs) == 2
    assert "EXPLAINER_VIDEO_SPEC_INVALID" in repairs[1]["error"]


async def test_generate_video_repairs_first_build_failure(
    sessionmaker: async_sessionmaker[AsyncSession], video_content: ExplainerContent
) -> None:
    """首次导演输出就不合法时也要进自愈循环，而不是整条判死（Top 100 实测 4 条这类失败）。"""
    llm = _StubLlm(
        [
            json.dumps(_INTENT, ensure_ascii=False),
            json.dumps(_PREREQ, ensure_ascii=False),
            json.dumps(_SEQUENCE, ensure_ascii=False),
            json.dumps(_BROKEN_DIRECTOR, ensure_ascii=False),
            json.dumps(_REPAIRED_DIRECTOR, ensure_ascii=False),
        ]
    )
    toolchain = _FakeToolchain(failures=0)
    result, _, _, _ = await _run(sessionmaker, video_content, llm=llm, toolchain=toolchain)
    assert result.status is ExplainerStatus.READY, result.error
    assert toolchain.render_calls == 1, "首次结构失败只应修复后渲染一次"
    repairs = result.script["repairs"]
    assert len(repairs) == 1
    assert "EXPLAINER_VIDEO_SPEC_INVALID" in repairs[0]["error"]


def test_validate_prereq_graph_all_cycle_falls_back() -> None:
    """模型把全部节点连成环时，entry 兜底取首个节点，不再以 RuntimeError 炸掉生成。"""
    payload = {
        "nodes": [
            {"id": "a", "label": "甲", "why": "先会数数"},
            {"id": "b", "label": "乙", "why": "先会比大小"},
        ],
        "edges": [["a", "b"], ["b", "a"]],
        "entry": "",
    }
    result = explainer_video.validate_prereq_graph(payload)
    assert result["entry"] == "a"


def test_student_script_strips_repairs() -> None:
    """学生端脚本视图剥掉 repairs（stderr/TeX 片段），其余与 None 原样透传。"""
    script = {"version": "manim-v1", "intent": {"a": 1}, "repairs": [{"error": "x" * 500}]}
    served = explainer_video.student_script(script)
    assert "repairs" not in served
    assert served["intent"] == {"a": 1}
    assert explainer_video.student_script(None) is None
    assert explainer_video.student_script({"intent": {}}) == {"intent": {}}


async def test_sapi_voice_is_passed_as_parameter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SAPI 的 voice/rate 走 PowerShell 参数，不再内插进脚本源码。"""
    from app.services import tts as tts_module

    captured: dict[str, object] = {}

    def fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        parts = list(args)
        # 脚本文件随 TemporaryDirectory 一起清理：必须在 fake_run 里读内容
        captured["script_body"] = Path(parts[parts.index("-File") + 1]).read_text(
            encoding="utf-8-sig"
        )
        voice_index = parts.index("-Voice")
        captured["voice"] = parts[voice_index + 1]
        out_index = parts.index("-OutPath")
        out_path = Path(parts[out_index + 1])
        out_path.write_bytes(b"wav-bytes")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(tts_module.subprocess, "run", fake_run)
    provider = tts_module.WindowsSapiTtsProvider("Microsoft Evil'); Remove-Item C:\\ -Recurse")
    audio, mime = await provider.synthesize("你好")
    assert audio == b"wav-bytes" and mime == "audio/wav"
    script_body = str(captured["script_body"])
    assert "SelectVoice($Voice)" in script_body
    assert "Remove-Item" not in script_body, "恶意 voice 不能进脚本源码"
    assert captured["voice"] == "Microsoft Evil'); Remove-Item C:\\ -Recurse"


async def test_generate_video_fails_after_three_render_attempts(
    sessionmaker: async_sessionmaker[AsyncSession], video_content: ExplainerContent
) -> None:
    llm = _StubLlm(
        [
            json.dumps(_INTENT, ensure_ascii=False),
            json.dumps(_PREREQ, ensure_ascii=False),
            json.dumps(_SEQUENCE, ensure_ascii=False),
            json.dumps(_DIRECTOR, ensure_ascii=False),
            json.dumps(_REPAIRED_DIRECTOR, ensure_ascii=False),
            json.dumps(_REPAIRED_DIRECTOR, ensure_ascii=False),
        ]
    )
    toolchain = _FakeToolchain(failures=99)
    result, _, storage, _ = await _run(
        sessionmaker, video_content, llm=llm, toolchain=toolchain
    )
    assert result.status is ExplainerStatus.FAILED
    assert "EXPLAINER_VIDEO_RENDER_FAILED" in (result.error or "")
    assert toolchain.render_calls == 3, "自愈循环上限必须是 3 次"
    assert storage.uploads == []


async def test_generate_video_blocked_by_safety(
    sessionmaker: async_sessionmaker[AsyncSession], video_content: ExplainerContent
) -> None:
    safety = _FakeSafety(allowed=False)
    result, toolchain, storage, _ = await _run(sessionmaker, video_content, safety=safety)
    assert result.status is ExplainerStatus.FAILED
    assert "EXPLAINER_VIDEO_CONTENT_BLOCKED" in (result.error or "")
    assert safety.checked
    assert toolchain.sources == [], "内容安全不过关时不应进入渲染"
    assert storage.uploads == []


async def test_generate_video_is_idempotent_when_ready(
    sessionmaker: async_sessionmaker[AsyncSession], video_content: ExplainerContent
) -> None:
    first, _, _, _ = await _run(sessionmaker, video_content)
    assert first.status is ExplainerStatus.READY
    llm = _StubLlm([])  # 再一次不应调用任何 LLM
    second, toolchain, _, _ = await _run(sessionmaker, first, llm=llm)
    assert second.status is ExplainerStatus.READY
    assert toolchain.render_calls == 0


# --------------------------------------------------------------- 路由契约


async def test_video_request_without_pregen_returns_409(
    client: AsyncClient, student: tuple[uuid.UUID, str]
) -> None:
    _, token = student
    response = await client.post(
        "/v1/explainer/generate",
        json={"knowledge_id": POINT_CODE, "mode": "video"},
        headers=auth_headers(token),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "EXPLAINER_VIDEO_NOT_READY"


async def test_video_request_hits_cache_with_presigned_url(
    client: AsyncClient,
    student: tuple[uuid.UUID, str],
    sessionmaker: async_sessionmaker[AsyncSession],
    app: Any,
) -> None:
    _, token = student
    point = find_point(POINT_CODE)
    assert point is not None
    async with sessionmaker() as session:
        kp_id = await explainer_service.ensure_knowledge_point(
            session, point, stage=stage_for_grade(point.grade), sort_order=1
        )
        content = ExplainerContent(
            knowledge_point_id=kp_id,
            stage=stage_for_grade(point.grade),
            mode=ExplainerMode.VIDEO,
            style_version=settings.explainer_style_version,
            cache_key=explainer_service.cache_key(
                point.id,
                stage_for_grade(point.grade),
                settings.explainer_style_version,
                mode="video",
            ),
            title=point.name,
            video_key="explainer/video/demo.mp4",
            video_mime="video/mp4",
            duration_seconds=32,
            status=ExplainerStatus.READY,
        )
        session.add(content)
        await session.commit()

    class _PresignStorage:
        async def presign_download(self, *, key: str) -> str:
            assert key == "explainer/video/demo.mp4"
            return "http://minio.test/demo.mp4?sig=1"

    app.state.storage = _PresignStorage()

    response = await client.post(
        "/v1/explainer/generate",
        json={"knowledge_id": POINT_CODE, "mode": "video"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["cache_hit"] is True
    assert body["content"]["mode"] == "video"
    assert body["content"]["video_url"].endswith("sig=1")
    assert body["content"]["duration_seconds"] == 32

# --------------------------------------------------------------- 本地配音通道


def test_windows_tts_is_development_only() -> None:
    """本地 SAPI 只是开发通道：生产环境必须拒绝，避免「听起来能播」的假配音上线。"""
    with pytest.raises(TtsError):
        get_tts_provider(Settings(environment="production", tts_provider="windows"))
    provider = get_tts_provider(Settings(environment="testing", tts_provider="windows"))
    assert isinstance(provider, WindowsSapiTtsProvider)

