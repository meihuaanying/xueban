"""测评/模考与批改记录模型。"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class ExamKind(enum.StrEnum):
    """测评类型：模考 / 无辅助独立测评 / 入学诊断。"""

    MOCK = "mock"
    SOLO = "solo"
    DIAGNOSIS = "diagnosis"


class ExamStatus(enum.StrEnum):
    """测评状态。"""

    PREPARING = "preparing"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"


class GradingKind(enum.StrEnum):
    """批改类型。"""

    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"
    ESSAY = "essay"
    SPEAKING = "speaking"
    CODE = "code"


class Exam(Base, TimestampMixin):
    """试卷/测评实例。"""

    __tablename__ = "exams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[ExamKind] = mapped_column(
        SAEnum(ExamKind, name="exam_kind", native_enum=False, length=20, create_constraint=True),
        default=ExamKind.MOCK,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    time_limit_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[ExamStatus] = mapped_column(
        SAEnum(
            ExamStatus, name="exam_status", native_enum=False, length=20, create_constraint=True
        ),
        default=ExamStatus.PREPARING,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class ExamAnswer(Base, TimestampMixin):
    """逐题作答与诊断。"""

    __tablename__ = "exam_answers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_answer: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[float | None] = mapped_column(Float)
    diagnosis: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class GradingRecord(Base, TimestampMixin):
    """批改记录（客观/主观/作文/口语/代码）。"""

    __tablename__ = "grading_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL")
    )
    kind: Mapped[GradingKind] = mapped_column(
        SAEnum(
            GradingKind, name="grading_kind", native_enum=False, length=20, create_constraint=True
        ),
        nullable=False,
    )
    input_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    score: Mapped[float | None] = mapped_column(Float)
    model: Mapped[str | None] = mapped_column(String(64))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    excerpt: Mapped[str | None] = mapped_column(Text)
