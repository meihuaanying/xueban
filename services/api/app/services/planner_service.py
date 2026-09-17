"""规划引擎（F-06~F-10 的规划部分）：学习路径、每日任务、考期倒排、前置回溯、连续打卡。

路径生成遵循「先补前置 → 再学当前 → 后拔高」，依赖知识图谱的拓扑序；重排由 arq 定时触发
（见 app/worker.py），也可由用户手动触发（POST /v1/plan/path/regenerate）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.errors import AppError, NotFoundError
from app.models import (
    Exam,
    ExamAnswer,
    KnowledgeEdge,
    KnowledgePoint,
    MasteryRecord,
    Plan,
    PlanKind,
    PlanTask,
    QuestionKnowledgePoint,
    ReviewCard,
    TaskStatus,
    TaskType,
    User,
)
from app.services.mastery_service import BktParams, MasteryPoint

MASTERY_THRESHOLD = 0.6
ADVANCED_CEILING = 0.8
PATH_LIMIT = 10
DAILY_TASK_TARGET = 4
COUNTDOWN_MIN_DAYS = 7
COMPRESSION_LAG = 0.2


@dataclass(frozen=True, slots=True)
class PathPoint:
    """路径中的知识点。"""

    id: uuid.UUID
    name: str
    mastery: float


@dataclass(frozen=True, slots=True)
class PathPhase:
    """路径阶段。"""

    name: str
    title: str
    knowledge_points: list[PathPoint]


def _dedupe(points: list[PathPoint]) -> list[PathPoint]:
    """按 id 去重并保持顺序。"""
    seen: set[uuid.UUID] = set()
    result: list[PathPoint] = []
    for point in points:
        if point.id in seen:
            continue
        seen.add(point.id)
        result.append(point)
    return result


def build_learning_path(
    *,
    weak_points: list[PathPoint],
    prerequisites: dict[uuid.UUID, list[PathPoint]],
    strong_points: list[PathPoint],
    mastery_threshold: float = MASTERY_THRESHOLD,
) -> list[PathPhase]:
    """生成三阶段路径（纯函数；前置阶段永远排在前）。"""
    foundation: list[PathPoint] = []
    for weak in weak_points:
        foundation.extend(
            point
            for point in prerequisites.get(weak.id, [])
            if point.mastery < mastery_threshold
        )
    foundation = _dedupe(foundation)
    current = _dedupe([point for point in weak_points if point.mastery < mastery_threshold])
    taken = {point.id for point in foundation} | {point.id for point in current}
    advanced = _dedupe(
        [
            point
            for point in strong_points
            if mastery_threshold <= point.mastery < ADVANCED_CEILING and point.id not in taken
        ]
    )

    phases: list[PathPhase] = []
    if foundation:
        phases.append(PathPhase("foundation", "先补地基", foundation))
    if current:
        phases.append(PathPhase("current", "当前重点", current))
    if advanced:
        phases.append(PathPhase("advanced", "拔高提升", advanced))
    return phases


def flatten_phases(phases: list[PathPhase]) -> list[PathPoint]:
    """展平阶段为有序知识点列表（拓扑序：前置在前）。"""
    return [point for phase in phases for point in phase.knowledge_points]


def compute_streak(completed_dates: set[date], *, today: date) -> int:
    """连续打卡天数（跨天边界安全：当日未完成时从昨天起算）。"""
    start = today if today in completed_dates else today - timedelta(days=1)
    streak = 0
    cursor = start
    while cursor in completed_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


@dataclass(frozen=True, slots=True)
class CountdownPhase:
    """倒排阶段。"""

    name: str
    title: str
    start: date
    end: date
    days: int
    focus: str


@dataclass(frozen=True, slots=True)
class CountdownPlan:
    """考期倒排计划。"""

    phases: list[CountdownPhase]
    total_days: int
    warning: str | None = None
    compressed: bool = False


PHASE_FOCUS = {
    "foundation": "系统梳理教材与知识点，补足基础概念",
    "strengthen": "专项刷题与错题重练，提升解题速度",
    "sprint": "全真模考与高频错题回顾，保持考试状态",
}


def build_countdown_plan(*, today: date, exam_date: date) -> CountdownPlan:
    """基础/强化/冲刺三阶段倒排（不足 7 天仅冲刺并给出警示）。"""
    total_days = (exam_date - today).days
    if total_days <= 0:
        raise AppError("考试日期必须晚于今天", code="PLAN_INVALID_EXAM_DATE", status_code=400)

    if total_days < COUNTDOWN_MIN_DAYS:
        phase = CountdownPhase(
            "sprint",
            "冲刺",
            today,
            exam_date,
            total_days,
            PHASE_FOCUS["sprint"],
        )
        return CountdownPlan(
            phases=[phase],
            total_days=total_days,
            warning="距离考试不足 7 天：建议直接进行全真模拟与高频错题回顾，不再安排新知识学习。",
        )

    foundation_days = max(1, round(total_days * 0.4))
    strengthen_days = max(1, round(total_days * 0.35))
    sprint_days = total_days - foundation_days - strengthen_days
    if sprint_days < 1:
        sprint_days = 1
        foundation_days = total_days - strengthen_days - sprint_days

    cursor = today
    phases: list[CountdownPhase] = []
    for name, title, days in (
        ("foundation", "基础阶段", foundation_days),
        ("strengthen", "强化阶段", strengthen_days),
        ("sprint", "冲刺阶段", sprint_days),
    ):
        end = cursor + timedelta(days=days - 1)
        phases.append(CountdownPhase(name, title, cursor, end, days, PHASE_FOCUS[name]))
        cursor = end + timedelta(days=1)
    return CountdownPlan(phases=phases, total_days=total_days)


def should_compress(
    *, progress_ratio: float, elapsed_ratio: float, lag: float = COMPRESSION_LAG
) -> bool:
    """进度落后超过阈值时压缩后续计划。"""
    return progress_ratio < elapsed_ratio - lag


def elapsed_ratio(*, total_days: int, remaining_days: int) -> float:
    """时间进度（0~1）。"""
    if total_days <= 0:
        return 1.0
    return max(0.0, min(1.0, 1 - remaining_days / total_days))


def compress_remaining(
    phases: list[CountdownPhase], *, compression: float = COMPRESSION_LAG
) -> list[CountdownPhase]:
    """压缩强化阶段（天数减 20%），压缩出的天数并入冲刺阶段。"""
    if len(phases) < 2:
        return phases
    middle = phases[-2]
    last = phases[-1]
    reduce_days = max(1, round(middle.days * compression))
    if middle.days <= reduce_days:
        return phases
    new_middle_days = middle.days - reduce_days
    new_middle = replace(
        middle, days=new_middle_days, end=middle.start + timedelta(days=new_middle_days - 1)
    )
    new_last = replace(
        last,
        start=new_middle.end + timedelta(days=1),
        days=last.days + reduce_days,
        end=last.end,
    )
    return [*phases[:-2], new_middle, new_last]


def should_backtrack(recent_results: list[bool], *, threshold: int = 3) -> bool:
    """同一知识点连续答错达到阈值 → 触发前置回溯（F-09）。"""
    if len(recent_results) < threshold:
        return False
    return not any(recent_results[-threshold:])


# ---------- 数据库编排 ----------


def _as_path_point(point: MasteryPoint) -> PathPoint:
    return PathPoint(id=point.knowledge_point_id, name=point.name, mastery=point.mastery)


async def _prerequisite_points(
    session: AsyncSession, *, target_ids: list[uuid.UUID], mastery_by_kp: dict[uuid.UUID, float]
) -> dict[uuid.UUID, list[PathPoint]]:
    """目标知识点的直接前置（含掌握度）。"""
    if not target_ids:
        return {}
    rows = (
        await session.execute(
            select(KnowledgeEdge.to_id, KnowledgePoint.id, KnowledgePoint.name).join(
                KnowledgePoint, KnowledgePoint.id == KnowledgeEdge.from_id
            ).where(KnowledgeEdge.to_id.in_(target_ids))
        )
    ).all()
    result: dict[uuid.UUID, list[PathPoint]] = {}
    for to_id, from_id, name in rows:
        result.setdefault(to_id, []).append(
            PathPoint(
                id=from_id,
                name=name,
                mastery=mastery_by_kp.get(from_id, BktParams().p_init),
            )
        )
    return result


async def _fallback_points(
    session: AsyncSession, *, subject: str | None, limit: int
) -> list[PathPoint]:
    """无掌握度数据时的兜底路径：按教学顺序取前 N 个基础知识点。"""
    stmt = select(KnowledgePoint).where(KnowledgePoint.code.not_like("%.basic")).where(
        KnowledgePoint.code.not_like("%.apply")
    )
    if subject:
        stmt = stmt.where(KnowledgePoint.subject == subject)
    stmt = stmt.order_by(KnowledgePoint.sort_order).limit(limit)
    points = (await session.execute(stmt)).scalars().all()
    prior = BktParams().p_init
    return [PathPoint(id=point.id, name=point.name, mastery=prior) for point in points]


async def generate_path(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    subject: str | None = None,
    limit: int = PATH_LIMIT,
) -> Plan:
    """生成并保存学习路径（旧路径归档）。"""
    from app.services import mastery_service

    overview = await mastery_service.get_mastery_overview(session, user_id=user_id, subject=subject)
    mastery_by_kp = {point.knowledge_point_id: point.mastery for point in overview}
    weak_points = [_as_path_point(point) for point in overview][:limit]
    if not weak_points:
        weak_points = await _fallback_points(session, subject=subject, limit=5)
    strong_points = [
        _as_path_point(point)
        for point in overview
        if MASTERY_THRESHOLD <= point.mastery < ADVANCED_CEILING
    ][:limit]
    prerequisites = await _prerequisite_points(
        session, target_ids=[point.id for point in weak_points], mastery_by_kp=mastery_by_kp
    )
    phases = build_learning_path(
        weak_points=weak_points, prerequisites=prerequisites, strong_points=strong_points
    )

    previous = (
        await session.execute(
            select(Plan).where(
                Plan.user_id == user_id, Plan.kind == PlanKind.PATH, Plan.status == "active"
            )
        )
    ).scalars()
    for plan in previous:
        plan.status = "archived"

    plan = Plan(
        user_id=user_id,
        kind=PlanKind.PATH,
        title=f"{subject or '全科'}学习路径",
        meta={
            "subject": subject,
            "generated_at": utcnow().isoformat(),
            "phases": [
                {
                    "name": phase.name,
                    "title": phase.title,
                    "knowledge_points": [
                        {"id": str(point.id), "name": point.name, "mastery": point.mastery}
                        for point in phase.knowledge_points
                    ],
                }
                for phase in phases
            ],
        },
    )
    session.add(plan)
    await session.flush()
    return plan


async def get_or_create_path(
    session: AsyncSession, *, user_id: uuid.UUID, subject: str | None = None
) -> Plan:
    """获取活跃路径，不存在则生成。"""
    existing = (
        await session.execute(
            select(Plan)
            .where(
                Plan.user_id == user_id,
                Plan.kind == PlanKind.PATH,
                Plan.status == "active",
            )
            .order_by(Plan.created_at.desc())
        )
    ).scalars().first()
    if existing is not None:
        return existing
    return await generate_path(session, user_id=user_id, subject=subject)


async def get_or_create_today(
    session: AsyncSession, *, user_id: uuid.UUID
) -> tuple[Plan, list[PlanTask]]:
    """获取/生成今日任务卡（3~5 个：学/练/复习搭配）。"""
    today = utcnow().date()
    existing = (
        await session.execute(
            select(Plan).where(
                Plan.user_id == user_id,
                Plan.kind == PlanKind.DAILY,
                Plan.status == "active",
                Plan.starts_on == today,
            )
        )
    ).scalars().first()
    if existing is not None:
        tasks = await tasks_of_plan(session, existing.id)
        return existing, tasks

    path = await get_or_create_path(session, user_id=user_id)
    points: list[PathPoint] = []
    for phase in path.meta.get("phases", []):
        for item in phase.get("knowledge_points", []):
            mastery = float(item.get("mastery", 0.3))
            points.append(
                PathPoint(id=uuid.UUID(str(item["id"])), name=str(item["name"]), mastery=mastery)
            )

    review_due = await session.scalar(
        select(func.count())
        .select_from(ReviewCard)
        .where(
            ReviewCard.user_id == user_id,
            ReviewCard.due_at.is_not(None),
            ReviewCard.due_at <= utcnow(),
        )
    )

    plan = Plan(
        user_id=user_id,
        kind=PlanKind.DAILY,
        title=f"{today.isoformat()} 每日任务",
        starts_on=today,
        ends_on=today,
        meta={"date": today.isoformat()},
    )
    session.add(plan)
    await session.flush()

    specs: list[tuple[str, TaskType, PathPoint | None]] = []
    if points:
        specs.append((f"学习：{points[0].name}", TaskType.LEARN, points[0]))
        for point in points[1:3]:
            specs.append((f"练习：{point.name}", TaskType.PRACTICE, point))
    if review_due:
        specs.append(("复习到期卡片", TaskType.REVIEW, None))
    while len(specs) < DAILY_TASK_TARGET and points:
        point = points[len(specs) % len(points)]
        specs.append((f"巩固：{point.name}", TaskType.PRACTICE, point))

    for index, (title, task_type, spec_point) in enumerate(specs[:5]):
        session.add(
            PlanTask(
                plan_id=plan.id,
                user_id=user_id,
                task_date=today,
                title=title,
                task_type=task_type,
                ref_type="knowledge_point" if spec_point is not None else "review_card",
                ref_id=spec_point.id if spec_point is not None else None,
                sort_order=index,
            )
        )
    await session.flush()
    return plan, await tasks_of_plan(session, plan.id)


async def tasks_of_plan(session: AsyncSession, plan_id: uuid.UUID) -> list[PlanTask]:
    rows = (
        await session.execute(
            select(PlanTask).where(PlanTask.plan_id == plan_id).order_by(PlanTask.sort_order)
        )
    ).scalars()
    return list(rows)


@dataclass(slots=True)
class DailyStatus:
    """今日打卡状态。"""

    day: date
    total: int
    completed: int
    all_completed: bool
    streak_days: int


async def complete_task(
    session: AsyncSession, *, user: User, task_id: uuid.UUID
) -> tuple[PlanTask, DailyStatus]:
    """完成任务（幂等）；返回任务与最新打卡状态。"""
    task = await session.get(PlanTask, task_id)
    if task is None or task.user_id != user.id:
        raise NotFoundError("任务不存在", code="PLAN_TASK_NOT_FOUND")
    if task.status != TaskStatus.DONE:
        task.status = TaskStatus.DONE
        task.completed_at = utcnow()
    await session.flush()
    status = await daily_status(session, user_id=user.id, day=task.task_date)
    return task, status


async def daily_status(session: AsyncSession, *, user_id: uuid.UUID, day: date) -> DailyStatus:
    """指定日期的任务完成情况与连续天数。"""
    rows = (
        await session.execute(
            select(
                PlanTask.task_date,
                func.count().label("total"),
                func.count().filter(PlanTask.status == TaskStatus.DONE).label("done"),
            )
            .where(PlanTask.user_id == user_id)
            .group_by(PlanTask.task_date)
        )
    ).all()
    totals: dict[date, tuple[int, int]] = {
        row[0]: (int(row[1]), int(row[2])) for row in rows
    }
    completed_dates = {key for key, (total, done) in totals.items() if total > 0 and total == done}
    total, done = totals.get(day, (0, 0))
    return DailyStatus(
        day=day,
        total=total,
        completed=done,
        all_completed=total > 0 and total == done,
        streak_days=compute_streak(completed_dates, today=day),
    )


async def save_countdown_plan(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    exam_date: date,
    target_score: int | None,
    progress_ratio: float,
) -> tuple[Plan, CountdownPlan]:
    """生成并保存考期倒排（含落后压缩）。"""
    today = utcnow().date()
    countdown = build_countdown_plan(today=today, exam_date=exam_date)
    elapsed = elapsed_ratio(
        total_days=countdown.total_days, remaining_days=(exam_date - today).days
    )
    compressed = False
    if should_compress(progress_ratio=progress_ratio, elapsed_ratio=elapsed):
        countdown = replace(
            countdown, phases=compress_remaining(countdown.phases), compressed=True
        )
        compressed = True

    previous = (
        await session.execute(
            select(Plan).where(
                Plan.user_id == user_id,
                Plan.kind == PlanKind.EXAM_COUNTDOWN,
                Plan.status == "active",
            )
        )
    ).scalars()
    for plan in previous:
        plan.status = "archived"

    plan = Plan(
        user_id=user_id,
        kind=PlanKind.EXAM_COUNTDOWN,
        title=f"考期倒排（{exam_date.isoformat()}）",
        starts_on=today,
        ends_on=exam_date,
        meta={
            "exam_date": exam_date.isoformat(),
            "target_score": target_score,
            "progress_ratio": progress_ratio,
            "compressed": compressed,
            "warning": countdown.warning,
            "phases": [
                {
                    "name": phase.name,
                    "title": phase.title,
                    "start": phase.start.isoformat(),
                    "end": phase.end.isoformat(),
                    "days": phase.days,
                    "focus": phase.focus,
                }
                for phase in countdown.phases
            ],
        },
    )
    session.add(plan)
    await session.flush()
    return plan, countdown


@dataclass(slots=True)
class BacktrackResult:
    """前置回溯结果。"""

    backtrack: bool
    prerequisites: list[str]
    message: str


async def check_backtrack(
    session: AsyncSession, *, user: User, knowledge_point_id: uuid.UUID
) -> BacktrackResult:
    """检测连续答错并给出前置知识点建议（F-09）。"""
    kp = await session.get(KnowledgePoint, knowledge_point_id)
    if kp is None:
        raise NotFoundError("知识点不存在", code="KNOWLEDGE_POINT_NOT_FOUND")

    rows = (
        await session.execute(
            select(ExamAnswer.is_correct, ExamAnswer.created_at)
            .join(Exam, Exam.id == ExamAnswer.exam_id)
            .join(
                QuestionKnowledgePoint,
                QuestionKnowledgePoint.question_id == ExamAnswer.question_id,
            )
            .where(
                Exam.user_id == user.id,
                QuestionKnowledgePoint.knowledge_point_id == knowledge_point_id,
            )
            .order_by(ExamAnswer.created_at.desc())
            .limit(10)
        )
    ).all()
    recent = [bool(row[0]) for row in reversed(rows)]

    if not should_backtrack(recent):
        return BacktrackResult(
            backtrack=False,
            prerequisites=[],
            message=f"「{kp.name}」暂未出现连续卡顿，继续保持当前节奏。",
        )

    prerequisite_names = list(
        (
            await session.execute(
                select(KnowledgePoint.name)
                .join(KnowledgeEdge, KnowledgeEdge.from_id == KnowledgePoint.id)
                .where(KnowledgeEdge.to_id == knowledge_point_id)
            )
        ).scalars()
    )
    if prerequisite_names:
        joined = "、".join(prerequisite_names)
        message = f"检测到「{kp.name}」连续出错，建议先补前置知识：{joined}。"
    else:
        message = f"检测到「{kp.name}」连续出错，建议回到基础概念重新理解。"
    return BacktrackResult(
        backtrack=True, prerequisites=prerequisite_names, message=message
    )


async def regenerate_all_paths(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """为所有有学情数据的用户重排路径（arq 定时任务调用）。"""
    async with sessionmaker() as session:
        user_ids = list(
            (await session.execute(select(MasteryRecord.user_id).distinct())).scalars()
        )
    count = 0
    for user_id in user_ids:
        async with sessionmaker() as session:
            await generate_path(session, user_id=user_id)
            await session.commit()
        count += 1
    return count
