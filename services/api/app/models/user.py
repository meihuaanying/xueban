"""用户与账号安全相关模型。"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class UserRole(enum.StrEnum):
    """账号角色。"""

    STUDENT = "student"
    PARENT = "parent"
    ADMIN = "admin"


class User(Base, TimestampMixin):
    """用户账号。"""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(50))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=False, length=20, create_constraint=True),
        default=UserRole.STUDENT,
        nullable=False,
    )
    # K12 学生标记（未成年人保护策略入口）
    is_k12: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 注销时间：注销即匿名化并停用；超过保留期（默认 30 天）由 purge 脚本物理删除
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base, TimestampMixin):
    """刷新令牌（轮换 + 吊销）。"""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SmsCode(Base, TimestampMixin):
    """短信验证码（mock 先行，落库可审计）。"""

    __tablename__ = "sms_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), default="login", nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ParentChild(Base, TimestampMixin):
    """家长-孩子绑定关系。"""

    __tablename__ = "parent_children"
    __table_args__ = (UniqueConstraint("parent_id", "child_id", name="uq_parent_children_pair"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)


class ParentControl(Base, TimestampMixin):
    """家长防沉迷设置（F-40，服务端强制）。"""

    __tablename__ = "parent_controls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    daily_limit_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    allowed_start: Mapped[time | None] = mapped_column(Time)
    allowed_end: Mapped[time | None] = mapped_column(Time)
    rest_after_minutes: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
