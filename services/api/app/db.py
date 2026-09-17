"""数据库基础设施：声明基类、命名约定与引擎工厂。"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 统一约束命名，保证 Alembic autogenerate 迁移稳定
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """ORM 声明基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    """当前 UTC 时间（带时区）。"""
    return datetime.now(UTC)


class TimestampMixin:
    """创建/更新时间戳（带时区；客户端与服务端双保险）。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )


def create_engine(
    database_url: str,
    *,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    pool_timeout: float | None = None,
    pool_recycle: int | None = None,
    pool_pre_ping: bool | None = None,
) -> AsyncEngine:
    """创建异步引擎（预检连接 + 可配置池；默认取 settings）。"""
    from app.config import settings

    return create_async_engine(
        database_url,
        pool_pre_ping=(
            pool_pre_ping if pool_pre_ping is not None else settings.db_pool_pre_ping
        ),
        pool_size=pool_size if pool_size is not None else settings.db_pool_size,
        max_overflow=max_overflow if max_overflow is not None else settings.db_max_overflow,
        pool_timeout=(
            pool_timeout if pool_timeout is not None else settings.db_pool_timeout_seconds
        ),
        pool_recycle=(
            pool_recycle if pool_recycle is not None else settings.db_pool_recycle_seconds
        ),
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """创建会话工厂。"""
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """会话上下文（供脚本使用）。"""
    async with sessionmaker() as session:
        yield session


def jsonable(value: Any) -> Any:
    """将 datetime/UUID 等转换为可 JSON 序列化结构（递归）。"""
    import uuid as _uuid
    from datetime import date as _date

    if isinstance(value, _uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, _date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value
