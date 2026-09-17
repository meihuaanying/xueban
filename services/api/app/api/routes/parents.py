"""家长端路由（F-40~F-43）：看板、防沉迷、安全报告、亲子任务、免登录链接。"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, require_roles
from app.models import User, UserRole
from app.schemas import (
    ControlsResponse,
    ControlsUpdateRequest,
    DashboardLinkResponse,
    DashboardResponse,
    GuardianStatusResponse,
    ParentTaskCreateRequest,
    ParentTaskListResponse,
    ParentTaskOut,
    ParentWeeklyResponse,
    SafetyReportResponse,
)
from app.services import parent_service

router = APIRouter(prefix="/v1", tags=["parents"])


def _controls_response(control: object) -> ControlsResponse:
    """防沉迷设置响应。"""
    return ControlsResponse.model_validate(control)


def _task_out(task: object) -> ParentTaskOut:
    """亲子任务响应。"""
    return ParentTaskOut.model_validate(task)


@router.get(
    "/parents/children/{child_id}/dashboard",
    response_model=DashboardResponse,
    summary="孩子学情看板（F-41）",
)
async def child_dashboard(
    child_id: uuid.UUID,
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """家长查看已绑定孩子的学情看板。"""
    child = await parent_service.get_bound_child(session, parent=parent, child_id=child_id)
    data = await parent_service.build_dashboard(session, child=child)
    return DashboardResponse.model_validate(data)


@router.get(
    "/parents/children/{child_id}/controls",
    response_model=ControlsResponse,
    summary="读取防沉迷设置（F-40）",
)
async def get_controls(
    child_id: uuid.UUID,
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> ControlsResponse:
    """读取孩子的使用时长/时段设置。"""
    await parent_service.get_bound_child(session, parent=parent, child_id=child_id)
    control = await parent_service.get_controls(session, child_id=child_id)
    return _controls_response(control)


@router.put(
    "/parents/controls",
    response_model=ControlsResponse,
    summary="更新防沉迷设置（F-40，需家长密码）",
)
async def update_controls(
    payload: ControlsUpdateRequest,
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> ControlsResponse:
    """更新设置（服务端强制生效；修改需家长密码）。"""
    control = await parent_service.update_controls(
        session,
        parent=parent,
        child_id=payload.child_id,
        parent_password=payload.parent_password,
        is_enabled=payload.is_enabled,
        daily_limit_minutes=payload.daily_limit_minutes,
        allowed_start=payload.allowed_start,
        allowed_end=payload.allowed_end,
        rest_after_minutes=payload.rest_after_minutes,
    )
    await session.commit()
    return _controls_response(control)


@router.get(
    "/guardian/status",
    response_model=GuardianStatusResponse,
    summary="学习端防沉迷判定（F-40，服务端强制）",
)
async def guardian_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> GuardianStatusResponse:
    """学习端拉取锁屏判定（学生账号；无设置时返回未锁定）。"""
    status = await parent_service.guardian_status(session, user=user)
    return GuardianStatusResponse(
        locked=status.locked,
        reasons=status.reasons,
        used_minutes=status.used_minutes,
        limit_minutes=status.limit_minutes,
        suggest_break=status.suggest_break,
        curfew_active=status.curfew_active,
        available_from=status.available_from,
    )


@router.post(
    "/parents/dashboard/links",
    response_model=DashboardLinkResponse,
    summary="生成免登录看板链接（F-41，可吊销）",
)
async def create_dashboard_link(
    child_id: uuid.UUID = Query(...),
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> DashboardLinkResponse:
    """生成签名链接（只读、可吊销）。"""
    share = await parent_service.create_dashboard_link(session, parent=parent, child_id=child_id)
    await session.commit()
    return DashboardLinkResponse(
        token=share.token,
        url_path=f"/parents/view/{share.token}",
        expires_at=share.expires_at,
    )


@router.delete(
    "/parents/dashboard/links/{token}",
    status_code=204,
    summary="吊销免登录看板链接（F-41）",
)
async def revoke_dashboard_link(
    token: str,
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> None:
    """吊销签名链接。"""
    await parent_service.revoke_dashboard_link(session, parent=parent, token=token)
    await session.commit()


@router.get(
    "/parents/dashboard/{token}",
    response_model=DashboardResponse,
    summary="免登录看板（F-41，签名 token）",
)
async def shared_dashboard(
    token: str, session: AsyncSession = Depends(get_session)
) -> DashboardResponse:
    """免登录读取（需有效且未吊销的 token）。"""
    data = await parent_service.get_shared_dashboard(session, token=token)
    return DashboardResponse.model_validate(data)


@router.get(
    "/parents/children/{child_id}/safety",
    response_model=SafetyReportResponse,
    summary="内容安全报告（F-42，按周分页）",
)
async def safety_report(
    child_id: uuid.UUID,
    week_start: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> SafetyReportResponse:
    """拦截事件 + 对话留痕抽查（分页）。"""
    data = await parent_service.safety_report(
        session,
        parent=parent,
        child_id=child_id,
        week_start=week_start,
        page=page,
        page_size=page_size,
    )
    return SafetyReportResponse.model_validate(data)


@router.get(
    "/parents/tasks",
    response_model=ParentTaskListResponse,
    summary="亲子任务列表（F-43：家长/孩子角色各自视图）",
)
async def list_tasks(
    child_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ParentTaskListResponse:
    """家长查看自己布置/系统布置的任务；孩子查看自己的任务。"""
    if user.role == UserRole.PARENT:
        tasks = await parent_service.list_tasks(session, parent=user, child_id=child_id)
    else:
        tasks = await parent_service.list_child_tasks(session, child=user)
    await session.commit()
    return ParentTaskListResponse(tasks=[_task_out(task) for task in tasks])


@router.post(
    "/parents/tasks",
    response_model=ParentTaskOut,
    status_code=201,
    summary="家长布置亲子任务（F-43）",
)
async def create_task(
    payload: ParentTaskCreateRequest,
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> ParentTaskOut:
    """布置任务（孩子完成后家长确认）。"""
    task = await parent_service.create_task(
        session,
        parent=parent,
        child_id=payload.child_id,
        title=payload.title,
        description=payload.description,
        kind=payload.kind,
        due_date=payload.due_date,
    )
    await session.commit()
    return _task_out(task)


@router.post(
    "/parents/tasks/{task_id}/confirm",
    response_model=ParentTaskOut,
    summary="家长确认亲子任务（F-43）",
)
async def confirm_task(
    task_id: uuid.UUID,
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> ParentTaskOut:
    """确认孩子已完成的亲子任务。"""
    task = await parent_service.confirm_task(session, parent=parent, task_id=task_id)
    await session.commit()
    return _task_out(task)


@router.post(
    "/parents/tasks/{task_id}/done",
    response_model=ParentTaskOut,
    summary="孩子完成亲子任务（F-43）",
)
async def complete_task(
    task_id: uuid.UUID,
    user: User = Depends(require_roles(UserRole.STUDENT)),
    session: AsyncSession = Depends(get_session),
) -> ParentTaskOut:
    """孩子标记任务完成。"""
    task = await parent_service.complete_child_task(session, child=user, task_id=task_id)
    await session.commit()
    return _task_out(task)


@router.get(
    "/parents/weekly",
    response_model=ParentWeeklyResponse,
    summary="家长端周报（F-31：时长/进度/薄弱点 + 亲子建议）",
)
async def parent_weekly(
    child_id: uuid.UUID,
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> ParentWeeklyResponse:
    """家长可见周报：含至少 2 条可执行亲子建议。"""
    data = await parent_service.weekly_report(session, parent=parent, child_id=child_id)
    return ParentWeeklyResponse.model_validate(data)
