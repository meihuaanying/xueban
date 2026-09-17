"""规划契约（F-06~F-10）。"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field


class PathPointOut(BaseModel):
    """路径知识点。"""

    id: uuid.UUID
    name: str
    mastery: float


class PathPhaseOut(BaseModel):
    """路径阶段。"""

    name: str
    title: str
    knowledge_points: list[PathPointOut]


class PathResponse(BaseModel):
    """学习路径（has_path=false 表示暂无数据）。"""

    has_path: bool
    plan_id: uuid.UUID | None = None
    generated_at: str | None = None
    phases: list[PathPhaseOut] = Field(default_factory=list)


class TodayTaskOut(BaseModel):
    """今日任务。"""

    id: uuid.UUID
    title: str
    task_type: str
    status: str
    ref_type: str | None = None
    ref_id: uuid.UUID | None = None


class TodayResponse(BaseModel):
    """今日任务卡与打卡状态。"""

    date: date
    tasks: list[TodayTaskOut]
    completed_count: int
    total: int
    all_completed: bool
    streak_days: int


class CompleteTaskResponse(BaseModel):
    """完成任务响应。"""

    task: TodayTaskOut
    today: TodayResponse


class ExamCountdownRequest(BaseModel):
    """考期倒排请求。"""

    exam_date: date
    target_score: int | None = Field(default=None, ge=0, le=999)
    progress_ratio: float = Field(default=1.0, ge=0, le=1, description="当前进度（0~1）")


class CountdownPhaseOut(BaseModel):
    """倒排阶段。"""

    name: str
    title: str
    start: date
    end: date
    days: int
    focus: str


class ExamCountdownResponse(BaseModel):
    """考期倒排计划。"""

    plan_id: uuid.UUID
    exam_date: date
    total_days: int
    compressed: bool
    warning: str | None = None
    phases: list[CountdownPhaseOut]


class BacktrackRequest(BaseModel):
    """前置回溯请求。"""

    knowledge_point_id: uuid.UUID


class BacktrackResponse(BaseModel):
    """前置回溯结果。"""

    backtrack: bool
    prerequisites: list[str]
    message: str
