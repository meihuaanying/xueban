"""练习记录模型（F-17~F-19 的数据基座：7 天去重、错题归集、FSRS 联动、行为画像）。"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class PracticeSource(enum.StrEnum):
    """练习来源。"""

    PRACTICE = "practice"
    REPRACTICE = "repractice"
    VARIANT = "variant"


class PracticeRecord(Base, TimestampMixin):
    """一次练习作答（不含重做限制，保留全部历史用于画像与去重）。"""

    __tablename__ = "practice_records"
    __table_args__ = (
        UniqueConstraint("user_id", "client_event_id", name="uq_practice_client_event"),
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
    source: Mapped[PracticeSource] = mapped_column(
        SAEnum(
            PracticeSource,
            name="practice_source",
            native_enum=False,
            length=20,
            create_constraint=True,
        ),
        default=PracticeSource.PRACTICE,
        nullable=False,
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    user_answer: Mapped[str | None] = mapped_column(Text)
    # 离线补齐幂等键（F-39/T9.2）：同一作答重放不重复计数
    client_event_id: Mapped[str | None] = mapped_column(String(64))
