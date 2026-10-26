"""防沉迷设置行的并发安全初始化。

页面首屏会同时请求 guardian/status 与其它接口，两个请求可能同时发现
「该孩子还没有 parent_controls 行」并各自 INSERT；child_id 唯一约束会让
其中一个请求 500（浏览器侧表现为 Failed to fetch，整页数据加载失败）。

这里用一条常量 SQL（命名绑定参数）做幂等插入：ON CONFLICT DO NOTHING。
单独成模块是为了让这段并发处理有唯一入口、也能被单测直接覆盖。
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_controls_row(session: AsyncSession, *, child_id: uuid.UUID) -> None:
    """确保该孩子存在防沉迷设置行；已存在时无操作（并发安全）。"""
    await session.execute(
        text(
            "INSERT INTO parent_controls"
            " (id, child_id, is_enabled, daily_limit_minutes, rest_after_minutes)"
            " VALUES (:id, :child_id, true, 60, 40)"
            " ON CONFLICT (child_id) DO NOTHING"
        ),
        {"id": uuid.uuid4(), "child_id": child_id},
    )
    await session.flush()


__all__ = ["ensure_controls_row"]
