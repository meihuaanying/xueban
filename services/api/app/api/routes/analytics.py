"""埋点路由（F-05/F-46 数据源与行为画像）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas.analytics import (
    STYLE_LABELS,
    AnalyticsBatchRequest,
    AnalyticsBatchResponse,
    BehaviorResponse,
)
from app.services import analytics_service

router = APIRouter(tags=["analytics"])


@router.post(
    "/v1/analytics/events",
    response_model=AnalyticsBatchResponse,
    summary="批量上报埋点事件（F-05 数据源）",
)
async def record_events(
    payload: AnalyticsBatchRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnalyticsBatchResponse:
    """批量写入（最多 100 条/批；事件名与负载由 schema 校验）。"""
    recorded = await analytics_service.record_events(
        session,
        user=user,
        events=payload.events,
        user_agent=request.headers.get("User-Agent"),
    )
    response = AnalyticsBatchResponse(recorded=recorded)
    await session.commit()
    return response


@router.get(
    "/v1/profile/behavior",
    response_model=BehaviorResponse,
    summary="学习行为画像（F-05，含可解释依据）",
)
async def behavior_profile(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BehaviorResponse:
    """基于埋点/练习/求助记录推断学习风格。"""
    profile = await analytics_service.compute_behavior_profile(session, user=user)
    response = BehaviorResponse(
        learning_style=profile.learning_style,
        learning_style_label=STYLE_LABELS.get(profile.learning_style, profile.learning_style),
        evidence=profile.evidence,
        independent_score=profile.independent_score,
        assisted_score=profile.assisted_score,
    )
    await session.commit()
    return response
