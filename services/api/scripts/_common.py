"""脚本公共工具：数据库会话。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import create_engine, create_sessionmaker


@asynccontextmanager
async def database_session() -> AsyncIterator[AsyncSession]:
    """脚本用会话（自动创建/释放引擎）。"""
    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    try:
        async with sessionmaker() as session:
            yield session
    finally:
        await engine.dispose()
