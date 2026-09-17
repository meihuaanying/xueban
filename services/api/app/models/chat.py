"""对话模型：讲解/搜题/陪练等会话与消息。"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
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


class ChatRole(enum.StrEnum):
    """消息角色。"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatScene(enum.StrEnum):
    """会话场景。"""

    TUTOR = "tutor"
    PHOTO_SEARCH = "photo_search"
    COMPANION = "companion"
    ROLEPLAY = "roleplay"
    INTERVIEW = "interview"
    WRITING = "writing"


class ChatSession(Base, TimestampMixin):
    """会话（含守护型讲解的求助层级与无辅助测评锁）。"""

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    scene: Mapped[ChatScene] = mapped_column(
        SAEnum(ChatScene, name="chat_scene", native_enum=False, length=20, create_constraint=True),
        default=ChatScene.TUTOR,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(128))
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL")
    )
    hint_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 无辅助限时测评期间为 True，服务端强制禁止提示类接口（F-28）
    solo_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatMessage(Base, TimestampMixin):
    """消息（记录求助层级与内容安全动作）。"""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[ChatRole] = mapped_column(
        SAEnum(ChatRole, name="chat_role", native_enum=False, length=20, create_constraint=True),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    hint_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    safety_action: Mapped[str | None] = mapped_column(String(20))
    flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
