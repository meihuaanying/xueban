"""守护型讲解契约（F-11）。"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class TutorSessionStartRequest(BaseModel):
    """开启讲解会话。"""

    question_id: uuid.UUID


class TutorQuestionOut(BaseModel):
    """讲解题目信息（不含答案）。"""

    id: uuid.UUID
    stem: str
    qtype: str
    options: dict[str, str] | None = None
    difficulty: int
    knowledge_points: list[str] = Field(default_factory=list)


class TutorSessionResponse(BaseModel):
    """讲解会话。"""

    session_id: uuid.UUID
    question: TutorQuestionOut
    hint_level: int
    hint_level_name: str
    max_hint_level: int = 3


class TutorHintRequest(BaseModel):
    """请求某层提示（不填则自动进入下一层）。"""

    level: int | None = Field(default=None, ge=1, le=3)


class TutorHintResponse(BaseModel):
    """提示内容。"""

    session_id: uuid.UUID
    level: int
    level_name: str
    content: str
    next_level: int | None = None
