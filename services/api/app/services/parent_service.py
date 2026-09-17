"""家长端服务：看板、防沉迷、安全报告、亲子任务、免登录链接（F-40~F-43）。"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, cast

from sqlalchemy import Integer, func, select
from sqlalchemy import cast as sa_cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.errors import AuthError, NotFoundError, PermissionDeniedError
from app.models import (
    AnalyticsEvent,
    ChatMessage,
    ChatSession,
    LearningProfile,
    MasteryRecord,
    MistakeBookEntry,
    ParentChild,
    ParentControl,
    ParentTask,
    PlanTask,
    PracticeRecord,
    ReportShare,
    SafetyEvent,
    TaskStatus,
    User,
    WeeklyReport,
)
from app.services.security import verify_password

DASHBOARD_SHARE_KIND = "parent_dashboard"
DASHBOARD_SHARE_DAYS = 30
USAGE_EVENT_NAME = "study.time"
SAFETY_TRACE_LIMIT = 10


async def get_bound_child(session: AsyncSession, *, parent: User, child_id: uuid.UUID) -> User:
    """校验孩子属于该家长（RBAC），否则 403/404。"""
    result = await session.execute(
        select(User)
        .join(ParentChild, ParentChild.child_id == User.id)
        .where(
            ParentChild.parent_id == parent.id,
            ParentChild.child_id == child_id,
            ParentChild.status == "active",
        )
    )
    child = result.scalar_one_or_none()
    if child is None:
        raise PermissionDeniedError("无权查看该孩子的数据", code="PARENT_CHILD_FORBIDDEN")
    return child


async def get_controls(session: AsyncSession, *, child_id: uuid.UUID) -> ParentControl:
    """读取防沉迷设置（缺失时落库默认值）。"""
    result = await session.execute(select(ParentControl).where(ParentControl.child_id == child_id))
    control = result.scalar_one_or_none()
    if control is None:
        # 显式写入默认值并落库（列默认值由数据库侧生成，未 flush 前读出为 None）
        control = ParentControl(
            child_id=child_id,
            is_enabled=True,
            daily_limit_minutes=60,
            rest_after_minutes=40,
        )
        session.add(control)
        await session.flush()
    return control


async def update_controls(
    session: AsyncSession,
    *,
    parent: User,
    child_id: uuid.UUID,
    parent_password: str,
    is_enabled: bool,
    daily_limit_minutes: int,
    allowed_start: time | None,
    allowed_end: time | None,
    rest_after_minutes: int,
) -> ParentControl:
    """更新防沉迷设置（修改需家长密码，F-40）。"""
    await get_bound_child(session, parent=parent, child_id=child_id)
    if not verify_password(parent_password, parent.password_hash):
        raise AuthError("家长密码不正确", code="PARENT_PASSWORD_INVALID")
    if allowed_start is not None and allowed_end is not None and allowed_start >= allowed_end:
        raise AuthError("允许时段起始时间必须早于结束时间", code="PARENT_CONTROL_TIME_INVALID")

    control = await get_controls(session, child_id=child_id)
    control.updated_by = parent.id
    control.is_enabled = is_enabled
    control.daily_limit_minutes = daily_limit_minutes
    control.allowed_start = allowed_start
    control.allowed_end = allowed_end
    control.rest_after_minutes = rest_after_minutes
    session.add(control)
    await session.flush()
    return control


async def _today_usage_minutes(session: AsyncSession, *, user_id: uuid.UUID, day: date) -> int:
    """统计当日学习时长（来源：study.time 埋点，seconds 求和）。"""
    start = datetime.combine(day, time.min, tzinfo=utcnow().tzinfo)
    seconds = await session.scalar(
        select(
            func.coalesce(func.sum(sa_cast(AnalyticsEvent.payload["seconds"].astext, Integer)), 0)
        ).where(
            AnalyticsEvent.user_id == user_id,
            AnalyticsEvent.event_name == USAGE_EVENT_NAME,
            AnalyticsEvent.occurred_at >= start,
        )
    )
    return int(seconds or 0) // 60


@dataclass(slots=True)
class GuardianStatus:
    """学习端防沉迷判定结果。"""

    locked: bool
    reasons: list[str]
    used_minutes: int
    limit_minutes: int | None
    suggest_break: bool
    curfew_active: bool
    available_from: time | None


async def guardian_status(
    session: AsyncSession, *, user: User, now: datetime | None = None
) -> GuardianStatus:
    """服务端判定是否锁屏（F-40：防本地篡改）。"""
    moment = now or utcnow()
    control = await get_controls(session, child_id=user.id)
    if not control.is_enabled:
        return GuardianStatus(False, [], 0, None, False, False, None)

    used = await _today_usage_minutes(session, user_id=user.id, day=moment.date())
    reasons: list[str] = []
    limit = control.daily_limit_minutes
    if limit > 0 and used >= limit:
        reasons.append("daily_limit")

    curfew_active = False
    available_from: time | None = None
    if control.allowed_start is not None and control.allowed_end is not None:
        current = moment.time()
        if not (control.allowed_start <= current < control.allowed_end):
            curfew_active = True
            reasons.append("curfew")
            available_from = control.allowed_start

    suggest_break = (
        control.rest_after_minutes > 0
        and used > 0
        and used % max(control.rest_after_minutes, 1) == 0
    )
    return GuardianStatus(
        locked=bool(reasons),
        reasons=reasons,
        used_minutes=used,
        limit_minutes=limit or None,
        suggest_break=suggest_break,
        curfew_active=curfew_active,
        available_from=available_from,
    )


async def _mastery_summary(session: AsyncSession, *, child_id: uuid.UUID) -> dict[str, Any]:
    """掌握度摘要（红黄绿分布 + 平均）。"""
    rows = (
        (
            await session.execute(
                select(MasteryRecord)
                .where(MasteryRecord.user_id == child_id)
                .order_by(MasteryRecord.mastery)
            )
        )
        .scalars()
        .all()
    )
    red = sum(1 for row in rows if row.mastery < 0.6)
    yellow = sum(1 for row in rows if 0.6 <= row.mastery < 0.8)
    green = sum(1 for row in rows if row.mastery >= 0.8)
    average = round(sum(row.mastery for row in rows) / len(rows), 4) if rows else None
    return {
        "red_count": red,
        "yellow_count": yellow,
        "green_count": green,
        "average_mastery": average,
        "points": [
            {
                "knowledge_point_id": str(row.knowledge_point_id),
                "mastery": round(row.mastery, 4),
                "attempts": row.total_attempts,
            }
            for row in rows[:20]
        ],
    }


async def _streak_days(session: AsyncSession, *, child_id: uuid.UUID) -> int:
    """连续打卡天数（全部任务完成的日子）。"""
    rows = (
        await session.execute(
            select(PlanTask.task_date, func.count().label("total"))
            .add_columns(func.count().filter(PlanTask.status == TaskStatus.DONE).label("done"))
            .where(PlanTask.user_id == child_id)
            .group_by(PlanTask.task_date)
            .order_by(PlanTask.task_date.desc())
        )
    ).all()
    completed = {row[0] for row in rows if row[1] and row[1] == row[2]}
    streak = 0
    cursor = max(completed) if completed else None
    while cursor is not None and cursor in completed:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


async def _weekly_summary(session: AsyncSession, *, child_id: uuid.UUID) -> dict[str, Any] | None:
    """最近一份周报摘要。"""
    report = (
        await session.execute(
            select(WeeklyReport)
            .where(WeeklyReport.user_id == child_id)
            .order_by(WeeklyReport.week_start.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if report is None:
        return None
    return {
        "week_start": report.week_start,
        "week_end": report.week_start + timedelta(days=6),
        "summary": dict(report.payload or {}),
    }


async def build_dashboard(session: AsyncSession, *, child: User) -> dict[str, Any]:
    """构建学情看板数据（F-41）。"""
    now = utcnow()
    since = now - timedelta(days=7)
    practice_7d = await session.scalar(
        select(func.count())
        .select_from(PracticeRecord)
        .where(PracticeRecord.user_id == child.id, PracticeRecord.created_at >= since)
    )
    task_rows = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(PlanTask.status == TaskStatus.DONE).label("done"),
            ).where(PlanTask.user_id == child.id, PlanTask.created_at >= since)
        )
    ).one()
    total_tasks = int(task_rows[0] or 0)
    done_tasks = int(task_rows[1] or 0)
    mistakes_active = await session.scalar(
        select(func.count())
        .select_from(MistakeBookEntry)
        .where(MistakeBookEntry.user_id == child.id, MistakeBookEntry.removed_at.is_(None))
    )
    profile = (
        await session.execute(select(LearningProfile).where(LearningProfile.user_id == child.id))
    ).scalar_one_or_none()
    return {
        "child_id": child.id,
        "child_nickname": child.nickname,
        "mastery": await _mastery_summary(session, child_id=child.id),
        "streak_days": await _streak_days(session, child_id=child.id),
        "practice_7d": int(practice_7d or 0),
        "task_completion_7d": round(done_tasks / total_tasks, 4) if total_tasks else 0.0,
        "mistakes_active": int(mistakes_active or 0),
        "behavior_style": cast(str | None, getattr(profile, "learning_style", None)),
        "weekly": await _weekly_summary(session, child_id=child.id),
        "generated_at": now,
    }


async def create_dashboard_link(
    session: AsyncSession, *, parent: User, child_id: uuid.UUID, days: int = DASHBOARD_SHARE_DAYS
) -> ReportShare:
    """创建免登录看板链接（签名 token，可吊销，F-41）。"""
    child = await get_bound_child(session, parent=parent, child_id=child_id)
    share = ReportShare(
        user_id=parent.id,
        token=secrets.token_urlsafe(24),
        payload={
            "kind": DASHBOARD_SHARE_KIND,
            "child_id": str(child.id),
            "child_nickname": child.nickname,
        },
        expires_at=utcnow() + timedelta(days=days),
    )
    session.add(share)
    await session.flush()
    return share


async def get_shared_dashboard(session: AsyncSession, *, token: str) -> dict[str, Any]:
    """免登录读取看板（校验 token 未吊销/未过期）。"""
    share = (
        await session.execute(select(ReportShare).where(ReportShare.token == token))
    ).scalar_one_or_none()
    if share is None or share.revoked_at is not None:
        raise NotFoundError("分享链接不存在或已吊销", code="PARENT_SHARE_NOT_FOUND")
    if share.expires_at <= utcnow():
        raise NotFoundError("分享链接已过期", code="PARENT_SHARE_EXPIRED")
    payload = dict(share.payload or {})
    if payload.get("kind") != DASHBOARD_SHARE_KIND:
        raise NotFoundError("分享链接类型不匹配", code="PARENT_SHARE_KIND_MISMATCH")
    child = await session.get(User, uuid.UUID(str(payload["child_id"])))
    if child is None:
        raise NotFoundError("孩子账号不存在", code="PARENT_CHILD_NOT_FOUND")
    return await build_dashboard(session, child=child)


async def revoke_dashboard_link(session: AsyncSession, *, parent: User, token: str) -> None:
    """吊销看板链接。"""
    share = (
        await session.execute(select(ReportShare).where(ReportShare.token == token))
    ).scalar_one_or_none()
    if share is None or share.user_id != parent.id:
        raise NotFoundError("分享链接不存在", code="PARENT_SHARE_NOT_FOUND")
    share.revoked_at = utcnow()
    await session.flush()


async def safety_report(
    session: AsyncSession,
    *,
    parent: User,
    child_id: uuid.UUID,
    week_start: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """内容安全报告（F-42）：拦截事件 + 对话留痕抽查，按周分页。"""
    child = await get_bound_child(session, parent=parent, child_id=child_id)
    start_day = week_start or (utcnow().date() - timedelta(days=utcnow().weekday()))
    start = datetime.combine(start_day, time.min, tzinfo=utcnow().tzinfo)
    end = start + timedelta(days=7)

    base = select(SafetyEvent).where(
        SafetyEvent.user_id == child.id,
        SafetyEvent.created_at >= start,
        SafetyEvent.created_at < end,
    )
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    blocked = await session.scalar(
        select(func.count()).select_from(base.where(SafetyEvent.action == "blocked").subquery())
    )
    events = (
        (
            await session.execute(
                base.order_by(SafetyEvent.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    trace_base = (
        select(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(
            ChatSession.user_id == child.id,
            ChatMessage.created_at >= start,
            ChatMessage.created_at < end,
        )
    )
    trace_total = await session.scalar(select(func.count()).select_from(trace_base.subquery()))
    traces = (
        (
            await session.execute(
                trace_base.order_by(ChatMessage.created_at.desc()).limit(SAFETY_TRACE_LIMIT)
            )
        )
        .scalars()
        .all()
    )

    return {
        "week_start": start_day,
        "week_end": start_day + timedelta(days=6),
        "blocked_count": int(blocked or 0),
        "total_events": int(total or 0),
        "page": page,
        "page_size": page_size,
        "events": list(events),
        "traces": [
            {
                "id": message.id,
                "role": message.role.value if hasattr(message.role, "value") else str(message.role),
                "hint_level": message.hint_level,
                "excerpt": (message.content or "")[:120],
                "created_at": message.created_at,
            }
            for message in traces
        ],
        "trace_total": int(trace_total or 0),
    }


DEFAULT_TASKS: list[tuple[str, str, str]] = [
    ("听孩子讲一道题", "让孩子选一道今天做过的题，讲给你听，讲完记得鼓励并确认。", "explain"),
    ("一起看本周学习周报", "打开周报，和孩子聊聊本周的进步与下一步计划。", "review"),
]


async def ensure_default_tasks(session: AsyncSession, *, parent: User, child_id: uuid.UUID) -> None:
    """首次查看时为系统布置两条默认亲子任务（幂等）。"""
    existing = await session.scalar(
        select(func.count())
        .select_from(ParentTask)
        .where(ParentTask.parent_id == parent.id, ParentTask.child_id == child_id)
    )
    if existing:
        return
    for title, description, kind in DEFAULT_TASKS:
        session.add(
            ParentTask(
                parent_id=parent.id,
                child_id=child_id,
                title=title,
                description=description,
                kind=kind,
                source="system",
                status="pending",
            )
        )
    await session.flush()


async def list_tasks(
    session: AsyncSession, *, parent: User, child_id: uuid.UUID | None = None
) -> list[ParentTask]:
    """家长查看亲子任务列表。"""
    if child_id is not None:
        await get_bound_child(session, parent=parent, child_id=child_id)
        await ensure_default_tasks(session, parent=parent, child_id=child_id)
    query = select(ParentTask).where(ParentTask.parent_id == parent.id)
    if child_id is not None:
        query = query.where(ParentTask.child_id == child_id)
    result = await session.execute(query.order_by(ParentTask.created_at.desc()))
    return list(result.scalars().all())


async def create_task(
    session: AsyncSession,
    *,
    parent: User,
    child_id: uuid.UUID,
    title: str,
    description: str | None,
    kind: str,
    due_date: date | None,
) -> ParentTask:
    """家长布置亲子任务。"""
    await get_bound_child(session, parent=parent, child_id=child_id)
    task = ParentTask(
        parent_id=parent.id,
        child_id=child_id,
        title=title,
        description=description,
        kind=kind,
        source="parent",
        status="pending",
        due_date=due_date,
    )
    session.add(task)
    await session.flush()
    return task


async def confirm_task(session: AsyncSession, *, parent: User, task_id: uuid.UUID) -> ParentTask:
    """家长确认孩子已完成任务（F-43 闭环）。"""
    task = await session.get(ParentTask, task_id)
    if task is None or task.parent_id != parent.id:
        raise NotFoundError("亲子任务不存在", code="PARENT_TASK_NOT_FOUND")
    if task.status == "pending":
        raise PermissionDeniedError("孩子尚未完成任务，暂不能确认", code="PARENT_TASK_NOT_DONE")
    task.status = "confirmed"
    task.confirmed_at = utcnow()
    await session.flush()
    return task


async def list_child_tasks(session: AsyncSession, *, child: User) -> list[ParentTask]:
    """孩子查看自己的亲子任务。"""
    result = await session.execute(
        select(ParentTask)
        .where(ParentTask.child_id == child.id)
        .order_by(ParentTask.created_at.desc())
    )
    return list(result.scalars().all())


async def complete_child_task(
    session: AsyncSession, *, child: User, task_id: uuid.UUID
) -> ParentTask:
    """孩子标记完成亲子任务。"""
    task = await session.get(ParentTask, task_id)
    if task is None or task.child_id != child.id:
        raise NotFoundError("亲子任务不存在", code="PARENT_TASK_NOT_FOUND")
    if task.status == "confirmed":
        return task
    task.status = "child_done"
    task.child_done_at = utcnow()
    await session.flush()
    return task


async def weekly_report(
    session: AsyncSession, *, parent: User, child_id: uuid.UUID
) -> dict[str, Any]:
    """家长端周报（F-31）：本周时长/任务/掌握度 + ≥2 条亲子建议。"""
    child = await get_bound_child(session, parent=parent, child_id=child_id)
    now = utcnow()
    week_start = now.date() - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    start_dt = datetime.combine(week_start, time.min, tzinfo=now.tzinfo)

    week_seconds = await session.scalar(
        select(
            func.coalesce(func.sum(sa_cast(AnalyticsEvent.payload["seconds"].astext, Integer)), 0)
        ).where(
            AnalyticsEvent.user_id == child.id,
            AnalyticsEvent.event_name == USAGE_EVENT_NAME,
            AnalyticsEvent.occurred_at >= start_dt,
        )
    )
    task_row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(PlanTask.status == TaskStatus.DONE).label("done"),
            ).where(PlanTask.user_id == child.id, PlanTask.task_date >= week_start)
        )
    ).one()
    tasks_total = int(task_row[0] or 0)
    tasks_done = int(task_row[1] or 0)

    mastery = await _mastery_summary(session, child_id=child.id)
    weak_rows = (
        (
            await session.execute(
                select(MasteryRecord)
                .where(MasteryRecord.user_id == child.id, MasteryRecord.mastery < 0.7)
                .order_by(MasteryRecord.mastery)
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    weak_points = [str(row.knowledge_point_id) for row in weak_rows]

    suggestions: list[str] = []
    if tasks_total == 0 or tasks_done / max(tasks_total, 1) < 0.7:
        suggestions.append(
            "本周任务完成率偏低：和孩子约定固定的 20 分钟学习时段，先完成最小任务卡。"
        )
    else:
        suggestions.append(
            "本周任务完成度不错：可以请孩子给你讲一道最有成就感的题，巩固表达与理解。"
        )
    if weak_points:
        suggestions.append(
            "有知识点仍低于 70%：周末一起看一次微课，再做 5 道同类练习（错题本可一键重练）。"
        )
    else:
        suggestions.append("本周掌握度整体稳定：尝试把目标提高一档（难度 +1），保持最近发展区。")
    suggestions.append("每次学习后用「听孩子讲一道题」亲子任务确认理解，比只看时长的激励更有效。")

    return {
        "child_id": child.id,
        "week_start": str(week_start),
        "week_end": str(week_end),
        "study_minutes": int(week_seconds or 0) // 60,
        "tasks_done": tasks_done,
        "tasks_total": tasks_total,
        "mastery_average": mastery.get("average_mastery"),
        "weak_points": weak_points,
        "suggestions": suggestions[:4],
    }
