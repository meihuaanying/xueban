"""学情画像路由（F-03 雷达图数据）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas.profile import MasteryOverviewResponse, MasteryPointResponse
from app.services import mastery_service

router = APIRouter(prefix="/v1/profile", tags=["profile"])


@router.get(
    "/mastery",
    response_model=MasteryOverviewResponse,
    summary="知识掌握度雷达图（F-03）",
)
async def get_mastery(
    subject: str | None = Query(default=None, max_length=32),
    stage: str | None = Query(default=None, max_length=20),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MasteryOverviewResponse:
    """返回掌握度总览（含时间衰减与红黄绿分级）。"""
    points = await mastery_service.get_mastery_overview(
        session, user_id=user.id, subject=subject, stage=stage
    )
    levels = {"red": 0, "yellow": 0, "green": 0}
    for point in points:
        levels[point.level] = levels.get(point.level, 0) + 1
    return MasteryOverviewResponse(
        has_data=bool(points),
        average_mastery=mastery_service.mastery_average(points),
        red_count=levels["red"],
        yellow_count=levels["yellow"],
        green_count=levels["green"],
        points=[MasteryPointResponse.model_validate(point) for point in points],
    )
