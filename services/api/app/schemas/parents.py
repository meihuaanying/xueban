"""家长端契约（F-40~F-43）。"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field


class ControlsUpdateRequest(BaseModel):
    """修改防沉迷设置（F-40：修改需家长密码）。"""

    child_id: uuid.UUID
    parent_password: str = Field(min_length=1, max_length=64)
    is_enabled: bool = True
    daily_limit_minutes: int = Field(default=60, ge=0, le=720)
    allowed_start: time | None = None
    allowed_end: time | None = None
    rest_after_minutes: int = Field(default=40, ge=0, le=240)


class ControlsResponse(BaseModel):
    """防沉迷设置。"""

    model_config = ConfigDict(from_attributes=True)

    child_id: uuid.UUID
    is_enabled: bool
    daily_limit_minutes: int
    allowed_start: time | None = None
    allowed_end: time | None = None
    rest_after_minutes: int
    updated_at: datetime | None = None


class GuardianStatusResponse(BaseModel):
    """学习端防沉迷判定（F-40：服务端判定，防本地篡改）。"""

    locked: bool
    reasons: list[str]
    used_minutes: int
    limit_minutes: int | None = None
    suggest_break: bool = False
    curfew_active: bool = False
    available_from: time | None = None


class MasterySummaryOut(BaseModel):
    """孩子掌握度摘要。"""

    red_count: int
    yellow_count: int
    green_count: int
    average_mastery: float | None = None
    points: list[dict[str, object]] = Field(default_factory=list)


class WeeklySummaryOut(BaseModel):
    """周报摘要。"""

    week_start: date
    week_end: date
    summary: dict[str, object] = Field(default_factory=dict)


class DashboardResponse(BaseModel):
    """学情看板（F-41）。"""

    child_id: uuid.UUID
    child_nickname: str | None = None
    mastery: MasterySummaryOut
    streak_days: int
    practice_7d: int
    task_completion_7d: float
    mistakes_active: int
    behavior_style: str | None = None
    weekly: WeeklySummaryOut | None = None
    generated_at: datetime


class DashboardLinkResponse(BaseModel):
    """免登录看板链接（签名 token，可吊销）。"""

    token: str
    url_path: str
    expires_at: datetime


class SafetyEventOut(BaseModel):
    """内容安全拦截事件。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scene: str
    action: str
    categories: dict[str, object] | None = None
    snippet: str | None = None
    created_at: datetime


class ChatTraceOut(BaseModel):
    """对话留痕抽查条目（脱敏节选）。"""

    id: uuid.UUID
    role: str
    hint_level: int | None = None
    excerpt: str
    created_at: datetime


class SafetyReportResponse(BaseModel):
    """安全报告（F-42）：拦截事件 + 对话留痕抽查，按周分页。"""

    week_start: date
    week_end: date
    blocked_count: int
    total_events: int
    page: int
    page_size: int
    events: list[SafetyEventOut]
    traces: list[ChatTraceOut]
    trace_total: int


class ParentTaskOut(BaseModel):
    """亲子任务。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    child_id: uuid.UUID
    title: str
    description: str | None = None
    kind: str
    source: str
    status: str
    due_date: date | None = None
    child_done_at: datetime | None = None
    confirmed_at: datetime | None = None
    created_at: datetime


class ParentTaskCreateRequest(BaseModel):
    """家长布置亲子任务。"""

    child_id: uuid.UUID
    title: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    kind: str = Field(default="explain", max_length=32)
    due_date: date | None = None


class ParentTaskListResponse(BaseModel):
    """亲子任务列表。"""

    tasks: list[ParentTaskOut]
