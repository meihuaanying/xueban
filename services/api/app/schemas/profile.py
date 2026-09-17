"""学情画像契约（F-03/F-05）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MasteryPointResponse(BaseModel):
    """单个知识点掌握度。"""

    model_config = ConfigDict(from_attributes=True)

    knowledge_point_id: uuid.UUID
    code: str
    name: str
    subject: str
    stage: str
    mastery: float = Field(ge=0, le=1)
    level: str = Field(description="red/yellow/green 预警分级")
    total_attempts: int
    correct_attempts: int
    last_practiced_at: datetime | None = None


class MasteryOverviewResponse(BaseModel):
    """雷达图/画像总览（空数据时 has_data=false，前端展示引导态）。"""

    has_data: bool
    average_mastery: float | None = None
    red_count: int
    yellow_count: int
    green_count: int
    points: list[MasteryPointResponse]
