"""Explainer 交互网页讲解服务（P1 / §5.2 生成管线）。

管线五步（§5.2），每一步失败都有明确的去处，不允许静默产出坏内容：

    ① 教学设计（LLM 出脚本 JSON，≤4 幕）
    ② 网页生成（LLM 出单文件 HTML，内联 CSS/JS）
    ③ 静态校验（explainer_sanitize：白名单 + 禁外链 + 注入 CSP + 体积）
    ④ 缓存写入（cache_key = hash(知识点, 学段, 风格版本)，跨用户共享）
    ⑤ 前端沙箱渲染（在 packages/ui 的 ExplainerFrame 里，不在本模块）

§5.4 的两条降级纪律在这里落地：
- 交互页生成不出合格产物 → 退回「图文分步讲解」（:func:`render_degraded_html`），
  页面绝不白屏；
- 重试仍失败 → job 标记 failed 并带上原因，前端据此显示静态兜底文案。
"""

from __future__ import annotations

import hashlib
import html as html_lib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.data.curriculum import (
    KnowledgePoint as CurriculumPoint,
)
from app.data.curriculum import (
    find_point,
    grade_name,
    subject_name,
)
from app.errors import AppError, LlmError, NotFoundError, RateLimitedError
from app.models import (
    ExplainerContent,
    ExplainerFeedback,
    ExplainerJob,
    ExplainerMode,
    ExplainerStatus,
    MasteryRecord,
    MistakeBookEntry,
    Question,
    QuestionKnowledgePoint,
)
from app.models import (
    KnowledgePoint as KnowledgePointModel,
)
from app.services.explainer_sanitize import SanitizeResult, sanitize_explainer_html
from app.services.llm_client import LlmClient
from app.services.llm_json import extract_json_object
from app.services.prompts import (
    EXPLAINER_DESIGN_SYSTEM_PROMPT,
    EXPLAINER_DESIGN_USER_TEMPLATE,
    EXPLAINER_HTML_SYSTEM_PROMPT,
    EXPLAINER_HTML_USER_TEMPLATE,
)
from app.services.safety_service import SafetyService

logger = logging.getLogger("xueban.explainer")

#: 题库管线与讲解共用同一个学段常量，避免两处各写一个字符串。
ELEMENTARY_STAGE = "grade1_2"


class ExplainerError(AppError):
    """讲解生成相关业务错误。"""

    status_code = 502
    code = "EXPLAINER_ERROR"


# ---------------------------------------------------------------- 缓存键


def cache_key(point_code: str, stage: str, style_version: str) -> str:
    """§5.2 ④：缓存键 = hash(知识点, 学段, 风格版本)。

    风格版本进键是刻意的：改教学风格就换版本号，历史讲解自然作废，
    不会出现「新风格的孩子看到旧讲解」。
    """
    raw = f"{point_code}|{stage}|{style_version}".encode()
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------- 知识点解析


async def ensure_knowledge_point(
    session: AsyncSession, point: CurriculumPoint, *, stage: str, sort_order: int
) -> uuid.UUID:
    """把课程树里的知识点写进 knowledge_points（幂等）。

    讲解与出题共用同一套知识点行，所以这里不新建表、也不复制数据。
    """
    existing = await session.execute(
        select(KnowledgePointModel).where(KnowledgePointModel.code == point.id)
    )
    record = existing.scalar_one_or_none()
    if record is None:
        record = KnowledgePointModel(
            code=point.id,
            name=point.name,
            subject=point.subject,
            stage=stage,
            sort_order=sort_order,
        )
        session.add(record)
        await session.flush()
    return record.id


