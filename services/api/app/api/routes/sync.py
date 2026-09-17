"""同步路由（F-39）：轮询状态 + WebSocket 版本推送。"""

from __future__ import annotations

import asyncio
import contextlib
import uuid

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas.sync import SyncStateResponse, SyncSummaryOut
from app.services import sync_service

router = APIRouter(prefix="/v1/sync", tags=["sync"])

PUSH_INTERVAL_SECONDS = 5


def _to_response(snapshot: sync_service.SyncSnapshot, *, user: User) -> SyncStateResponse:
    """快照 → 响应契约。"""
    return SyncStateResponse(
        version=snapshot.version,
        summary=SyncSummaryOut(
            completed_today=snapshot.completed_today,
            total_today=snapshot.total_today,
            streak_days=snapshot.streak_days,
            mistakes_active=snapshot.mistakes_active,
        ),
        server_time=snapshot.server_time,
        channel=sync_service.user_channel(user.id),
    )


@router.get(
    "/state",
    response_model=SyncStateResponse,
    summary="同步状态（F-39：轮询比对版本号）",
)
async def sync_state(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SyncStateResponse:
    """返回版本号与关键进度摘要；客户端版本变化时刷新各自数据。"""
    snapshot = await sync_service.snapshot(session, user=user)
    await session.commit()
    return _to_response(snapshot, user=user)


async def _authenticate_ws(token: str, sessionmaker: object) -> User | None:
    """WebSocket 鉴权（查询参数 token）。"""
    from app.errors import AuthError
    from app.services.security import decode_token

    try:
        payload = decode_token(token, expected_type="access")
    except (AuthError, ValueError, KeyError):
        return None
    subject = payload.get("sub")
    if not subject:
        return None
    async with sessionmaker() as session:  # type: ignore[operator]
        user: User | None = await session.get(User, uuid.UUID(str(subject)))
    return user


@router.websocket("/ws")
async def sync_ws(websocket: WebSocket, token: str = Query(...)) -> None:
    """WebSocket：每 5 秒推送版本号与摘要（版本不变也推送，便于保活检测）。"""
    sessionmaker = websocket.app.state.sessionmaker
    user = await _authenticate_ws(token, sessionmaker)
    if user is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        while True:
            async with sessionmaker() as session:
                snapshot = await sync_service.snapshot(session, user=user)
            await websocket.send_json(
                {
                    "version": snapshot.version,
                    "summary": {
                        "completed_today": snapshot.completed_today,
                        "total_today": snapshot.total_today,
                        "streak_days": snapshot.streak_days,
                        "mistakes_active": snapshot.mistakes_active,
                    },
                    "server_time": snapshot.server_time.isoformat(),
                }
            )
            await asyncio.sleep(PUSH_INTERVAL_SECONDS)
    except (WebSocketDisconnect, RuntimeError):
        with contextlib.suppress(RuntimeError):
            await websocket.close()
