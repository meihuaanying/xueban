"""微课模型（F-16：讲解稿 + TTS 音频异步生成）。"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class MicroLessonStatus(enum.StrEnum):
    """微课生成状态。"""

    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class MicroLesson(Base, TimestampMixin):
    """知识点微课（异步生成讲解稿与音频）。"""

    __tablename__ = "micro_lessons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    script: Mapped[str | None] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    audio_key: Mapped[str | None] = mapped_column(String(512))
    audio_mime: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[MicroLessonStatus] = mapped_column(
        SAEnum(
            MicroLessonStatus,
            name="micro_lesson_status",
            native_enum=False,
            length=20,
            create_constraint=True,
        ),
        default=MicroLessonStatus.PENDING,
        nullable=False,
    )
    retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
