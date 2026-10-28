"""错题与复习卡的学科/学段范围（2026-10-28）。

错题本与 FSRS 复习卡原本只按用户取全量，高中生复习时会混入其它八科和
初小学段的错题。这里集中做范围收窄：所有用户输入都经 `sa.bindparam`
绑定，不参与 SQL 字符串构造（与 grade_scope 同一口径）。
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import MistakeBookEntry, Question, ReviewCard, User
from app.services.mistake_book_service import MistakeEntryView


async def list_mistakes_scoped(
    session: AsyncSession,
    *,
    user: User,
    state: str | None = None,
    error_reason: str | None = None,
    limit: int = 50,
    subject: str | None = None,
    stage: str | None = None,
) -> tuple[list[MistakeEntryView], list[tuple[str, int]]]:
    """错题列表 + 错因计数，按 subject/stage 收窄。"""
    params: dict[str, object] = {
        "scope_subject": subject,
        "scope_stage": stage,
        "scope_state": state,
        "scope_reason": error_reason,
    }
    stmt = (
        select(MistakeBookEntry, Question)
        .join(Question, Question.id == MistakeBookEntry.question_id)
        .where(
            MistakeBookEntry.user_id == user.id,
            MistakeBookEntry.removed_at.is_(None),
        )
    )
    if subject:
        stmt = stmt.where(Question.subject == sa.bindparam("scope_subject"))
    if stage:
        stmt = stmt.where(Question.stage == sa.bindparam("scope_stage"))
    if state:
        stmt = stmt.where(MistakeBookEntry.state == sa.bindparam("scope_state"))
    if error_reason:
        stmt = stmt.where(MistakeBookEntry.error_reason == sa.bindparam("scope_reason"))
    rows = (
        await session.execute(
            stmt.order_by(MistakeBookEntry.created_at.desc()).limit(limit), params
        )
    ).all()
    entries = [MistakeEntryView(entry=row[0], question=row[1]) for row in rows]

    summary_stmt = (
        select(MistakeBookEntry.error_reason, func.count())
        .join(Question, Question.id == MistakeBookEntry.question_id)
        .where(
            MistakeBookEntry.user_id == user.id,
            MistakeBookEntry.removed_at.is_(None),
        )
    )
    if subject:
        summary_stmt = summary_stmt.where(Question.subject == sa.bindparam("scope_subject"))
    if stage:
        summary_stmt = summary_stmt.where(Question.stage == sa.bindparam("scope_stage"))
    reason_rows = (
        await session.execute(
            summary_stmt.group_by(MistakeBookEntry.error_reason), params
        )
    ).all()
    summary = [
        (str(row[0]) if row[0] else "unattributed", int(row[1])) for row in reason_rows
    ]
    return entries, summary


async def repractice_questions_scoped(
    session: AsyncSession,
    *,
    user: User,
    count: int = 5,
    error_reason: str | None = None,
    subject: str | None = None,
    stage: str | None = None,
) -> list[Question]:
    """一键重练题目，按 subject/stage 收窄。"""
    params: dict[str, object] = {
        "scope_subject": subject,
        "scope_stage": stage,
        "scope_reason": error_reason,
    }
    stmt = (
        select(Question)
        .join(MistakeBookEntry, MistakeBookEntry.question_id == Question.id)
        .where(
            MistakeBookEntry.user_id == user.id,
            MistakeBookEntry.removed_at.is_(None),
        )
    )
    if subject:
        stmt = stmt.where(Question.subject == sa.bindparam("scope_subject"))
    if stage:
        stmt = stmt.where(Question.stage == sa.bindparam("scope_stage"))
    if error_reason:
        stmt = stmt.where(MistakeBookEntry.error_reason == sa.bindparam("scope_reason"))
    stmt = stmt.order_by(
        MistakeBookEntry.review_count, MistakeBookEntry.created_at
    ).limit(count)
    return list((await session.execute(stmt, params)).scalars().all())


def _due_conditions(
    *, user_id: uuid.UUID, now: datetime, subject: str | None, stage: str | None
) -> tuple[list[ColumnElement[bool]], dict[str, object]]:
    conditions: list[ColumnElement[bool]] = [
        ReviewCard.user_id == user_id,
        ReviewCard.suspended.is_(False),
        ReviewCard.due_at.is_not(None),
        ReviewCard.due_at <= now,
    ]
    params: dict[str, object] = {"scope_subject": subject, "scope_stage": stage}
    if subject:
        conditions.append(Question.subject == sa.bindparam("scope_subject"))
    if stage:
        conditions.append(Question.stage == sa.bindparam("scope_stage"))
    return conditions, params


async def due_cards_scoped(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int = 20,
    subject: str | None = None,
    stage: str | None = None,
    now: datetime | None = None,
) -> list[ReviewCard]:
    """到期复习卡，按 subject/stage 收窄。"""
    current = now or utcnow()
    conditions, params = _due_conditions(
        user_id=user_id, now=current, subject=subject, stage=stage
    )
    stmt = (
        select(ReviewCard)
        .join(Question, Question.id == ReviewCard.question_id)
        .where(*conditions)
        .order_by(ReviewCard.due_at)
        .limit(limit)
    )
    return list((await session.execute(stmt, params)).scalars().all())


async def due_count_scoped(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    subject: str | None = None,
    stage: str | None = None,
    now: datetime | None = None,
) -> int:
    """到期复习卡数量，按 subject/stage 收窄。"""
    current = now or utcnow()
    conditions, params = _due_conditions(
        user_id=user_id, now=current, subject=subject, stage=stage
    )
    stmt = (
        select(func.count())
        .select_from(ReviewCard)
        .join(Question, Question.id == ReviewCard.question_id)
        .where(*conditions)
    )
    return int((await session.scalar(stmt, params)) or 0)
