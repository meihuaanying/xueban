"""内容安全路由：对话入口统一过检（M3 起被讲解/陪练接口复用）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas import SafetyCheckRequest, SafetyCheckResponse
from app.services.safety_service import SafetyService

router = APIRouter(prefix="/v1/safety", tags=["safety"])


@router.post("/check", response_model=SafetyCheckResponse, summary="文本内容安全检查")
async def check_text(
    payload: SafetyCheckRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SafetyCheckResponse:
    """检查文本是否合规；阻断事件落库（F-42 数据源）。"""
    service: SafetyService = request.app.state.safety
    decision = await service.check_and_record(
        session, text=payload.text, scene=payload.scene, user_id=user.id
    )
    await session.commit()
    return SafetyCheckResponse(
        allowed=decision.allowed,
        action=decision.action,
        provider=decision.provider,
        categories=decision.categories,
    )
