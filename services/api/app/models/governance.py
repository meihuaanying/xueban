"""治理域模型：题库版本、质量巡检、A/B 实验、告警记录（F-44~F-47 / T7.4）。"""

from __future__ import annotations

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class QuestionVersion(Base, TimestampMixin):
    """题目解析/内容版本历史（F-44：解析修改留版本历史）。"""

    __tablename__ = "question_versions"
    __table_args__ = (UniqueConstraint("question_id", "version", name="uq_question_versions_no"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    editor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    change_note: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class InspectionReport(Base, TimestampMixin):
    """每日 AI 质量巡检报告（F-45）。"""

    __tablename__ = "inspection_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flagged_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wrong_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sympy_checked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sympy_passed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    redline_hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alerted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class Experiment(Base, TimestampMixin):
    """A/B 实验（F-47：提示词版本 / 讲解策略分组）。"""

    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    variants: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    metric: Mapped[str] = mapped_column(String(64), default="accuracy", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExperimentAssignment(Base, TimestampMixin):
    """实验分组（同用户恒定同组）。"""

    __tablename__ = "experiment_assignments"
    __table_args__ = (
        UniqueConstraint("experiment_id", "user_id", name="uq_experiment_assignments"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    variant: Mapped[str] = mapped_column(String(32), nullable=False)


class AlertRecord(Base, TimestampMixin):
    """巡检/红线告警投递记录（T7.4：webhook 可接飞书机器人）。"""

    __tablename__ = "alert_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    target_url: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="skipped", nullable=False)
    response_code: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
