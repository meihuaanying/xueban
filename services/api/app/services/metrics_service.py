"""学情数据看板指标（F-46）：全部口径用 SQL 聚合实现，可溯源、可单测。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import (
    AnalyticsEvent,
    MasteryRecord,
    PlanTask,
    PracticeRecord,
    Subscription,
    SubscriptionPlan,
    TaskStatus,
    User,
)

RETENTION_WINDOW_DAYS = 7
RENEWAL_PLANS = (SubscriptionPlan.TRIAL, SubscriptionPlan.PRO)


async def users_total(session: AsyncSession) -> int:
    """用户总数。"""
    return int(await session.scalar(select(func.count()).select_from(User)) or 0)


async def users_active_7d(session: AsyncSession) -> int:
    """近 7 天有任意埋点活动的用户数。"""
    since = utcnow() - timedelta(days=RETENTION_WINDOW_DAYS)
    return int(
        await session.scalar(
            select(func.count(func.distinct(AnalyticsEvent.user_id))).where(
                AnalyticsEvent.occurred_at >= since
            )
        )
        or 0
    )


async def _activity_days(session: AsyncSession, *, user_ids: list[Any]) -> dict[Any, set[date]]:
    """每个用户在窗口内的活跃日期集合（埋点 occurred_at 的日期）。"""
    if not user_ids:
        return {}
    rows = (
        await session.execute(
            select(
                AnalyticsEvent.user_id,
                func.date(AnalyticsEvent.occurred_at).label("day"),
            )
            .where(AnalyticsEvent.user_id.in_(user_ids))
            .group_by(AnalyticsEvent.user_id, func.date(AnalyticsEvent.occurred_at))
        )
    ).all()
    result: dict[Any, set[date]] = {}
    for user_id, day in rows:
        value = day if isinstance(day, date) else datetime.fromisoformat(str(day)).date()
        result.setdefault(user_id, set()).add(value)
    return result


async def retention(session: AsyncSession, *, days: int) -> float:
    """次日（D1）/ 七日（D7）留存：注册后第 N 天仍有活动的比例。

    口径：取注册时间在 [now-days-7, now-days] 的用户为队列；若某用户在注册日 +days 之后
    （含当日）仍有埋点活动则计入留存。窗口内无队列用户时返回 0。
    """
    now = utcnow()
    cohort_start = now - timedelta(days=days + RETENTION_WINDOW_DAYS)
    cohort_end = now - timedelta(days=days)
    cohort = (
        await session.execute(
            select(User.id, User.created_at).where(
                User.created_at >= cohort_start, User.created_at <= cohort_end
            )
        )
    ).all()
    if not cohort:
        return 0.0
    activity = await _activity_days(session, user_ids=[row[0] for row in cohort])
    retained = 0
    for user_id, created_at in cohort:
        registered = created_at.date()
        target = registered + timedelta(days=days)
        days_active = activity.get(user_id, set())
        if any(day >= target for day in days_active):
            retained += 1
    return round(retained / len(cohort), 4)


async def task_completion_rate_7d(session: AsyncSession) -> float:
    """近 7 天任务卡完成率（完成数 / 生成数）。"""
    since = utcnow() - timedelta(days=RETENTION_WINDOW_DAYS)
    row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(PlanTask.status == TaskStatus.DONE).label("done"),
            ).where(PlanTask.created_at >= since)
        )
    ).one()
    total = int(row[0] or 0)
    return round(int(row[1] or 0) / total, 4) if total else 0.0


async def renewal_rate(session: AsyncSession) -> float:
    """续费率：试用/专业套餐中开启自动续费的比例。"""
    row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(Subscription.auto_renew.is_(True)).label("renewing"),
            ).where(Subscription.plan.in_(RENEWAL_PLANS))
        )
    ).one()
    total = int(row[0] or 0)
    return round(int(row[1] or 0) / total, 4) if total else 0.0


async def mastery_improvement(session: AsyncSession) -> float:
    """掌握度提升：近 7 天有更新的知识点平均掌握度 − 更早更新的平均掌握度。

    口径说明：MasteryRecord 每次作答会更新 updated_at，因此“近 7 天平均值”代表
    本周活跃知识点的当前水平，“更早平均值”代表上周水平，差值即近似提升幅度。
    """
    since = utcnow() - timedelta(days=RETENTION_WINDOW_DAYS)
    recent = await session.scalar(
        select(func.avg(MasteryRecord.mastery)).where(MasteryRecord.updated_at >= since)
    )
    older = await session.scalar(
        select(func.avg(MasteryRecord.mastery)).where(MasteryRecord.updated_at < since)
    )
    if recent is None and older is None:
        return 0.0
    return round(float(recent or 0.0) - float(older or 0.0), 4)


async def practice_accuracy(session: AsyncSession, *, since: datetime | None = None) -> float:
    """练习正确率（辅助指标）。"""
    query = select(
        func.count().label("total"),
        func.count().filter(PracticeRecord.is_correct.is_(True)).label("correct"),
    )
    if since is not None:
        query = query.where(PracticeRecord.created_at >= since)
    row = (await session.execute(query)).one()
    total = int(row[0] or 0)
    return round(int(row[1] or 0) / total, 4) if total else 0.0


async def overview(session: AsyncSession) -> dict[str, Any]:
    """汇总看板（F-46）。"""
    return {
        "users_total": await users_total(session),
        "users_active_7d": await users_active_7d(session),
        "retention_d1": await retention(session, days=1),
        "retention_d7": await retention(session, days=7),
        "task_completion_rate_7d": await task_completion_rate_7d(session),
        "renewal_rate": await renewal_rate(session),
        "mastery_improvement": await mastery_improvement(session),
        "generated_at": utcnow(),
    }


__all__ = [
    "mastery_improvement",
    "overview",
    "practice_accuracy",
    "renewal_rate",
    "retention",
    "task_completion_rate_7d",
    "users_active_7d",
    "users_total",
]
