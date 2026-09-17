"""埋点与行为画像契约（F-05/F-46）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

EVENT_NAME_PATTERN = r"^[a-z][a-z0-9_.]{1,63}$"

STYLE_LABELS: dict[str, str] = {
    "independent": "独立型",
    "balanced": "均衡型",
    "guided": "依赖引导型",
    "impulsive": "冲动型",
}


class AnalyticsEventItem(BaseModel):
    """单条埋点事件。"""

    name: str = Field(pattern=EVENT_NAME_PATTERN, description="事件名，如 answer.change")
    payload: dict[str, object] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class AnalyticsBatchRequest(BaseModel):
    """批量上报。"""

    events: list[AnalyticsEventItem] = Field(min_length=1, max_length=100)


class AnalyticsBatchResponse(BaseModel):
    """上报结果。"""

    recorded: int


class BehaviorResponse(BaseModel):
    """学习行为画像（含可解释依据）。"""

    learning_style: str
    learning_style_label: str
    evidence: dict[str, object]
    independent_score: float | None = None
    assisted_score: float | None = None