async def resolve_point(
    session: AsyncSession, knowledge_id: str, *, settings: Settings
) -> tuple[KnowledgePointModel, CurriculumPoint]:
    """把 ``knowledge_id`` 解析成 (库里的知识点行, 课程树知识点)。

    同时接受课程编码（如 ``math.add-sub-10``）与库内 UUID——前端旅程页拿到的
    是课程编码，运维/家长端可能拿的是 UUID，两种都得能用。
    """
    code = knowledge_id
    try:
        as_uuid = uuid.UUID(knowledge_id)
    except ValueError:
        as_uuid = None

    record: KnowledgePointModel | None = None
    if as_uuid is not None:
        found = await session.execute(
            select(KnowledgePointModel).where(KnowledgePointModel.id == as_uuid)
        )
        record = found.scalar_one_or_none()
        if record is None:
            raise NotFoundError("知识点不存在", code="KNOWLEDGE_POINT_NOT_FOUND")
        code = record.code

    point = find_point(code)
    if point is None:
        raise NotFoundError(
            f"课程树里没有知识点 {code}", code="CURRICULUM_POINT_NOT_FOUND"
        )
    if record is None:
        record_id = await ensure_knowledge_point(
            session, point, stage=ELEMENTARY_STAGE, sort_order=point.difficulty_band
        )
        await session.flush()
        found = await session.execute(
            select(KnowledgePointModel).where(KnowledgePointModel.id == record_id)
        )
        created = found.scalar_one_or_none()
        if created is None:  # pragma: no cover - 刚写入却读不到属于数据库异常
            raise AppError(
                "知识点写入后读不到",
                code="KNOWLEDGE_POINT_WRITE_FAILED",
                status_code=500,
            )
        record = created
    return record, point


# ---------------------------------------------------------------- 学生画像

#: 没有用户上下文（如后台预生成）时的占位画像。
_EMPTY_PROFILE = "- 当前掌握度：暂无记录\n- 近期错误：暂无记录"


async def _student_profile(session: AsyncSession, user_id: uuid.UUID, kp_id: uuid.UUID) -> str:
    """拼一段给教学设计用的学生画像文字（掌握度 + 近期错误）。

    画像只取「最近 3 条错题的题干」，不落用户原文，避免把未脱敏的输入喂给模型。
    """
    mastery_row = await session.execute(
        select(MasteryRecord.mastery).where(
            MasteryRecord.user_id == user_id, MasteryRecord.knowledge_point_id == kp_id
        )
    )
    mastery = mastery_row.scalar_one_or_none()

    error_rows = await session.execute(
        select(Question.stem, MistakeBookEntry.error_reason)
        .join(QuestionKnowledgePoint, QuestionKnowledgePoint.question_id == Question.id)
        .join(MistakeBookEntry, MistakeBookEntry.question_id == Question.id)
        .where(
            MistakeBookEntry.user_id == user_id,
            QuestionKnowledgePoint.knowledge_point_id == kp_id,
        )
        .order_by(MistakeBookEntry.created_at.desc())
        .limit(3)
    )
    errors = [
        f"{stem.strip()[:60]}（{reason}）" if reason else stem.strip()[:60]
        for stem, reason in error_rows.all()
    ]

    mastery_text = "暂无记录（按新知识点讲）" if mastery is None else f"{mastery:.0%}"
    errors_text = "、".join(errors) if errors else "暂无记录"
    return f"- 当前掌握度：{mastery_text}\n- 近期错误：{errors_text}"


# ---------------------------------------------------------------- ①② 生成


def extract_html_document(raw: str) -> str:
    """从模型输出里取出 HTML 源码（容忍 Markdown 代码块围栏）。"""
    text = raw.strip()
    fence = re.match(r"^```(?:html|HTML)?\s*\n?(.*?)\n?```$", text, re.DOTALL)
    if fence is not None:
        text = fence.group(1)
    index = text.lower().find("<!doctype")
    if index < 0:
        index = text.lower().find("<html")
    if index > 0:
        text = text[index:]
    if "<" not in text:
        raise ExplainerError("模型未返回 HTML", code="EXPLAINER_HTML_MISSING")
    return text


