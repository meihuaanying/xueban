"""BKT 学情画像引擎（F-03）：掌握度计算/更新、滑窗衰减、雷达图数据。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import KnowledgePoint, MasteryRecord


@dataclass(frozen=True, slots=True)
class BktParams:
    """BKT 参数（先验/学习转移/猜对/失误）。"""

    p_init: float = 0.30
    p_transit: float = 0.20
    p_guess: float = 0.25
    p_slip: float = 0.10


DEFAULT_BKT = BktParams()

# 衰减：未练习时掌握度向先验回归（半衰期 30 天）
DECAY_HALF_LIFE_DAYS = 30.0
MIN_MASTERY = 0.0
MAX_MASTERY = 1.0


def bkt_update(prior: float, correct: bool, params: BktParams = DEFAULT_BKT) -> float:
    """单次作答后的掌握度（标准 BKT 后验 + 学习转移）。"""
    prior = min(max(prior, MIN_MASTERY), MAX_MASTERY)
    if correct:
        numerator = prior * (1.0 - params.p_slip)
        denominator = numerator + (1.0 - prior) * params.p_guess
    else:
        numerator = prior * params.p_slip
        denominator = numerator + (1.0 - prior) * (1.0 - params.p_guess)
    posterior = numerator / denominator if denominator > 0 else prior
    updated = posterior + (1.0 - posterior) * params.p_transit
    return min(max(updated, MIN_MASTERY), MAX_MASTERY)


def apply_decay(
    mastery: float,
    last_practiced_at: datetime | None,
    *,
    now: datetime | None = None,
    params: BktParams = DEFAULT_BKT,
) -> float:
    """滑窗衰减：掌握度随时间向先验回归。"""
    if last_practiced_at is None:
        return mastery
    current = now or utcnow()
    days = max((current - last_practiced_at).total_seconds() / 86400.0, 0.0)
    if days <= 0:
        return mastery
    factor: float = 0.5 ** (days / DECAY_HALF_LIFE_DAYS)
    decayed = params.p_init + (mastery - params.p_init) * factor
    return min(max(decayed, MIN_MASTERY), MAX_MASTERY)


def mastery_level(mastery: float) -> str:
    """红黄绿预警分级。"""
    if mastery < 0.6:
        return "red"
    if mastery < 0.8:
        return "yellow"
    return "green"


@dataclass(slots=True)
class MasteryPoint:
    """单个知识点的掌握度视图。"""

    knowledge_point_id: uuid.UUID
    code: str
    name: str
    subject: str
    stage: str
    mastery: float
    level: str
    total_attempts: int
    correct_attempts: int
    last_practiced_at: datetime | None


async def record_practice(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    knowledge_point_id: uuid.UUID,
    correct: bool,
    params: BktParams = DEFAULT_BKT,
    occurred_at: datetime | None = None,
) -> MasteryRecord:
    """记录一次练习并更新掌握度（外键须已存在）。"""
    result = await session.execute(
        select(MasteryRecord).where(
            MasteryRecord.user_id == user_id,
            MasteryRecord.knowledge_point_id == knowledge_point_id,
        )
    )
    record = result.scalar_one_or_none()
    now = occurred_at or utcnow()
    if record is None:
        record = MasteryRecord(
            user_id=user_id,
            knowledge_point_id=knowledge_point_id,
            mastery=params.p_init,
            alpha=params.p_init,
            beta=1.0 - params.p_init,
        )
        session.add(record)
        await session.flush()
    current = apply_decay(record.mastery, record.last_practiced_at, now=now, params=params)
    record.mastery = bkt_update(current, correct, params)
    record.total_attempts += 1
    record.correct_attempts += 1 if correct else 0
    record.last_practiced_at = now
    await session.flush()
    return record


async def get_mastery_overview(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    subject: str | None = None,
    stage: str | None = None,
    knowledge_point_ids: list[uuid.UUID] | None = None,
) -> list[MasteryPoint]:
    """掌握度总览（含衰减），供雷达图/画像使用。"""
    stmt = (
        select(MasteryRecord, KnowledgePoint)
        .join(KnowledgePoint, KnowledgePoint.id == MasteryRecord.knowledge_point_id)
        .where(MasteryRecord.user_id == user_id)
    )
    if subject:
        stmt = stmt.where(KnowledgePoint.subject == subject)
    if stage:
        stmt = stmt.where(KnowledgePoint.stage == stage)
    if knowledge_point_ids:
        stmt = stmt.where(KnowledgePoint.id.in_(knowledge_point_ids))
    rows = (await session.execute(stmt)).all()
    now = utcnow()
    points: list[MasteryPoint] = []
    for record, knowledge_point in rows:
        value = apply_decay(record.mastery, record.last_practiced_at, now=now)
        points.append(
            MasteryPoint(
                knowledge_point_id=knowledge_point.id,
                code=knowledge_point.code,
                name=knowledge_point.name,
                subject=knowledge_point.subject,
                stage=knowledge_point.stage,
                mastery=round(value, 4),
                level=mastery_level(value),
                total_attempts=record.total_attempts,
                correct_attempts=record.correct_attempts,
                last_practiced_at=record.last_practiced_at,
            )
        )
    points.sort(key=lambda item: item.mastery)
    return points


def mastery_average(points: list[MasteryPoint]) -> float | None:
    """平均掌握度（无数据返回 None）。"""
    if not points:
        return None
    return round(sum(point.mastery for point in points) / len(points), 4)
