"""规划路由（F-06~F-10）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import Plan, PlanTask, User
from app.schemas.plan import (
    BacktrackRequest,
    BacktrackResponse,
    CompleteTaskResponse,
    CountdownPhaseOut,
    ExamCountdownRequest,
    ExamCountdownResponse,
    PathPhaseOut,
    PathPointOut,
    PathResponse,
    TodayResponse,
    TodayTaskOut,
)
from app.services import planner_service
from app.services.planner_service import DailyStatus

router = APIRouter(prefix="/v1/plan", tags=["plan"])


def _path_response(plan: Plan | None) -> PathResponse:
    """路径计划 → 响应。"""
    if plan is None:
        return PathResponse(has_path=False)
    phases = [
        PathPhaseOut(
            name=str(phase.get("name", "")),
            title=str(phase.get("title", "")),
            knowledge_points=[
                PathPointOut(
                    id=uuid.UUID(str(item["id"])),
                    name=str(item["name"]),
                    mastery=float(item.get("mastery", 0.0)),
                )
                for item in phase.get("knowledge_points", [])
            ],
        )
        for phase in plan.meta.get("phases", [])
    ]
    return PathResponse(
        has_path=bool(phases),
        plan_id=plan.id,
        generated_at=str(plan.meta.get("generated_at")) if plan.meta.get("generated_at") else None,
        phases=phases,
    )


def _task_out(task: PlanTask) -> TodayTaskOut:
    return TodayTaskOut(
        id=task.id,
        title=task.title,
        task_type=task.task_type.value,
        status=task.status.value,
        ref_type=task.ref_type,
        ref_id=task.ref_id,
    )


def _today_response(plan: Plan, tasks: list[PlanTask], status: DailyStatus) -> TodayResponse:
    return TodayResponse(
        date=status.day,
        tasks=[_task_out(task) for task in tasks],
        completed_count=status.completed,
        total=status.total,
        all_completed=status.all_completed,
        streak_days=status.streak_days,
    )


@router.get("/path", response_model=PathResponse, summary="个性化学习路径（F-06）")
async def get_path(
    subject: str | None = Query(default=None, max_length=32),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PathResponse:
    """获取活跃路径（不存在则自动生成）。"""
    plan = await planner_service.get_or_create_path(session, user_id=user.id, subject=subject)
    response = _path_response(plan)
    await session.commit()
    return response


@router.post(
    "/path/regenerate",
    response_model=PathResponse,
    status_code=status.HTTP_201_CREATED,
    summary="重排学习路径（F-06）",
)
async def regenerate_path(
    subject: str | None = Query(default=None, max_length=32),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PathResponse:
    """按最新学情重排（旧路径归档）。"""
    plan = await planner_service.generate_path(session, user_id=user.id, subject=subject)
    response = _path_response(plan)
    await session.commit()
    return response


@router.get("/today", response_model=TodayResponse, summary="每日任务卡（F-07）")
async def get_today(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TodayResponse:
    """获取/生成今日任务卡与打卡状态。"""
    plan, tasks = await planner_service.get_or_create_today(session, user_id=user.id)
    assert plan.starts_on is not None
    status = await planner_service.daily_status(session, user_id=user.id, day=plan.starts_on)
    response = _today_response(plan, tasks, status)
    await session.commit()
    return response


@router.post(
    "/tasks/{task_id}/complete",
    response_model=CompleteTaskResponse,
    summary="完成任务打卡（F-07）",
)
async def complete_task(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CompleteTaskResponse:
    """完成任务并返回最新打卡状态（幂等）。"""
    task, status = await planner_service.complete_task(session, user=user, task_id=task_id)
    plan = await session.get(Plan, task.plan_id)
    tasks = await planner_service.tasks_of_plan(session, task.plan_id)
    assert plan is not None
    response = CompleteTaskResponse(
        task=_task_out(task), today=_today_response(plan, tasks, status)
    )
    await session.commit()
    return response


@router.post(
    "/exam-countdown",
    response_model=ExamCountdownResponse,
    status_code=status.HTTP_201_CREATED,
    summary="考期倒排计划（F-08）",
)
async def exam_countdown(
    payload: ExamCountdownRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExamCountdownResponse:
    """基础/强化/冲刺三阶段；落后自动压缩并给出警示。"""
    plan, countdown = await planner_service.save_countdown_plan(
        session,
        user_id=user.id,
        exam_date=payload.exam_date,
        target_score=payload.target_score,
        progress_ratio=payload.progress_ratio,
    )
    response = ExamCountdownResponse(
        plan_id=plan.id,
        exam_date=payload.exam_date,
        total_days=countdown.total_days,
        compressed=countdown.compressed,
        warning=countdown.warning,
        phases=[
            CountdownPhaseOut(
                name=phase.name,
                title=phase.title,
                start=phase.start,
                end=phase.end,
                days=phase.days,
                focus=phase.focus,
            )
            for phase in countdown.phases
        ],
    )
    await session.commit()
    return response


@router.post("/backtrack", response_model=BacktrackResponse, summary="前置知识回溯（F-09）")
async def backtrack(
    payload: BacktrackRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BacktrackResponse:
    """检测连续答错并返回前置知识建议。"""
    result = await planner_service.check_backtrack(
        session, user=user, knowledge_point_id=payload.knowledge_point_id
    )
    response = BacktrackResponse(
        backtrack=result.backtrack,
        prerequisites=result.prerequisites,
        message=result.message,
    )
    await session.commit()
    return response
