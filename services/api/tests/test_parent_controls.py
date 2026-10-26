"""防沉迷设置行的并发安全初始化（回归：child_id 唯一约束不再 500）。"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ParentControl, User
from app.services.parent_controls import ensure_controls_row
from app.services.security import hash_password
from tests.conftest import next_phone
from tests.helpers import TEST_PASSWORD


async def _create_child(sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with sessionmaker() as session:
        user = User(phone=next_phone(), password_hash=hash_password(TEST_PASSWORD))
        session.add(user)
        await session.commit()
        return user.id


async def _count_rows(
    sessionmaker: async_sessionmaker[AsyncSession], child_id: uuid.UUID
) -> int:
    async with sessionmaker() as session:
        total = await session.scalar(
            select(func.count())
            .select_from(ParentControl)
            .where(ParentControl.child_id == child_id)
        )
        return int(total or 0)


async def test_ensure_controls_row_is_idempotent(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    child_id = await _create_child(sessionmaker)
    async with sessionmaker() as session:
        await ensure_controls_row(session, child_id=child_id)
        await session.commit()
    async with sessionmaker() as session:
        await ensure_controls_row(session, child_id=child_id)
        await session.commit()
    assert await _count_rows(sessionmaker, child_id) == 1


async def test_ensure_controls_row_handles_concurrent_first_visit(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """多个请求同时首访：ON CONFLICT DO NOTHING 保证不抛唯一约束错误。"""

    child_id = await _create_child(sessionmaker)

    async def visit() -> None:
        async with sessionmaker() as session:
            await ensure_controls_row(session, child_id=child_id)
            await session.commit()

    await asyncio.gather(visit(), visit(), visit())

    assert await _count_rows(sessionmaker, child_id) == 1