async def design_script(
    *, llm: LlmClient, point: CurriculumPoint, profile: str, settings: Settings
) -> dict[str, Any]:
    """① 教学设计：输出 ≤4 幕的教学脚本 JSON。"""
    response = await llm.complete(
        [
            {"role": "system", "content": EXPLAINER_DESIGN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": EXPLAINER_DESIGN_USER_TEMPLATE.format(
                    subject=point.subject,
                    subject_name=subject_name(point.subject),
                    grade_name=grade_name(point.grade),
                    unit_name=point.unit_name,
                    point_name=point.name,
                    objective=point.objective,
                    prerequisites="、".join(point.prerequisites) or "无",
                    mastery=profile,
                    recent_errors=profile,
                    max_acts=settings.explainer_max_acts,
                ),
            },
        ],
        model=settings.content_generation_model,
        max_tokens=settings.content_max_tokens,
        temperature=0.6,
    )
    script = extract_json_object(response.content, code="EXPLAINER_SCRIPT_INVALID")
    acts = script.get("acts")
    if not isinstance(acts, list) or not acts:
        raise ExplainerError("教学脚本缺少 acts", code="EXPLAINER_SCRIPT_INVALID")
    script["acts"] = acts[: settings.explainer_max_acts]
    script["title"] = str(script.get("title") or point.name)[:200]
    return script


def _render_script_for_prompt(script: dict[str, Any]) -> str:
    lines: list[str] = []
    for index, act in enumerate(script.get("acts", []), start=1):
        if not isinstance(act, dict):
            continue
        interaction = act.get("interaction") or {}
        lines.append(
            f"第{index}幕·{act.get('name', '')}"
            f"\n  目标：{act.get('goal', '')}"
            f"\n  讲解词：{act.get('narration', '')}"
            f"\n  交互：{interaction.get('kind', 'tap')} —— {interaction.get('prompt', '')}"
            f"\n  选项：{' / '.join(str(o) for o in (interaction.get('options') or []))}"
            f"\n  正确答案：{interaction.get('answer', '')}"
            f"\n  画面：{act.get('visual', '')}"
        )
    if script.get("checkpoint"):
        lines.append(f"收束问题：{script['checkpoint']}")
    return "\n".join(lines)


async def render_html(
    *, llm: LlmClient, point: CurriculumPoint, script: dict[str, Any], settings: Settings
) -> str:
    """② 网页生成：输出单文件 HTML 源码。"""
    acts = script.get("acts", [])
    # HTML 比脚本长得多，但推理模型的开销不随页数线性增长；给足预算避免正文被截断。
    max_tokens = min(settings.content_max_tokens, settings.content_tokens_per_question * 8)
    response = await llm.complete(
        [
            {"role": "system", "content": EXPLAINER_HTML_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": EXPLAINER_HTML_USER_TEMPLATE.format(
                    title=script.get("title", point.name),
                    point_name=point.name,
                    grade_name=grade_name(point.grade),
                    subject_name=subject_name(point.subject),
                    hook=script.get("hook", ""),
                    act_count=len(acts),
                    script=_render_script_for_prompt(script),
                ),
            },
        ],
        model=settings.content_generation_model,
        max_tokens=max_tokens,
        temperature=0.4,
    )
    return extract_html_document(response.content)


# ---------------------------------------------------------------- 降级产物


_TAG_RE = re.compile(r"<[^>]+>")
_STYLE = """
body{font-family:system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
     margin:0;padding:16px;background:#FFFDF7;color:#1F2933;line-height:1.9;font-size:20px}
h1{font-size:26px;margin:0 0 4px}
.hook{color:#5B6B7B;margin:0 0 16px}
.act{background:#fff;border:2px solid #E4E7EB;border-radius:16px;padding:14px 16px;margin:0 0 12px}
.act h2{font-size:21px;margin:0 0 6px;color:#2B6CB0}
.act p{margin:0 0 8px}
.doing{color:#2F855A;font-weight:600}
.check{margin-top:20px;padding:14px 16px;background:#EBF8FF;border-radius:16px}
""".strip()


