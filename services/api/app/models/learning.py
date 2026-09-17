"""学情闭环业务模型：画像、掌握度、错题本、计划、复习卡。"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class MistakeState(enum.StrEnum):
    """错题掌握状态。"""

    NEW = "new"
    LEARNING = "learning"
    REVIEWING = "reviewing"
    MASTERED = "mastered"


class PlanKind(enum.StrEnum):
    """计划类型。"""

    PATH = "path"
    DAILY = "daily"
    EXAM_COUNTDOWN = "exam_countdown"


class TaskType(enum.StrEnum):
    """任务类型。"""

    LEARN = "learn"
    PRACTICE = "practice"
    REVIEW = "review"


class TaskStatus(enum.StrEnum):
    """任务状态。"""

    PENDING = "pending"
    DONE = "done"
    SKIPPED = "skipped"


class LearningProfile(Base, TimestampMixin):
    """学习行为画像（F-05：做题时长/犹豫修改/求助频次）。"""

    __tablename__ = "learning_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    learning_style: Mapped[str | None] = mapped_column(String(32))
    behavior_stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    independent_score: Mapped[float | None] = mapped_column(Float)
    assisted_score: Mapped[float | None] = mapped_column(Float)


class MasteryRecord(Base, TimestampMixin):
    """知识点掌握度（BKT 参数）。"""

    __tablename__ = "mastery_records"
    __table_args__ = (UniqueConstraint("user_id", "knowledge_point_id", name="uq_mastery_user_kp"),)

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
    mastery: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    alpha: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    beta: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_practiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MistakeBookEntry(Base, TimestampMixin):
    """错题本条目（自动归集，一键重练，移出即 removed_at 置位）。"""

    __tablename__ = "mistake_book_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_mistake_book_user_question"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(20), default="practice", nullable=False)
    wrong_answer: Mapped[str | None] = mapped_column(Text)
    error_reason: Mapped[str | None] = mapped_column(String(32))
    state: Mapped[MistakeState] = mapped_column(
        SAEnum(
            MistakeState, name="mistake_state", native_enum=False, length=20, create_constraint=True
        ),
        default=MistakeState.NEW,
        nullable=False,
    )
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Plan(Base, TimestampMixin):
    """学习计划（路径/每日/考期倒排）。"""

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[PlanKind] = mapped_column(
        SAEnum(PlanKind, name="plan_kind", native_enum=False, length=20, create_constraint=True),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class PlanTask(Base, TimestampMixin):
    """每日任务卡（3–5 个任务，学/练/复习搭配）。"""

    __tablename__ = "plan_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    task_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    task_type: Mapped[TaskType] = mapped_column(
        SAEnum(TaskType, name="task_type", native_enum=False, length=20, create_constraint=True),
        nullable=False,
    )
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(
            TaskStatus, name="task_status", native_enum=False, length=20, create_constraint=True
        ),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewCard(Base, TimestampMixin):
    """FSRS 间隔重复卡片。"""

    __tablename__ = "review_cards"
    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_review_cards_user_question"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lapses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
