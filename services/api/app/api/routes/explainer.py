"""Explainer 路由（P1 / §5.5：生成 → 轮询 → 取内容 → 反馈）。

状态码契约照 §5.5 写死：
- 缓存命中 → **200** 并直接带内容（前端秒开，不进轮询）；
- 需要生成 → **202** 只带 ``job_id``，前端轮询 ``GET /v1/explainer/{job_id}``；
- 触发每日限额 → **429**，错误码 ``EXPLAINER_QUOTA_EXCEEDED``。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.config import settings
from app.errors import NotFoundError
from app.models import ExplainerContent, ExplainerFeedback, ExplainerJob, ExplainerMode, User
from app.schemas.explainer import (
    ExplainerContentOut,
    ExplainerContentResponse,
    ExplainerFeedbackRequest,
    ExplainerFeedbackResponse,
    ExplainerGenerateRequest,
    ExplainerGenerateResponse,
    ExplainerJobResponse,
)
from app.services import explainer_service

router = APIRouter(prefix="/v1/explainer", tags=["explainer"])


def _content_out(content: ExplainerContent) -> ExplainerContentOut:
    return ExplainerContentOut(
        id=content.id,
        # 前端拿这个 id 就能再次请求（讲解页会长期开在错题详情里）
        knowledge_id=content.knowledge_point_id.hex,
        stage=content.stage,
        title=content.title,
        status=content.status.value,
        html=content.html or "",
        degraded=content.degraded,
        byte_size=content.byte_size,
        script=content.script,
        render_timeout_seconds=settings.explainer_render_timeout_seconds,
    )


async def _load_job(session: AsyncSession, job_id: uuid.UUID, user: User) -> ExplainerJob:
    found = await session.execute(select(ExplainerJob).where(ExplainerJob.id == job_id))
    job = found.scalar_one_or_none()
    if job is None or job.user_id != user.id:
        # 不区分「不存在」与「不是你的」，避免用 job_id 探测他人数据
        raise NotFoundError("讲解任务不存在", code="EXPLAINER_JOB_NOT_FOUND")
    return job


async def _load_content(session: AsyncSession, content_id: uuid.UUID) -> ExplainerContent:
    found = await session.execute(
        select(ExplainerContent).where(ExplainerContent.id == content_id)
    )
    content = found.scalar_one_or_none()
    if content is None:
        raise NotFoundError("讲解内容不存在", code="EXPLAINER_NOT_FOUND")
    return content


@router.post(
    "/generate",
    response_model=ExplainerGenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="生成交互讲解（缓存命中直接 200 返回内容）",
)
async def generate_explainer(
    payload: ExplainerGenerateRequest,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExplainerGenerateResponse:
    """触发讲解生成。缓存命中时改写状态码为 200 并直接带内容。"""
    job, content = await explainer_service.request_explainer(
        session,
        user=user,
        knowledge_id=payload.knowledge_id,
        mode=ExplainerMode(payload.mode),
        settings=settings,
    )
    await session.commit()
    if content is not None:
        response.status_code = status.HTTP_200_OK
        return ExplainerGenerateResponse(
            job_id=job.id,
            status=job.status.value,
            cache_hit=True,
            content=_content_out(content),
        )
    return ExplainerGenerateResponse(job_id=job.id, status=job.status.value)


@router.get(
    "/{job_id}",
    response_model=ExplainerJobResponse,
    summary="轮询生成进度",
)
async def get_explainer_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExplainerJobResponse:
    """按 job_id 查进度；就绪时带上消毒后的 HTML。"""
    job = await _load_job(session, job_id, user)
    content: ExplainerContent | None = None
    if job.content_id is not None:
        content = await _load_content(session, job.content_id)
    return ExplainerJobResponse(
        job_id=job.id,
        status=job.status.value,
        error=job.error or (content.error if content is not None else None),
        content=_content_out(content) if content is not None else None,
    )


@router.get(
    "/content/{content_id}",
    response_model=ExplainerContentResponse,
    summary="获取已生成的讲解内容",
)
async def get_explainer_content(
    content_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExplainerContentResponse:
    """取已生成内容（含消毒后 HTML）。

    内容按知识点跨用户共享，所以这里不校验归属——但必须登录：
    未成年人内容不对匿名流量开放。
    """
    content = await _load_content(session, content_id)
    return ExplainerContentResponse(content=_content_out(content))


@router.post(
    "/feedback",
    response_model=ExplainerFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="记录「看懂了 / 还是不懂」",
)
async def post_explainer_feedback(
    payload: ExplainerFeedbackRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExplainerFeedbackResponse:
    """反馈回流画像，并返回该内容的累计看懂/没看懂次数。"""
    feedback = await explainer_service.record_feedback(
        session,
        user_id=user.id,
        content_id=payload.content_id,
        understood=payload.understood,
        note=payload.note,
    )
    await session.commit()

    rows = await session.execute(
        select(
            ExplainerFeedback.understood,
            func.count(),
        )
        .where(ExplainerFeedback.content_id == payload.content_id)
        .group_by(ExplainerFeedback.understood)
    )
    understood_count = 0
    confused_count = 0
    for flag, total in rows.all():
        if flag:
            understood_count = int(total)
        else:
            confused_count = int(total)

    return ExplainerFeedbackResponse(
        feedback_id=feedback.id,
        content_id=feedback.content_id,
        understood=feedback.understood,
        understood_count=understood_count,
        confused_count=confused_count,
    )