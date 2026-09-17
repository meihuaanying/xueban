"""微课契约（F-16）。"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class MicroLessonCreateRequest(BaseModel):
    """创建微课。"""

    knowledge_point_id: uuid.UUID


class MicroLessonResponse(BaseModel):
    """微课状态。"""

    lesson_id: uuid.UUID
    title: str
    status: str
    char_count: int
    retries: int
    error: str | None = None


class MicroLessonAudioResponse(BaseModel):
    """微课音频地址。"""

    lesson_id: uuid.UUID
    url: str
    mime: str
    expires_in: int
