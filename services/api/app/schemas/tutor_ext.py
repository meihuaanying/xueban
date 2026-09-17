"""讲解扩展契约（F-12~F-14）。"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class AltSolutionOut(BaseModel):
    """一种解法。"""

    title: str
    steps: list[str]
    scenario: str
    answer_verified: bool = Field(description="SymPy 等价性抽检是否通过")


class AltSolutionsResponse(BaseModel):
    """多解法对比。"""

    session_id: uuid.UUID
    solutions: list[AltSolutionOut]
    checked_count: int
    verified_count: int


class AnalogyResponse(BaseModel):
    """生活化类比。"""

    session_id: uuid.UUID
    analogy: str
    mapping: str
    caveat: str


class VariantOut(BaseModel):
    """变式题（不含答案）。"""

    question_id: uuid.UUID
    stem: str
    options: dict[str, str] | None = None
    difficulty: int


class VariantsResponse(BaseModel):
    """变式题列表。"""

    session_id: uuid.UUID
    variants: list[VariantOut]


class VariantAnswerRequest(BaseModel):
    """变式题作答。"""

    answer: str = Field(min_length=1, max_length=500)


class BackToTutorOut(BaseModel):
    """答错回炉信息。"""

    session_id: uuid.UUID
    message: str


class VariantAnswerResponse(BaseModel):
    """变式题作答结果。"""

    is_correct: bool
    correct_answer: str
    back_to_tutor: BackToTutorOut | None = None
