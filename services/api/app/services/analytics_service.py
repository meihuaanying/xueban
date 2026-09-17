"""埋点与行为画像服务（F-05 后端 / F-46 数据源）。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import (
    AnalyticsEvent,
    ChatMessage,
    ChatRole,
    ChatSession,
    LearningProfile,
    PracticeRecord,
    User,
)
from app.schemas.analytics import AnalyticsEventItem

BEHAVIOR_WINDOW_DAYS = 30
HINT_HEAVY_RATE = 0.5
HINT_LIGHT_RATE = 0.2
INDEPENDENT_ACCURACY = 0.8
IMPULSIVE_CHANGE_RATIO = 0.3


@dataclass(slots=True)
class BehaviorProfile:
    """学习行为画像（含可解释依据）。"""

    learning_style: str
    evidence: dict[str, object] = field(default_factory=dict)
    independent_score: float | None = None
    assisted_score: float | None = None


async def record_events(
    session: AsyncSession,
    *,
    user: User,
    events: list[AnalyticsEventItem],
    user_agent: str | None = None,
) -> int:
    """批量记录埋点事件（schema 已在入口校验）。"""
    now = utcnow()
    for item in events:
        session.add(
            AnalyticsEvent(
                user_id=user.id,
                event_name=item.name,
                payload=item.payload or {},
                occurred_at=item.occurred_at or now,
                created_at=now,
                user_agent=user_agent,
            )
        )
    await session.flush()
    return len(events)


async def _get_or_create_profile(session: AsyncSession, user_id: uuid.UUID) -> LearningProfile:
    profile = (
        await session.execute(
            select(LearningProfile).where(LearningProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    if profile is None:
        profile = LearningProfile(user_id=user_id)
        session.add(profile)
        await session.flush()
    return profile


async def compute_behavior_profile(session: AsyncSession, *, user: User) -> BehaviorProfile:
    """从埋点、练习与求助记录推断学习风格（可解释）。"""
    cutoff = utcnow() - timedelta(days=BEHAVIOR_WINDOW_DAYS)

    practice_rows = (
        await session.execute(
            select(PracticeRecord.is_correct).where(
                PracticeRecord.user_id == user.id, PracticeRecord.created_at >= cutoff
            )
        )
    ).scalars()
    practice_results = [bool(item) for item in practice_rows]
    practice_count = len(practice_results)
    accuracy = (
        sum(1 for item in practice_results if item) / practice_count if practice_count else 0.0
    )

    answer_change_rows = (
        await session.execute(
            select(func.count())
            .select_from(AnalyticsEvent)
            .where(
                AnalyticsEvent.user_id == user.id,
                AnalyticsEvent.event_name == "answer.change",
                AnalyticsEvent.occurred_at >= cutoff,
            )
        )
    ).scalar()
    answer_changes = int(answer_change_rows or 0)

    duration_rows = (
        await session.execute(
            select(AnalyticsEvent.payload).where(
                AnalyticsEvent.user_id == user.id,
                AnalyticsEvent.event_name == "study.session",
                AnalyticsEvent.occurred_at >= cutoff,
            )
        )
    ).scalars()
    study_seconds = 0
    for payload in duration_rows:
        if isinstance(payload, dict):
            value = payload.get("duration_seconds")
            if isinstance(value, (int, float)):
                study_seconds += int(value)

    hint_count = await session.scalar(
        select(func.count())
        .select_from(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(
            ChatSession.user_id == user.id,
            ChatMessage.role == ChatRole.ASSISTANT,
            ChatMessage.hint_level >= 1,
            ChatMessage.created_at >= cutoff,
        )
    )
    hint_requests = int(hint_count or 0)
    hint_rate = hint_requests / practice_count if practice_count else 0.0

    if practice_count > 0 and answer_changes >= max(3, practice_count * IMPULSIVE_CHANGE_RATIO):
        style = "impulsive"
    elif hint_rate >= HINT_HEAVY_RATE and practice_count > 0:
        style = "guided"
    elif (
        practice_count > 0
        and accuracy >= INDEPENDENT_ACCURACY
        and hint_rate <= HINT_LIGHT_RATE
    ):
        style = "independent"
    else:
        style = "balanced"

    profile = await _get_or_create_profile(session, user.id)
    profile.learning_style = style
    profile.behavior_stats = {
        "practice_count": practice_count,
        "accuracy": round(accuracy, 4),
        "answer_changes": answer_changes,
        "hint_requests": hint_requests,
        "study_seconds": study_seconds,
        "window_days": BEHAVIOR_WINDOW_DAYS,
    }
    await session.flush()

    return BehaviorProfile(
        learning_style=style,
        evidence={
            "practice_count": practice_count,
            "accuracy": round(accuracy, 4),
            "answer_changes": answer_changes,
            "hint_requests": hint_requests,
            "hint_rate": round(hint_rate, 4),
            "study_seconds": study_seconds,
            "window_days": BEHAVIOR_WINDOW_DAYS,
            "rules": [
                "修改频繁（≥30%）→ 冲动型",
                "求助率 ≥50% → 依赖引导型",
                "正确率 ≥80% 且求助率 ≤20% → 独立型",
                "其余 → 均衡型",
            ],
        },
        independent_score=profile.independent_score,
        assisted_score=profile.assisted_score,
    )
