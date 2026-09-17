"""诊断与错因契约（F-01/F-02）。"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.profile import MasteryPointResponse


class DiagnosisStartRequest(BaseModel):
    """开启诊断。"""

    subject: str = Field(default="math", max_length=32)
    stage: str = Field(default="junior", max_length=20)
    target_count: int = Field(default=25, ge=20, le=30, description="题量 20~30")


class DiagnosisProgress(BaseModel):
    """进度。"""

    answered: int
    total: int


class DiagnosisQuestionOut(BaseModel):
    """诊断题目（不下发答案）。"""

    id: uuid.UUID
    stem: str
    qtype: str
    options: dict[str, str] | None = None
    difficulty: int
    knowledge_points: list[str] = Field(default_factory=list)


class DiagnosisStartResponse(BaseModel):
    """开启诊断响应。"""

    exam_id: uuid.UUID
    status: str
    progress: DiagnosisProgress
    question: DiagnosisQuestionOut


class DiagnosisAnswerRequest(BaseModel):
    """提交作答。"""

    question_id: uuid.UUID
    answer: str = Field(min_length=1, max_length=500)


class DiagnosisAnswerResponse(BaseModel):
    """作答判定与下一题。"""

    exam_id: uuid.UUID
    is_correct: bool
    correct_answer: str
    progress: DiagnosisProgress
    finished: bool
    next_question: DiagnosisQuestionOut | None = None


class DiagnosisReportResponse(BaseModel):
    """诊断报告。"""

    exam_id: uuid.UUID
    finished: bool
    summary: dict[str, Any]
    points: list[MasteryPointResponse]
    has_data: bool


class AttributionResponse(BaseModel):
    """错因归因响应。"""

    entry_id: uuid.UUID
    reason: str
    reason_label: str
    confidence: float
    explanation: str
