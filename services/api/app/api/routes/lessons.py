"""微课路由（F-16：异步生成 + 音频地址）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.config import settings
from app.models import User
from app.schemas.lesson import (
    MicroLessonAudioResponse,
    MicroLessonCreateRequest,
    MicroLessonResponse,
)
from app.services import lesson_service

router = APIRouter(prefix="/v1/micro-lessons", tags=["micro-lessons"])


def _lesson_out(lesson: object, lesson_id: uuid.UUID) -> MicroLessonResponse:
    from app.models import MicroLesson

    assert isinstance(lesson, MicroLesson)
    return MicroLessonResponse(
        lesson_id=lesson_id,
        title=lesson.title,
        status=lesson.status.value,
        char_count=lesson.char_count,
        retries=lesson.retries,
        error=lesson.error,
    )


@router.post(
    "",
    response_model=MicroLessonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建知识点微课（异步生成，F-16）",
)
async def create_lesson(
    payload: MicroLessonCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MicroLessonResponse:
    """创建微课并投递异步生成任务（不阻塞请求）。"""
    lesson = await lesson_service.create_micro_lesson(
        session, user=user, knowledge_point_id=payload.knowledge_point_id
    )
    lesson_id = lesson.id
    await session.commit()
    await lesson_service.enqueue_micro_lesson(lesson_id)
    return _lesson_out(lesson, lesson_id)


@router.get(
    "/{lesson_id}/audio",
    response_model=MicroLessonAudioResponse,
    summary="微课音频地址（可在线播放）",
)
async def get_audio(
    lesson_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MicroLessonAudioResponse:
    """返回预签名音频地址；未就绪返回 409。"""
    lesson, url = await lesson_service.get_audio_url(
        session, user=user, lesson_id=lesson_id, storage=request.app.state.storage
    )
    return MicroLessonAudioResponse(
        lesson_id=lesson.id,
        url=url,
        mime=lesson.audio_mime or "audio/wav",
        expires_in=settings.presign_expire_seconds,
    )
