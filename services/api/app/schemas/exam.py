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


class ExamBlueprintCreateRequest(BaseModel):
    """按地区考卷蓝图组卷（新高考数学 19 题结构）。"""

    blueprint_id: str = Field(default="gaokao_2026_gd", max_length=64)


class ExamQuestionOut(BaseModel):
    """试卷题目（不含答案）。"""

    id: uuid.UUID
    stem: str
    qtype: str
    options: dict[str, str] | None = None
    difficulty: int
    knowledge_points: list[str] = Field(default_factory=list)
    knowledge_point_ids: list[str] = Field(default_factory=list)


class ExamCreateResponse(BaseModel):
    """创建结果。"""

    exam_id: uuid.UUID
    kind: str
    title: str
    time_limit_minutes: int
    deadline: datetime | None = None
    questions: list[ExamQuestionOut]


class ExamAnswerItem(BaseModel):
    """一道作答。

    上限按解答题批改接口（8000）对齐：解答题是步骤文字，500 字会在交卷时
    整卷 422；客观题的实际输入远小于此，不做题型区分。
    """

    question_id: uuid.UUID
    answer: str = Field(min_length=1, max_length=8000)


class ExamSubmitRequest(BaseModel):
    """交卷（可为空，表示自动交卷）。"""

    answers: list[ExamAnswerItem] = Field(default_factory=list)


class ExamSubjectiveGradeRequest(BaseModel):
    """解答题批改请求（蓝图模考）。

    批改以交卷时落库的作答为准；`student_answer` 仅在未作答时兜底，
    防止交卷后看到标准答案再改答案刷分。
    """

    question_id: uuid.UUID
    student_answer: str | None = Field(default=None, max_length=8000)


class ExamSubjectiveStepOut(BaseModel):
    """解答题逐步得分。"""

    step: str
    score: float
    comment: str = ""
    lost_points: str = ""


class ExamSubjectiveGradeResponse(BaseModel):
    """解答题批改结果 + 整卷总分状态。"""

    question_id: uuid.UUID
    score: float
    max_score: float
    # 全部解答题批完前保持 None（客观分不冒充整卷分）
    exam_score: float | None
    graded_count: int
    subjective_count: int
    all_graded: bool
    steps: list[ExamSubjectiveStepOut] = Field(default_factory=list)
    rewrite: str = ""
    summary: str = ""
    machine_check: dict[str, object] | None = None


class ExamDiagnosisOut(BaseModel):
    """逐题诊断。"""

    question_id: uuid.UUID
    stem: str
    # 主观题（解答题）未批改时为 None
    is_correct: bool | None
    correct_answer: str
    analysis: str | None = None
    subjective: bool = False
    # 解答题批改后才有：该题卷面得分与是否已批
    score: float | None = None
    graded: bool = False


class ExamReportResponse(BaseModel):
    """测评报告（即时出分 + 百分位 + 逐题诊断）。"""

    exam_id: uuid.UUID
    kind: str
    status: str
    auto_submitted: bool = False
    summary: dict[str, object]
    diagnoses: list[ExamDiagnosisOut]
    submitted_at: datetime | None = None