def strip_html_text(html: str) -> str:
    """把 HTML 压成纯文本，用于内容安全过滤。"""
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    return html_lib.unescape(_TAG_RE.sub(" ", text))


def render_degraded_html(*, title: str, script: dict[str, Any]) -> str:
    """§5.4 降级：交互页渲染失败/超时时的「图文分步讲解」。

    刻意不依赖任何脚本——它必须比交互页更可靠，否则降级本身也会白屏。
    """
    parts = [
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">",
        f"<title>{html_lib.escape(title)}</title><style>{_STYLE}</style></head><body>",
        f"<h1>{html_lib.escape(title)}</h1>",
        f"<p class=\"hook\">{html_lib.escape(str(script.get('hook') or '我们一步一步来看。'))}</p>",
    ]
    for index, act in enumerate(script.get("acts", []), start=1):
        if not isinstance(act, dict):
            continue
        interaction = act.get("interaction") or {}
        parts.append('<section class="act">')
        parts.append(f"<h2>第{index}步：{html_lib.escape(str(act.get('name') or '一起做'))}</h2>")
        parts.append(f"<p>{html_lib.escape(str(act.get('narration') or ''))}</p>")
        if interaction.get("prompt"):
            parts.append(
                f"<p class=\"doing\">动手做一做：{html_lib.escape(str(interaction['prompt']))}</p>"
            )
        parts.append("</section>")
    if script.get("checkpoint"):
        closing = html_lib.escape(str(script["checkpoint"]))
        parts.append(f'<div class="check">说给爸爸妈妈听：{closing}</div>')
    parts.append("</body></html>")
    return "".join(parts)


# ---------------------------------------------------------------- 生成主流程


async def _apply_safety(
    *,
    session: AsyncSession,
    safety: SafetyService | None,
    user_id: uuid.UUID | None,
    html: str,
) -> None:
    """§5.4：生成内容入库前必须过内容安全过滤。

    ``safety`` 为 None 只发生在测试替身里；生产路径一定会传（main.py 注入单例）。
    """
    if safety is None:
        return
    decision = await safety.check_and_record(
        session, text=strip_html_text(html), scene="explainer", user_id=user_id
    )
    if not decision.allowed:
        raise ExplainerError(
            "讲解内容未通过内容安全检查", code="EXPLAINER_CONTENT_BLOCKED", status_code=422
        )


