"""批改契约（F-22~F-24）。"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ObjectiveGradingRequest(BaseModel):
    """客观题批改请求。"""

    question_id: uuid.UUID
    answer: str = Field(min_length=1, max_length=500)


class ObjectiveGradingResponse(BaseModel):
    """客观题批改结果（答错给出讲解会话直达入口）。"""

    is_correct: bool
    correct_answer: str
    analysis: str | None = None
    tutor_session_id: uuid.UUID | None = None


class SubjectiveStepOut(BaseModel):
    """逐步得分点。"""

    step: str
    score: float
    comment: str
    lost_points: str


class SubjectiveGradingRequest(BaseModel):
    """主观题批改请求（question_id 与 stem+answer 二选一）。"""

    question_id: uuid.UUID | None = None
    stem: str | None = Field(default=None, max_length=2000)
    answer: str | None = Field(default=None, max_length=2000)
    criteria: str | None = Field(default=None, max_length=1000)
    student_answer: str = Field(min_length=1, max_length=8000)


class SubjectiveGradingResponse(BaseModel):
    """主观题批改结果。"""

    total_score: float
    max_score: float
    steps: list[SubjectiveStepOut]
    rewrite: str
    summary: str
    machine_check: dict[str, object] | None = None


class EssayGradingRequest(BaseModel):
    """作文批改请求。"""

    rubric: Literal["zhongkao", "gaokao", "cet", "kaoyan"]
    content: str = Field(min_length=50, max_length=20000)
    prompt: str | None = Field(default=None, max_length=2000)


class DimensionScoreOut(BaseModel):
    """作文维度分。"""

    score: float
    max_score: float
    comment: str


class ParagraphCommentOut(BaseModel):
    """逐段评语。"""

    index: int
    comment: str
    suggestion: str


class EssayGradingResponse(BaseModel):
    """作文批改结果。"""

    total_score: float
    max_score: float
    rubric: str
    structure: DimensionScoreOut
    ideas: DimensionScoreOut
    language: DimensionScoreOut
    paragraphs: list[ParagraphCommentOut]
    upgrade_sample: str
    summary: str
