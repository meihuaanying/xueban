"""复盘服务（F-27/F-29/F-30）：周报（幂等+分享）、打卡日历、考前冲刺包。"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.errors import AppError, NotFoundError
from app.models import (
    KnowledgePoint,
    MistakeBookEntry,
    Plan,
    PlanKind,
    PlanTask,
    PracticeRecord,
    Question,
    QuestionKnowledgePoint,
    ReportShare,
    TaskStatus,
    User,
    WeeklyReport,
)
from app.services import mastery_service
from app.services.planner_service import compute_streak

SHARE_TTL_DAYS = 30
SPRINT_MISTAKE_LIMIT = 5
SPRINT_KP_LIMIT = 5
SPRINT_PAPER_COUNT = 10
WEEKLY_ACTIVE_DAYS = 14


def week_start_of(day: date) -> date:
    """返回所在周的周一。"""
    return day - timedelta(days=day.weekday())


@dataclass(slots=True)
class CalendarDay:
    """日历中的一天。"""

    day: date
    practice_count: int
    correct_count: int
    tasks_total: int
    tasks_done: int

    @property
    def studied(self) -> bool:
        return self.practice_count > 0 or self.tasks_done > 0


@dataclass(slots=True)
class CalendarStats:
    """学习日历统计。"""

    year: int
    month: int
    streak_days: int
    max_practice: int
    days: list[CalendarDay]


async def _practice_stats(
    session: AsyncSession, *, user_id: uuid.UUID, start: datetime, end: datetime
) -> dict[str, float]:
    rows = (
        await session.execute(
            select(PracticeRecord.is_correct).where(
                PracticeRecord.user_id == user_id,
                PracticeRecord.created_at >= start,
                PracticeRecord.created_at < end,
            )
        )
    ).scalars()
    results = [bool(item) for item in rows]
    return {
        "total": len(results),
        "correct": sum(1 for item in results if item),
        "accuracy": round(sum(1 for item in results if item) / len(results) * 100, 1)
        if results
        else 0.0,
    }


async def _task_stats(
    session: AsyncSession, *, user_id: uuid.UUID, start: date, end: date
) -> dict[str, int]:
    total = await session.scalar(
        select(func.count())
        .select_from(PlanTask)
        .where(PlanTask.user_id == user_id, PlanTask.task_date >= start, PlanTask.task_date <= end)
    )
    done = await session.scalar(
        select(func.count())
        .select_from(PlanTask)
        .where(
            PlanTask.user_id == user_id,
            PlanTask.task_date >= start,
            PlanTask.task_date <= end,
            PlanTask.status == TaskStatus.DONE,
        )
    )
    return {"total": int(total or 0), "done": int(done or 0)}


async def _top_mistake_knowledge_points(
    session: AsyncSession, *, user_id: uuid.UUID, start: datetime, end: datetime, limit: int = 3
) -> list[dict[str, object]]:
    rows = (
        await session.execute(
            select(KnowledgePoint.name, func.count())
            .join(
                QuestionKnowledgePoint,
                QuestionKnowledgePoint.knowledge_point_id == KnowledgePoint.id,
            )
            .join(
                MistakeBookEntry,
                MistakeBookEntry.question_id == QuestionKnowledgePoint.question_id,
            )
            .where(
                MistakeBookEntry.user_id == user_id,
                MistakeBookEntry.created_at >= start,
                MistakeBookEntry.created_at < end,
            )
            .group_by(KnowledgePoint.name)
            .order_by(func.count().desc())
            .limit(limit)
        )
    ).all()
    return [{"name": row[0], "count": int(row[1])} for row in rows]


async def build_weekly_report(
    session: AsyncSession, *, user_id: uuid.UUID, week_start: date
) -> dict[str, object]:
    """生成周报内容（掌握度曲线 + 错题 TOP + 下周建议）。"""
    week_end = week_start + timedelta(days=6)
    start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=utcnow().tzinfo)
    end_dt = start_dt + timedelta(days=7)

    practice = await _practice_stats(session, user_id=user_id, start=start_dt, end=end_dt)
    tasks = await _task_stats(session, user_id=user_id, start=week_start, end=week_end)
    top_mistakes = await _top_mistake_knowledge_points(
        session, user_id=user_id, start=start_dt, end=end_dt
    )
    mistakes_new = await session.scalar(
        select(func.count())
        .select_from(MistakeBookEntry)
        .where(
            MistakeBookEntry.user_id == user_id,
            MistakeBookEntry.created_at >= start_dt,
            MistakeBookEntry.created_at < end_dt,
        )
    )
    points = await mastery_service.get_mastery_overview(session, user_id=user_id)
    average = mastery_service.mastery_average(points)
    levels = {"red": 0, "yellow": 0, "green": 0}
    for point in points:
        levels[point.level] = levels.get(point.level, 0) + 1
    weakest: list[dict[str, object]] = [
        {"name": point.name, "mastery": point.mastery, "level": point.level}
        for point in points[:3]
    ]

    suggestions: list[str] = []
    if weakest:
        weakest_names = "、".join(str(item["name"]) for item in weakest)
        suggestions.append(f"下周优先复习：{weakest_names}")
    if practice["accuracy"] < 60 and practice["total"] > 0:
        suggestions.append("练习正确率偏低，建议先看「守护型讲解」再做同类题。")
    if tasks["total"] > tasks["done"]:
        suggestions.append("有未完成的每日任务，建议把任务拆小、固定时段完成。")
    if not suggestions:
        suggestions.append("保持当前节奏，每天练习 20~30 分钟即可。")

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "practice": practice,
        "tasks": tasks,
        "mistakes_new": int(mistakes_new or 0),
        "top_mistakes": top_mistakes,
        "mastery": {
            "average": average,
            "red_count": levels["red"],
            "yellow_count": levels["yellow"],
            "green_count": levels["green"],
            "weakest": weakest,
        },
        "suggestions": suggestions,
        "generated_at": utcnow().isoformat(),
    }


async def get_or_create_weekly_report(
    session: AsyncSession, *, user: User, week_start: date | None = None
) -> WeeklyReport:
    """按周幂等获取/生成周报。"""
    start = week_start or week_start_of(utcnow().date())
    existing = (
        await session.execute(
            select(WeeklyReport).where(
                WeeklyReport.user_id == user.id, WeeklyReport.week_start == start
            )
        )
    ).scalar_one_or_none()
    payload = await build_weekly_report(session, user_id=user.id, week_start=start)
    if existing is None:
        existing = WeeklyReport(user_id=user.id, week_start=start, payload=payload)
        session.add(existing)
    else:
        existing.payload = payload
    await session.flush()
    return existing


async def create_share(
    session: AsyncSession, *, user: User, week_start: date | None = None
) -> ReportShare:
    """生成免登录只读分享链接（30 天有效，可吊销）。"""
    report = await get_or_create_weekly_report(session, user=user, week_start=week_start)
    share = ReportShare(
        user_id=user.id,
        report_id=report.id,
        token=secrets.token_urlsafe(24),
        payload=dict(report.payload),
        expires_at=utcnow() + timedelta(days=SHARE_TTL_DAYS),
    )
    session.add(share)
    await session.flush()
    return share


async def revoke_share(session: AsyncSession, *, user: User, token: str) -> None:
    """吊销分享链接。"""
    share = (
        await session.execute(select(ReportShare).where(ReportShare.token == token))
    ).scalar_one_or_none()
    if share is None or share.user_id != user.id:
        raise NotFoundError("分享链接不存在", code="SHARE_NOT_FOUND")
    share.revoked_at = utcnow()
    await session.flush()


async def get_shared_report(session: AsyncSession, *, token: str) -> dict[str, object]:
    """免登录读取分享报告（已吊销/过期返回 404）。"""
    share = (
        await session.execute(select(ReportShare).where(ReportShare.token == token))
    ).scalar_one_or_none()
    if share is None or share.revoked_at is not None:
        raise NotFoundError("分享链接不存在或已失效", code="SHARE_NOT_FOUND")
    if share.expires_at <= utcnow():
        raise AppError("分享链接已过期", code="SHARE_EXPIRED", status_code=410)
    return dict(share.payload)


async def calendar_stats(
    session: AsyncSession, *, user_id: uuid.UUID, year: int, month: int
) -> CalendarStats:
    """学习日历（打卡热力图 + 连续天数，不做排名）。"""
    if not 1 <= month <= 12:
        raise AppError("月份不合法", code="CALENDAR_INVALID_MONTH", status_code=400)
    first_day = date(year, month, 1)
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)

    practice_rows = (
        await session.execute(
            select(
                func.date(PracticeRecord.created_at).label("day"),
                func.count(),
                func.count().filter(PracticeRecord.is_correct.is_(True)),
            )
            .where(
                PracticeRecord.user_id == user_id,
                func.date(PracticeRecord.created_at) >= first_day,
                func.date(PracticeRecord.created_at) <= last_day,
            )
            .group_by(func.date(PracticeRecord.created_at))
        )
    ).all()
    practice_map = {
        _as_date(row[0]): (int(row[1]), int(row[2])) for row in practice_rows
    }

    task_rows = (
        await session.execute(
            select(
                PlanTask.task_date,
                func.count(),
                func.count().filter(PlanTask.status == TaskStatus.DONE),
            )
            .where(
                PlanTask.user_id == user_id,
                PlanTask.task_date >= first_day,
                PlanTask.task_date <= last_day,
            )
            .group_by(PlanTask.task_date)
        )
    ).all()
    task_map = {row[0]: (int(row[1]), int(row[2])) for row in task_rows}

    all_done_dates = {
        day for day, (total, done) in task_map.items() if total > 0 and total == done
    }
    days: list[CalendarDay] = []
    max_practice = 0
    cursor = first_day
    while cursor <= last_day:
        practice_count, correct_count = practice_map.get(cursor, (0, 0))
        tasks_total, tasks_done = task_map.get(cursor, (0, 0))
        max_practice = max(max_practice, practice_count)
        days.append(
            CalendarDay(
                day=cursor,
                practice_count=practice_count,
                correct_count=correct_count,
                tasks_total=tasks_total,
                tasks_done=tasks_done,
            )
        )
        cursor += timedelta(days=1)

    return CalendarStats(
        year=year,
        month=month,
        streak_days=compute_streak(all_done_dates, today=utcnow().date()),
        max_practice=max_practice,
        days=days,
    )


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@dataclass(slots=True)
class SprintPackage:
    """考前冲刺包。"""

    exam_date: date
    remaining_days: int
    high_freq_mistakes: list[dict[str, Any]]
    unmastered_knowledge_points: list[dict[str, Any]]
    predicted_paper: list[dict[str, Any]]
    generated_at: datetime


async def build_sprint_package(session: AsyncSession, *, user: User) -> SprintPackage:
    """考前冲刺包（F-30）：高频错题 + 未掌握考点 + 预测卷。"""
    plan = (
        await session.execute(
            select(Plan)
            .where(
                Plan.user_id == user.id,
                Plan.kind == PlanKind.EXAM_COUNTDOWN,
                Plan.status == "active",
            )
            .order_by(Plan.created_at.desc())
        )
    ).scalars().first()
    if plan is None:
        raise AppError(
            "请先设置考期倒排计划（POST /v1/plan/exam-countdown）",
            code="EXAM_PREP_NO_PLAN",
            status_code=400,
        )
    exam_date_raw = plan.meta.get("exam_date")
    exam_date = (
        date.fromisoformat(str(exam_date_raw)) if exam_date_raw else plan.ends_on
    )
    remaining_days = max(((exam_date or utcnow().date()) - utcnow().date()).days, 0)

    mistake_rows = (
        await session.execute(
            select(Question)
            .join(MistakeBookEntry, MistakeBookEntry.question_id == Question.id)
            .where(
                MistakeBookEntry.user_id == user.id,
                MistakeBookEntry.removed_at.is_(None),
            )
            .order_by(MistakeBookEntry.review_count.desc(), MistakeBookEntry.created_at.asc())
            .limit(SPRINT_MISTAKE_LIMIT)
        )
    ).scalars()
    high_freq_mistakes = [
        {"question_id": str(question.id), "stem": question.stem}
        for question in mistake_rows
    ]

    points = await mastery_service.get_mastery_overview(session, user_id=user.id)
    unmastered = [
        {
            "knowledge_point_id": str(point.knowledge_point_id),
            "name": point.name,
            "mastery": point.mastery,
        }
        for point in points
        if point.mastery < 0.6
    ][:SPRINT_KP_LIMIT]

    from app.services import practice_service

    paper = await practice_service.generate_practice(
        session,
        user=user,
        count=SPRINT_PAPER_COUNT,
        knowledge_point_ids=[
            uuid.UUID(str(item["knowledge_point_id"])) for item in unmastered
        ]
        or None,
    )
    predicted_paper = [
        {"question_id": str(item.question.id), "stem": item.question.stem}
        for item in paper.items
    ]

    return SprintPackage(
        exam_date=exam_date or utcnow().date(),
        remaining_days=remaining_days,
        high_freq_mistakes=high_freq_mistakes,
        unmastered_knowledge_points=unmastered,
        predicted_paper=predicted_paper,
        generated_at=utcnow(),
    )


async def generate_weekly_reports_all(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """为近两周有练习记录的用户生成周报（arq 每周任务）。"""
    cutoff = utcnow() - timedelta(days=WEEKLY_ACTIVE_DAYS)
    async with sessionmaker() as session:
        user_ids = list(
            (
                await session.execute(
                    select(PracticeRecord.user_id)
                    .where(PracticeRecord.created_at >= cutoff)
                    .distinct()
                )
            ).scalars()
        )
    count = 0
    for user_id in user_ids:
        async with sessionmaker() as session:
            user = await session.get(User, user_id)
            if user is None:
                continue
            await get_or_create_weekly_report(session, user=user)
            await session.commit()
        count += 1
    return count


__all__ = [
    "CalendarDay",
    "CalendarStats",
    "SprintPackage",
    "build_sprint_package",
    "build_weekly_report",
    "calendar_stats",
    "create_share",
    "generate_weekly_reports_all",
    "get_or_create_weekly_report",
    "get_shared_report",
    "revoke_share",
    "week_start_of",
]