async def generate_content(
    session: AsyncSession,
    *,
    content_id: uuid.UUID,
    llm: LlmClient,
    settings: Settings,
    safety: SafetyService | None = None,
    user_id: uuid.UUID | None = None,
) -> ExplainerContent:
    """跑完 §5.2 的 ①②③，写回消毒后的 HTML。失败时降级为图文分步讲解。"""
    found = await session.execute(
        select(ExplainerContent).where(ExplainerContent.id == content_id)
    )
    content = found.scalar_one()
    if content.status is ExplainerStatus.READY:
        return content  # 幂等：重复入队不重复生成

    record = await session.execute(
        select(KnowledgePointModel).where(KnowledgePointModel.id == content.knowledge_point_id)
    )
    kp = record.scalar_one()
    point = find_point(kp.code)
    if point is None:
        content.status = ExplainerStatus.FAILED
        content.error = f"课程树里没有知识点 {kp.code}"
        return content

    content.status = ExplainerStatus.GENERATING
    content.attempts += 1

    script: dict[str, Any] = {}
    reason: str | None = None
    result: SanitizeResult | None = None

    try:
        profile = _EMPTY_PROFILE
        if user_id is not None:
            profile = await _student_profile(session, user_id, kp.id)
        script = await design_script(llm=llm, point=point, profile=profile, settings=settings)
        content.script = script
        raw = await render_html(llm=llm, point=point, script=script, settings=settings)
        result = sanitize_explainer_html(raw, max_bytes=settings.explainer_max_bytes)
        if not result.ok:
            reason = result.reason
        else:
            await _apply_safety(
                session=session, safety=safety, user_id=user_id, html=result.html or ""
            )
    except (LlmError, AppError) as exc:
        reason = f"{exc.code or type(exc).__name__}：{exc.message}"
    except Exception:
        logger.exception("Explainer 生成异常")
        reason = "生成过程异常"

    if result is not None and result.ok:
        content.html = result.html
        content.byte_size = result.byte_size
        content.degraded = False
        content.status = ExplainerStatus.READY
        content.error = None
        return content

    # §5.4：交互页拿不到就降级为图文分步讲解，绝不返回半成品、绝不白屏。
    logger.warning("Explainer 交互页生成失败，降级图文分步：%s", reason)
    fallback = render_degraded_html(title=content.title, script=script)
    fallback_result = sanitize_explainer_html(fallback, max_bytes=settings.explainer_max_bytes)
    content.html = fallback_result.html if fallback_result.ok else fallback
    content.byte_size = len(content.html.encode("utf-8"))
    content.degraded = True
    content.status = ExplainerStatus.READY
    content.error = reason
    content.meta = {**content.meta, "fallback_reason": reason}
    return content


# ---------------------------------------------------------------- 缓存与请求


async def get_cached_content(
    session: AsyncSession, *, point_code: str, stage: str, settings: Settings
) -> ExplainerContent | None:
    """按缓存键取一份**已就绪**的讲解（§5.2 ④ + §5.1「已预生成的讲解直接秒开」）。"""
    key = cache_key(point_code, stage, settings.explainer_style_version)
    found = await session.execute(
        select(ExplainerContent).where(
            ExplainerContent.cache_key == key,
            ExplainerContent.status == ExplainerStatus.READY,
        )
    )
    return found.scalar_one_or_none()


async def _reserve_content(
    session: AsyncSession,
    *,
    point_code: str,
    kp_id: uuid.UUID,
    stage: str,
    title: str,
    mode: ExplainerMode,
    settings: Settings,
) -> ExplainerContent:
    """占一行缓存（INSERT ... ON CONFLICT DO NOTHING）。

    并发场景下多个学生会同时触发同一知识点，用 upsert 而不是「查了没有再插」，
    否则会撞 ``uq_explainer_contents_cache_key`` 让其中一个请求 500。
    """
    key = cache_key(point_code, stage, settings.explainer_style_version)
    stmt = (
        pg_insert(ExplainerContent)
        .values(
            id=uuid.uuid4(),
            knowledge_point_id=kp_id,
            stage=stage,
            mode=mode,
            style_version=settings.explainer_style_version,
            cache_key=key,
            title=title[:200],
            script={},
            degraded=False,
            byte_size=0,
            status=ExplainerStatus.PENDING,
            attempts=0,
            meta={},
        )
        .on_conflict_do_nothing(index_elements=["cache_key"])
        .returning(ExplainerContent.id)
    )
    inserted = (await session.execute(stmt)).scalar_one_or_none()
    found = await session.execute(
        select(ExplainerContent).where(ExplainerContent.cache_key == key)
    )
    content = found.scalar_one()
    if inserted is not None:
        content.id = inserted
    return content


async def daily_usage(session: AsyncSession, user_id: uuid.UUID) -> int:
    """今天已经发起的讲解生成次数（缓存命中不计入）。"""
    since = datetime.now(UTC) - timedelta(hours=24)
    rows = await session.execute(
        select(func.count())
        .select_from(ExplainerJob)
        .where(ExplainerJob.user_id == user_id, ExplainerJob.created_at >= since)
    )
    return int(rows.scalar_one() or 0)


