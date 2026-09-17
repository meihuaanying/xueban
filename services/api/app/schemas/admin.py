"""运营后台契约（F-44~F-47 / T7.4）。"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AdminQuestionOut(BaseModel):
    """后台题目视图（含答案与解析）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    stage: str
    qtype: str
    stem: str
    options: dict[str, str] | None = None
    answer: str
    analysis: str | None = None
    difficulty: int
    source: str
    status: str
    created_at: datetime
    updated_at: datetime


class AdminQuestionListResponse(BaseModel):
    """题库分页列表。"""

    total: int
    page: int
    page_size: int
    items: list[AdminQuestionOut]


class AdminQuestionCreateRequest(BaseModel):
    """新建题目（草稿态）。"""

    subject: str = Field(max_length=32)
    stage: str = Field(default="junior", max_length=20)
    qtype: Literal["choice", "fill", "short_answer"] = "choice"
    stem: str = Field(min_length=2)
    options: dict[str, str] | None = None
    answer: str = Field(min_length=1)
    analysis: str | None = None
    difficulty: int = Field(default=3, ge=1, le=5)
    source: str = Field(default="admin", max_length=128)


class AdminQuestionUpdateRequest(BaseModel):
    """编辑题目（解析修改留版本历史）。"""

    stem: str | None = None
    options: dict[str, str] | None = None
    answer: str | None = None
    analysis: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    change_note: str | None = Field(default=None, max_length=200)


class QuestionTransitionRequest(BaseModel):
    """审核流流转：draft → review → published（可回退 draft）。"""

    target: Literal["draft", "review", "published"]
    note: str | None = Field(default=None, max_length=200)


class QuestionVersionOut(BaseModel):
    """题目版本快照。"""

    model_config = ConfigDict(from_attributes=True)

    version: int
    editor_id: uuid.UUID | None = None
    change_note: str | None = None
    snapshot: dict[str, Any]
    created_at: datetime


class CoverageResponse(BaseModel):
    """题库覆盖率看板（F-44 验收：解析覆盖率 ≥95%）。"""

    total: int
    with_analysis: int
    coverage_rate: float
    published: int
    draft: int
    review: int
    by_subject: list[dict[str, Any]]


class InspectionRunRequest(BaseModel):
    """质量巡检参数（默认抽样 ≥50）。"""

    sample_size: int = Field(default=50, ge=1, le=200)
    threshold: float = Field(default=0.03, ge=0.0, le=1.0)


class InspectionReportOut(BaseModel):
    """巡检报告。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_date: date
    sample_size: int
    flagged_count: int
    wrong_rate: float
    sympy_checked: int
    sympy_passed: int
    redline_hits: int
    alerted: bool
    detail: dict[str, Any]
    created_at: datetime


class MetricsOverviewResponse(BaseModel):
    """学情数据看板（F-46）：指标口径见 metrics_service。"""

    users_total: int
    users_active_7d: int
    retention_d1: float
    retention_d7: float
    task_completion_rate_7d: float
    renewal_rate: float
    mastery_improvement: float
    generated_at: datetime


class VariantSpec(BaseModel):
    """实验分组定义。"""

    name: str = Field(min_length=1, max_length=32)
    weight: int = Field(default=1, ge=1, le=100)


class ExperimentCreateRequest(BaseModel):
    """创建 A/B 实验。"""

    key: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    variants: list[VariantSpec] = Field(min_length=2, max_length=5)
    metric: str = Field(default="accuracy", max_length=64)


class ExperimentOut(BaseModel):
    """实验详情。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    description: str | None = None
    variants: list[dict[str, Any]]
    metric: str
    status: str
    started_at: datetime | None = None
    created_at: datetime


class ExperimentVariantReport(BaseModel):
    """分组结果与显著性检验。"""

    name: str
    participants: int
    successes: int
    conversion_rate: float
    mean_score: float
    z_score: float | None = None
    p_value: float | None = None
    significant: bool = False


class ExperimentReportResponse(BaseModel):
    """实验报告（F-47：含显著性检验）。"""

    experiment_id: uuid.UUID
    key: str
    metric: str
    variants: list[ExperimentVariantReport]
    total_participants: int
    conclusion: str


class AlertTestRequest(BaseModel):
    """告警联调请求（T7.4）。"""

    kind: str = Field(default="test", max_length=48)
    payload: dict[str, Any] = Field(default_factory=dict)


class AlertRecordOut(BaseModel):
    """告警投递记录。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    target_url: str
    status: str
    response_code: int | None = None
    error: str | None = None
    sent_at: datetime | None = None
    created_at: datetime
