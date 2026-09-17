"""FSRS 间隔重复调度（简化移植）：stability 驱动间隔，评分 1~4。

与 fsrs4anki 的对应关系：保留「初始稳定性 / 学习阶段系数 / 复习阶段系数 / 难度调整」
四个核心机制，间隔取 stability（天）。评分：1=Again（10 分钟后重来）、2=Hard、
3=Good、4=Easy。完整参数化与参考实现逐值对齐留待 T10 评测阶段（见 BLOCKERS B-006）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.errors import AppError, NotFoundError
from app.models import ReviewCard, User

GRADES = (1, 2, 3, 4)
AGAIN_MINUTES = 10
MIN_STABILITY = 0.2
INITIAL_DIFFICULTY = 5.0
STATE_NEW = "new"
STATE_LEARNING = "learning"
STATE_REVIEW = "review"
STATE_RELEARNING = "relearning"

NEW_STABILITY = {1: 0.4, 2: 0.8, 3: 1.6, 4: 3.2}
LEARNING_FACTOR = {1: 0.6, 2: 1.2, 3: 1.8, 4: 2.4}
REVIEW_FACTOR = {2: 1.2, 3: 2.0, 4: 3.0}


@dataclass(slots=True)
class FsrsOutcome:
    """一次评分后的调度结果。"""

    state: str
    stability: float
    difficulty: float
    reps: int
    lapses: int
    interval_days: float
    due_at: datetime


def next_state_and_stability(*, state: str, stability: float, grade: int) -> tuple[str, float]:
    """状态迁移与稳定性更新（纯函数）。"""
    if grade not in GRADES:
        raise AppError("评分必须为 1~4", code="REVIEW_INVALID_GRADE", status_code=400)
    if state == STATE_NEW:
        base = NEW_STABILITY[grade]
        next_state = STATE_REVIEW if grade == 4 else STATE_LEARNING
        return next_state, base
    if state in (STATE_LEARNING, STATE_RELEARNING):
        factor = LEARNING_FACTOR[grade]
        next_state = STATE_REVIEW if grade >= 3 else state
        return next_state, max(MIN_STABILITY, stability * factor)
    if grade == 1:
        return STATE_RELEARNING, max(MIN_STABILITY, stability * 0.5)
    return STATE_REVIEW, stability * REVIEW_FACTOR[grade]


def adjust_difficulty(difficulty: float, grade: int) -> float:
    """难度随评分调整（1~10 截断）。"""
    if grade not in GRADES:
        raise AppError("评分必须为 1~4", code="REVIEW_INVALID_GRADE", status_code=400)
    updated = difficulty + (grade - 3) * 0.5
    return min(max(updated, 1.0), 10.0)


def schedule(
    *,
    state: str,
    stability: float,
    difficulty: float,
    reps: int,
    lapses: int,
    grade: int,
    now: datetime | None = None,
) -> FsrsOutcome:
    """计算下一次复习时间（纯函数）。"""
    current = now or utcnow()
    next_state, next_stability = next_state_and_stability(
        state=state, stability=stability, grade=grade
    )
    next_difficulty = adjust_difficulty(difficulty, grade)
    next_reps = reps + 1
    next_lapses = lapses + (1 if grade == 1 and state == STATE_REVIEW else 0)
    interval_days = round(next_stability, 4)
    if grade == 1:
        due_at = current + timedelta(minutes=AGAIN_MINUTES)
    else:
        due_at = current + timedelta(days=interval_days)
    return FsrsOutcome(
        state=next_state,
        stability=interval_days,
        difficulty=round(next_difficulty, 2),
        reps=next_reps,
        lapses=next_lapses,
        interval_days=interval_days,
        due_at=due_at,
    )


async def _get_or_create_card(
    session: AsyncSession, *, user_id: uuid.UUID, question_id: uuid.UUID
) -> ReviewCard:
    card = (
        await session.execute(
            select(ReviewCard).where(
                ReviewCard.user_id == user_id, ReviewCard.question_id == question_id
            )
        )
    ).scalar_one_or_none()
    if card is None:
        card = ReviewCard(
            user_id=user_id,
            question_id=question_id,
            state=STATE_NEW,
            stability=0.0,
            difficulty=INITIAL_DIFFICULTY,
        )
        session.add(card)
        await session.flush()
    return card


async def apply_grade(
    session: AsyncSession, card: ReviewCard, grade: int, *, now: datetime | None = None
) -> ReviewCard:
    """对卡片应用一次评分。"""
    outcome = schedule(
        state=card.state,
        stability=card.stability,
        difficulty=card.difficulty,
        reps=card.reps,
        lapses=card.lapses,
        grade=grade,
        now=now,
    )
    card.state = outcome.state
    card.stability = outcome.stability
    card.difficulty = outcome.difficulty
    card.reps = outcome.reps
    card.lapses = outcome.lapses
    card.due_at = outcome.due_at
    card.last_review_at = now or utcnow()
    await session.flush()
    return card


async def update_card_for_answer(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    question_id: uuid.UUID,
    correct: bool,
) -> ReviewCard:
    """练习作答联动：答对=Good(3)，答错=Again(1)。"""
    card = await _get_or_create_card(session, user_id=user_id, question_id=question_id)
    return await apply_grade(session, card, 3 if correct else 1)


async def grade_card(
    session: AsyncSession, *, user: User, card_id: uuid.UUID, grade: int
) -> ReviewCard:
    """显式评分（1~4）。"""
    card = await session.get(ReviewCard, card_id)
    if card is None or card.user_id != user.id:
        raise NotFoundError("复习卡片不存在", code="REVIEW_CARD_NOT_FOUND")
    if grade not in GRADES:
        raise AppError("评分必须为 1~4", code="REVIEW_INVALID_GRADE", status_code=400)
    return await apply_grade(session, card, grade)


async def due_cards(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int = 20, now: datetime | None = None
) -> list[ReviewCard]:
    """到期卡片（含逾期）。"""
    current = now or utcnow()
    rows = (
        await session.execute(
            select(ReviewCard)
            .where(
                ReviewCard.user_id == user_id,
                ReviewCard.suspended.is_(False),
                ReviewCard.due_at.is_not(None),
                ReviewCard.due_at <= current,
            )
            .order_by(ReviewCard.due_at)
            .limit(limit)
        )
    ).scalars()
    return list(rows)


async def due_count(
    session: AsyncSession, *, user_id: uuid.UUID, now: datetime | None = None
) -> int:
    """到期卡片数量。"""
    from sqlalchemy import func

    current = now or utcnow()
    count = await session.scalar(
        select(func.count())
        .select_from(ReviewCard)
        .where(
            ReviewCard.user_id == user_id,
            ReviewCard.suspended.is_(False),
            ReviewCard.due_at.is_not(None),
            ReviewCard.due_at <= current,
        )
    )
    return int(count or 0)
