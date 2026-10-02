"""Explainer 交互网页讲解模型（P1 / §5）。

三张表对应三件事：

- :class:`ExplainerContent`：**跨用户共享**的生成产物。缓存键是
  ``hash(知识点, 学段, 风格版本)``（§5.2 ④），所以同一知识点全平台只生成一次，
  命中即秒开（§5.1 触发场景 3「已预生成的讲解直接秒开」）。
- :class:`ExplainerJob`：某个学生触发的**一次生成请求**。它承载 §5.5 的
  ``202 {job_id}`` 契约，同时天然就是「每用户每日次数」的计数依据。
- :class:`ExplainerFeedback`：「看懂了 / 还是不懂」（§5.5 第四个端点）回流画像。
"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
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


class ExplainerMode(enum.StrEnum):
    """讲解形态（P1 只交付 interactive；video 见 §5.3 P3）。"""

    INTERACTIVE = "interactive"
    VIDEO = "video"


class ExplainerStatus(enum.StrEnum):
    """生成状态机。"""

    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class ExplainerContent(Base, TimestampMixin):
    """一个知识点的讲解网页（已消毒，单文件，跨用户共享）。"""

    __tablename__ = "explainer_contents"
    __table_args__ = (UniqueConstraint("cache_key", name="uq_explainer_contents_cache_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    mode: Mapped[ExplainerMode] = mapped_column(
        SAEnum(
            ExplainerMode,
            name="explainer_mode",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=ExplainerMode.INTERACTIVE,
        nullable=False,
    )
    #: 教学风格版本。换版本 = 换 key = 历史讲解自然作废，不会新旧风格混用。
    style_version: Mapped[str] = mapped_column(String(16), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    #: 消毒后的单文件 HTML（§5.2 ③ 保证只含内联 CSS/JS，无任何外链）。
    html: Mapped[str | None] = mapped_column(Text)
    #: 教学脚本（§5.2 ①）：≤4 幕，引入 → 拆解 → 交互点 → 收束。
    script: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    #: True 表示这是 §5.4 的降级产物：交互页渲染失败/超时时的「图文分步讲解」。
    degraded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[ExplainerStatus] = mapped_column(
        SAEnum(
            ExplainerStatus,
            name="explainer_status",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=ExplainerStatus.PENDING,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class ExplainerJob(Base, TimestampMixin):
    """一次讲解生成请求（§5.5 的 job_id 对应这张表）。"""

    __tablename__ = "explainer_jobs"
    __table_args__ = (Index("ix_explainer_jobs_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True
    )
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("explainer_contents.id", ondelete="SET NULL"), index=True
    )
    mode: Mapped[ExplainerMode] = mapped_column(
        SAEnum(
            ExplainerMode,
            name="explainer_job_mode",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=ExplainerMode.INTERACTIVE,
        nullable=False,
    )
    status: Mapped[ExplainerStatus] = mapped_column(
        SAEnum(
            ExplainerStatus,
            name="explainer_job_status",
            native_enum=False,
            length=16,
            create_constraint=True,
        ),
        default=ExplainerStatus.PENDING,
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text)
    #: 命中缓存直接 200 时置 True——这类请求不计入 §5.4 的每日限额。
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ExplainerFeedback(Base, TimestampMixin):
    """学生对某份讲解的「看懂了 / 还是不懂」反馈（§5.5 回流画像）。"""

    __tablename__ = "explainer_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("explainer_contents.id", ondelete="CASCADE"), index=True
    )
    understood: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: 学生原话/备注，可空。
    note: Mapped[str | None] = mapped_column(String(500))