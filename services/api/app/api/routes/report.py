"""复盘路由（F-27/F-29/F-30）。"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas.report import (
    CalendarDayOut,
    CalendarResponse,
    SharedReportResponse,
    ShareResponse,
    SprintResponse,
    WeeklyReportResponse,
)
from app.services import report_service

router = APIRouter(tags=["reports"])


@router.get(
    "/v1/reports/weekly",
    response_model=WeeklyReportResponse,
    summary="每周学情报告（F-27）",
)
async def weekly_report(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> WeeklyReportResponse:
    """获取本周报告（按周幂等生成）。"""
    report = await report_service.get_or_create_weekly_report(session, user=user)
    response = WeeklyReportResponse(
        week_start=report.week_start,
        week_end=report.week_start + timedelta(days=6),
        report=dict(report.payload),
    )
    await session.commit()
    return response


@router.post(
    "/v1/reports/weekly/share",
    response_model=ShareResponse,
    summary="生成免登录只读分享链接（F-27）",
)
async def share_weekly_report(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ShareResponse:
    """生成签名 token（30 天有效，可吊销）。"""
    share = await report_service.create_share(session, user=user)
    response = ShareResponse(
        token=share.token,
        url_path=f"/v1/reports/shared/{share.token}",
        expires_at=share.expires_at,
    )
    await session.commit()
    return response


@router.delete(
    "/v1/reports/shares/{token}",
    status_code=204,
    summary="吊销分享链接（F-27）",
)
async def revoke_share(
    token: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """吊销后分享链接立即失效。"""
    await report_service.revoke_share(session, user=user, token=token)
    await session.commit()


@router.get(
    "/v1/reports/shared/{token}",
    response_model=SharedReportResponse,
    summary="读取分享报告（免登录只读）",
)
async def shared_report(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> SharedReportResponse:
    """免登录访问分享的报告内容。"""
    payload = await report_service.get_shared_report(session, token=token)
    return SharedReportResponse(report=payload)


@router.get(
    "/v1/stats/calendar",
    response_model=CalendarResponse,
    summary="学习日历与打卡（F-29）",
)
async def calendar(
    year: int = Query(ge=2020, le=2100),
    month: int = Query(ge=1, le=12),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CalendarResponse:
    """学习热力图数据与连续打卡天数（不含排名）。"""
    stats = await report_service.calendar_stats(
        session, user_id=user.id, year=year, month=month
    )
    response = CalendarResponse(
        year=stats.year,
        month=stats.month,
        streak_days=stats.streak_days,
        max_practice=stats.max_practice,
        days=[
            CalendarDayOut(
                day=item.day,
                practice_count=item.practice_count,
                correct_count=item.correct_count,
                tasks_total=item.tasks_total,
                tasks_done=item.tasks_done,
                studied=item.studied,
            )
            for item in stats.days
        ],
    )
    await session.commit()
    return response


@router.get(
    "/v1/exam-prep/sprint",
    response_model=SprintResponse,
    summary="考前冲刺包（F-30）",
)
async def sprint_package(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SprintResponse:
    """高频错题 + 未掌握考点 + 预测卷（与考期倒排联动）。"""
    package = await report_service.build_sprint_package(session, user=user)
    response = SprintResponse(
        exam_date=package.exam_date,
        remaining_days=package.remaining_days,
        high_freq_mistakes=package.high_freq_mistakes,
        unmastered_knowledge_points=package.unmastered_knowledge_points,
        predicted_paper=package.predicted_paper,
        generated_at=package.generated_at,
    )
    await session.commit()
    return response
