"""练习/错题本/复习契约（F-17~F-19）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class QuestionBriefOut(BaseModel):
    """题目简要信息（不含答案）。"""

    id: uuid.UUID
    stem: str
    qtype: str
    options: dict[str, str] | None = None
    difficulty: int
    knowledge_points: list[str] = Field(default_factory=list)


class PracticeGenerateRequest(BaseModel):
    """智能出题请求。"""

    subject: str = Field(default="math", max_length=32)
    stage: str | None = Field(default=None, max_length=20)
    count: int = Field(default=5, ge=1, le=20)
    knowledge_point_ids: list[uuid.UUID] | None = None


class PracticeQuestionOut(QuestionBriefOut):
    """练习题目（含出题原因）。"""

    reason: str = Field(description="weak=薄弱知识点 / explore=拓展")


class PracticeGenerateResponse(BaseModel):
    """出题结果。"""

    count: int
    weak_count: int
    weak_ratio: float
    questions: list[PracticeQuestionOut]


class PracticeAnswerRequest(BaseModel):
    """练习作答。"""

    question_id: uuid.UUID
    answer: str = Field(min_length=1, max_length=500)
    source: Literal["practice", "repractice", "variant"] = "practice"
    client_event_id: str | None = Field(
        default=None, max_length=64, description="离线补齐幂等键（同一事件重放不重复计数）"
    )


class PracticeAnswerResponse(BaseModel):
    """练习作答结果（含动态难度与错题归集状态）。"""

    is_correct: bool
    correct_answer: str
    next_difficulty: int
    mistake_collected: bool
    mistake_removed: bool
    card_due_at: datetime | None = None
    explanation: str | None = None
    duplicate: bool = False


class MistakeSummaryItem(BaseModel):
    """错因分组计数。"""

    reason: str
    reason_label: str
    count: int


class MistakeEntryOut(BaseModel):
    """错题条目。"""

    id: uuid.UUID
    question: QuestionBriefOut
    wrong_answer: str | None = None
    error_reason: str | None = None
    error_reason_label: str | None = None
    state: str
    review_count: int
    created_at: datetime


class MistakeListResponse(BaseModel):
    """错题本列表（按错因分组统计）。"""

    active_count: int
    mastered_count: int
    summary: list[MistakeSummaryItem]
    entries: list[MistakeEntryOut]


class MistakeRepracticeRequest(BaseModel):
    """一键重练。"""

    count: int = Field(default=5, ge=1, le=20)
    error_reason: str | None = Field(default=None, max_length=32)


class MistakeRepracticeResponse(BaseModel):
    """重练题目列表（作答时 source=repractice 以触发移出）。"""

    count: int
    questions: list[QuestionBriefOut]


class ReviewCardOut(BaseModel):
    """复习卡片。"""

    card_id: uuid.UUID
    question: QuestionBriefOut
    state: str
    reps: int
    lapses: int
    difficulty: float
    due_at: datetime | None = None


class ReviewDueResponse(BaseModel):
    """到期复习卡片。"""

    due_count: int
    cards: list[ReviewCardOut]


class ReviewGradeRequest(BaseModel):
    """FSRS 评分（1=Again 2=Hard 3=Good 4=Easy）。"""

    grade: int = Field(ge=1, le=4)


class ReviewGradeResponse(BaseModel):
    """评分后的调度结果。"""

    card_id: uuid.UUID
    state: str
    interval_days: float
    due_at: datetime
    reps: int
    lapses: int
    difficulty: float
