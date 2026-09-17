"""模考与独立测评契约（F-20/F-28）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ExamCreateRequest(BaseModel):
    """创建限时测评。"""

    subject: str = Field(default="math", max_length=32)
    stage: str | None = Field(default=None, max_length=20)
    count: int = Field(default=10, ge=3, le=50)
    time_limit_minutes: int | None = Field(default=None, ge=5, le=300)
    title: str | None = Field(default=None, max_length=128)


class ExamQuestionOut(BaseModel):
    """试卷题目（不含答案）。"""

    id: uuid.UUID
    stem: str
    qtype: str
    options: dict[str, str] | None = None
    difficulty: int
    knowledge_points: list[str] = Field(default_factory=list)


class ExamCreateResponse(BaseModel):
    """创建结果。"""

    exam_id: uuid.UUID
    kind: str
    title: str
    time_limit_minutes: int
    deadline: datetime | None = None
    questions: list[ExamQuestionOut]


class ExamAnswerItem(BaseModel):
    """一道作答。"""

    question_id: uuid.UUID
    answer: str = Field(min_length=1, max_length=500)


class ExamSubmitRequest(BaseModel):
    """交卷（可为空，表示自动交卷）。"""

    answers: list[ExamAnswerItem] = Field(default_factory=list)


class ExamDiagnosisOut(BaseModel):
    """逐题诊断。"""

    question_id: uuid.UUID
    stem: str
    is_correct: bool
    correct_answer: str
    analysis: str | None = None


class ExamReportResponse(BaseModel):
    """测评报告（即时出分 + 百分位 + 逐题诊断）。"""

    exam_id: uuid.UUID
    kind: str
    status: str
    auto_submitted: bool = False
    summary: dict[str, object]
    diagnoses: list[ExamDiagnosisOut]
    submitted_at: datetime | None = None