async def request_explainer(
    session: AsyncSession,
    *,
    user: Any,
    knowledge_id: str,
    mode: ExplainerMode,
    settings: Settings,
    enqueue: bool = True,
) -> tuple[ExplainerJob, ExplainerContent | None]:
    """``POST /v1/explainer/generate`` 的业务逻辑。

    返回 ``(job, content)``：``content`` 非空且 status=READY 表示缓存命中
    （§5.5：此时接口返回 200 与内容，而不是 202 + job_id）。
    """
    kp, point = await resolve_point(session, knowledge_id, settings=settings)

    cached = await get_cached_content(
        session, point_code=point.id, stage=kp.stage, settings=settings
    )
    if cached is not None and cached.mode is mode:
        job = ExplainerJob(
            user_id=user.id,
            knowledge_point_id=kp.id,
            content_id=cached.id,
            mode=mode,
            status=ExplainerStatus.READY,
            cache_hit=True,
        )
        session.add(job)
        await session.flush()
        return job, cached

    used = await daily_usage(session, user.id)
    if used >= settings.explainer_daily_quota:
        raise RateLimitedError(
            f"今天的讲解额度用完了（{settings.explainer_daily_quota} 次），明天再来吧",
            code="EXPLAINER_QUOTA_EXCEEDED",
        )

    content = await _reserve_content(
        session,
        point_code=point.id,
        kp_id=kp.id,
        stage=kp.stage,
        title=point.name,
        mode=mode,
        settings=settings,
    )
    job = ExplainerJob(
        user_id=user.id,
        knowledge_point_id=kp.id,
        content_id=content.id,
        mode=mode,
        status=content.status,
    )
    session.add(job)
    await session.flush()

    if content.status is ExplainerStatus.PENDING and enqueue:
        enqueued = await enqueue_explainer(content.id)
        if enqueued and content.status is ExplainerStatus.PENDING:
            job.status = ExplainerStatus.GENERATING
            await session.execute(
                update(ExplainerContent)
                .where(ExplainerContent.id == content.id)
                .values(status=ExplainerStatus.GENERATING)
            )
    return job, None


async def enqueue_explainer(content_id: uuid.UUID) -> bool:
    """把生成任务投入 arq 队列（失败不阻塞请求，保持 pending 可人工重试）。"""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings as ArqRedisSettings

        from app.config import settings as global_settings

        pool = await create_pool(ArqRedisSettings.from_dsn(global_settings.redis_url))
        try:
            await pool.enqueue_job("generate_explainer_content", str(content_id))
        finally:
            close = getattr(pool, "aclose", None) or pool.close
            await close()
        return True
    except Exception:
        logger.warning("Explainer 任务入队失败（保持 pending，可人工重试）", exc_info=True)
        return False


# ---------------------------------------------------------------- 反馈


async def record_feedback(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    content_id: uuid.UUID,
    understood: bool,
    note: str | None,
) -> ExplainerFeedback:
    """「看懂了 / 还是不懂」回流画像（§5.5 第四个端点）。"""
    found = await session.execute(
        select(ExplainerContent).where(ExplainerContent.id == content_id)
    )
    if found.scalar_one_or_none() is None:
        raise NotFoundError("讲解不存在", code="EXPLAINER_NOT_FOUND")
    feedback = ExplainerFeedback(
        user_id=user_id,
        content_id=content_id,
        understood=understood,
        note=(note or "").strip()[:500] or None,
    )
    session.add(feedback)
    await session.flush()
    return feedback


__all__ = [
    "ELEMENTARY_STAGE",
    "ExplainerError",
    "cache_key",
    "daily_usage",
    "design_script",
    "enqueue_explainer",
    "ensure_knowledge_point",
    "extract_html_document",
    "generate_content",
    "get_cached_content",
    "record_feedback",
    "render_degraded_html",
    "render_html",
    "request_explainer",
    "resolve_point",
    "strip_html_text",
]