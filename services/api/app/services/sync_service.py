"""多端同步（F-39）：轮询状态 + WebSocket 推送版本号。

设计说明：
- 版本号由各业务表最新 updated_at 组合，客户端轮询比对，变化即刷新；
- WebSocket 仅推送「版本 + 关键摘要」，客户端收到后走各自数据层刷新（避免多套同步逻辑）。
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import (
    ChatMessage,
    ChatSession,
    MasteryRecord,
    MistakeBookEntry,
    PlanTask,
    PracticeRecord,
    TaskStatus,
    User,
)

SYNC_TABLES = "mastery,plan_tasks,mistakes,chat,practice"


@dataclass(slots=True)
class SyncSnapshot:
    """同步快照：版本号 + 关键进度摘要。"""

    version: str
    mastery_updated_at: datetime | None
    tasks_updated_at: datetime | None
    mistakes_updated_at: datetime | None
    chat_updated_at: datetime | None
    practice_updated_at: datetime | None
    completed_today: int
    total_today: int
    streak_days: int
    mistakes_active: int
    server_time: datetime


async def _max_updated(
    session: AsyncSession, column: object, user_filter: object
) -> datetime | None:
    """单表最新更新时间。"""
    return await session.scalar(select(func.max(column)).where(user_filter))  # type: ignore[arg-type]


def _build_version(parts: list[datetime | None]) -> str:
    """把多表最新时间拼成稳定短版本号。"""
    raw = "|".join(part.isoformat() if part else "-" for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


async def snapshot(
    session: AsyncSession, *, user: User, now: datetime | None = None
) -> SyncSnapshot:
    """生成同步快照（版本号变化即代表有可同步的新数据）。"""
    mastery_updated = await _max_updated(
        session, MasteryRecord.updated_at, MasteryRecord.user_id == user.id
    )
    tasks_updated = await _max_updated(session, PlanTask.updated_at, PlanTask.user_id == user.id)
    mistakes_updated = await _max_updated(
        session,
        MistakeBookEntry.updated_at,
        MistakeBookEntry.user_id == user.id,
    )
    chat_updated = await session.scalar(
        select(func.max(ChatMessage.created_at))
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(ChatSession.user_id == user.id)
    )
    practice_updated = await _max_updated(
        session, PracticeRecord.updated_at, PracticeRecord.user_id == user.id
    )

    today = (now or utcnow()).date()
    task_row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(PlanTask.status == TaskStatus.DONE).label("done"),
            ).where(PlanTask.user_id == user.id, PlanTask.task_date == today)
        )
    ).one()
    completed_today = int(task_row[1] or 0)
    total_today = int(task_row[0] or 0)

    mistakes_active = await session.scalar(
        select(func.count())
        .select_from(MistakeBookEntry)
        .where(MistakeBookEntry.user_id == user.id, MistakeBookEntry.removed_at.is_(None))
    )

    # 连续打卡：复用简单口径（近 60 天内全部完成的日子数）
    done_days = (
        await session.execute(
            select(PlanTask.task_date, func.count().label("total"))
            .add_columns(func.count().filter(PlanTask.status == TaskStatus.DONE).label("done"))
            .where(PlanTask.user_id == user.id)
            .group_by(PlanTask.task_date)
            .order_by(PlanTask.task_date.desc())
            .limit(60)
        )
    ).all()
    completed_dates = {row[0] for row in done_days if row[1] and row[1] == row[2]}
    streak = 0
    cursor = today
    from datetime import timedelta

    while cursor in completed_dates:
        streak += 1
        cursor = cursor - timedelta(days=1)

    parts = [mastery_updated, tasks_updated, mistakes_updated, chat_updated, practice_updated]
    return SyncSnapshot(
        version=_build_version(parts),
        mastery_updated_at=mastery_updated,
        tasks_updated_at=tasks_updated,
        mistakes_updated_at=mistakes_updated,
        chat_updated_at=chat_updated,
        practice_updated_at=practice_updated,
        completed_today=completed_today,
        total_today=total_today,
        streak_days=streak,
        mistakes_active=int(mistakes_active or 0),
        server_time=now or utcnow(),
    )


def user_channel(user_id: uuid.UUID) -> str:
    """用户同步频道名（WebSocket 广播用）。"""
    return f"sync:{user_id}"


__all__ = ["SYNC_TABLES", "SyncSnapshot", "snapshot", "user_channel"]
