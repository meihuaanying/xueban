"""微课服务（F-16）：讲解稿生成（≥600 字）与 TTS 音频异步产出。"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError, LlmError, NotFoundError, PermissionDeniedError
from app.models import KnowledgePoint, MicroLesson, MicroLessonStatus, User
from app.services.llm_client import LlmClient
from app.services.prompts import MICRO_LESSON_SYSTEM_PROMPT, MICRO_LESSON_USER_TEMPLATE
from app.services.storage_service import StorageService
from app.services.tts import TtsProvider

logger = logging.getLogger("xueban.micro_lesson")

MAX_ATTEMPTS = 3  # 首次 + 最多 2 次重试（规格书 T8.3）


async def enqueue_micro_lesson(lesson_id: uuid.UUID) -> bool:
    """把微课生成任务投入 arq 队列（失败不阻塞请求，保持 pending）。"""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await pool.enqueue_job("generate_micro_lesson", str(lesson_id))
        finally:
            close = getattr(pool, "aclose", None) or pool.close
            await close()
        return True
    except Exception:
        logger.warning("微课任务入队失败（保持 pending，可人工重试）", exc_info=True)
        return False


async def create_micro_lesson(
    session: AsyncSession, *, user: User, knowledge_point_id: uuid.UUID
) -> MicroLesson:
    """创建微课任务（异步生成，立即返回）。"""
    knowledge_point = await session.get(KnowledgePoint, knowledge_point_id)
    if knowledge_point is None:
        raise NotFoundError("知识点不存在", code="KNOWLEDGE_POINT_NOT_FOUND")
    lesson = MicroLesson(
        user_id=user.id,
        knowledge_point_id=knowledge_point.id,
        title=f"{knowledge_point.name}·微课",
        meta={"subject": knowledge_point.subject, "stage": knowledge_point.stage},
    )
    session.add(lesson)
    await session.flush()
    return lesson


async def generate_micro_lesson(
    session: AsyncSession,
    *,
    lesson_id: uuid.UUID,
    llm: LlmClient,
    tts: TtsProvider,
    storage: StorageService,
) -> MicroLesson:
    """生成讲解稿与音频（幂等；失败重试 ≤2 次后明示失败）。"""
    lesson = await session.get(MicroLesson, lesson_id)
    if lesson is None:
        raise NotFoundError("微课不存在", code="MICRO_LESSON_NOT_FOUND")
    if lesson.status == MicroLessonStatus.READY:
        return lesson

    knowledge_point = await session.get(KnowledgePoint, lesson.knowledge_point_id)
    if knowledge_point is None:
        lesson.status = MicroLessonStatus.FAILED
        lesson.error = "知识点已被删除"
        await session.flush()
        return lesson

    lesson.status = MicroLessonStatus.GENERATING
    await session.flush()

    script: str | None = None
    last_error: str | None = None
    for _attempt in range(MAX_ATTEMPTS):
        try:
            completion = await llm.complete(
                [
                    {"role": "system", "content": MICRO_LESSON_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": MICRO_LESSON_USER_TEMPLATE.format(
                            name=knowledge_point.name,
                            stage=knowledge_point.stage,
                            subject=knowledge_point.subject,
                        ),
                    },
                ],
                name="micro_lesson.script",
                temperature=0.7,
            )
            candidate = completion.content.strip()
            char_count = len(candidate)
            if not (
                settings.micro_lesson_min_chars
                <= char_count
                <= settings.micro_lesson_max_chars
            ):
                raise LlmError(
                    f"讲解稿字数 {char_count} 不在 "
                    f"{settings.micro_lesson_min_chars}~{settings.micro_lesson_max_chars} 之间",
                    code="MICRO_LESSON_LENGTH",
                    status_code=502,
                )
            script = candidate
            break
        except LlmError as exc:
            last_error = exc.message
            lesson.retries += 1
            await session.flush()
            logger.warning("微课讲解稿生成失败（第 %s 次）：%s", lesson.retries, exc.message)

    if script is None:
        lesson.status = MicroLessonStatus.FAILED
        lesson.error = f"生成失败（已重试 {lesson.retries} 次）：{last_error or '未知错误'}"
        await session.flush()
        return lesson

    try:
        audio_bytes, mime = await tts.synthesize(script)
        key = f"tts/{lesson.id}"
        extension = "wav" if "wav" in mime else "mp3"
        object_key = f"{key}.{extension}"
        await storage.upload_bytes(key=object_key, data=audio_bytes, content_type=mime)
    except Exception as exc:
        lesson.status = MicroLessonStatus.FAILED
        lesson.error = f"音频合成失败：{exc}"
        await session.flush()
        return lesson

    lesson.script = script
    lesson.char_count = len(script)
    lesson.audio_key = object_key
    lesson.audio_mime = mime
    lesson.status = MicroLessonStatus.READY
    lesson.error = None
    await session.flush()
    return lesson


async def get_audio_url(
    session: AsyncSession,
    *,
    user: User,
    lesson_id: uuid.UUID,
    storage: StorageService,
) -> tuple[MicroLesson, str]:
    """获取微课音频下载地址（未就绪返回 409）。"""
    lesson = await session.get(MicroLesson, lesson_id)
    if lesson is None:
        raise NotFoundError("微课不存在", code="MICRO_LESSON_NOT_FOUND")
    if lesson.user_id != user.id:
        raise PermissionDeniedError("无权访问该微课")
    if lesson.status != MicroLessonStatus.READY or not lesson.audio_key:
        raise AppError(
            f"微课音频尚未就绪（当前状态：{lesson.status.value}）"
            + (f"：{lesson.error}" if lesson.error else ""),
            code="MICRO_LESSON_NOT_READY",
            status_code=409,
        )
    url = await storage.presign_download(key=lesson.audio_key)
    return lesson, url
