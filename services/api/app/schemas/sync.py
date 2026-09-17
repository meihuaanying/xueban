"""同步契约（F-39）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SyncSummaryOut(BaseModel):
    """跨端进度摘要。"""

    completed_today: int
    total_today: int
    streak_days: int
    mistakes_active: int


class SyncStateResponse(BaseModel):
    """同步状态：版本号 + 摘要（客户端轮询比对版本）。"""

    version: str
    summary: SyncSummaryOut
    server_time: datetime
    channel: str = Field(description="WebSocket 频道名 `/v1/sync/ws`")
