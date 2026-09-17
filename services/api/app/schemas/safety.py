"""内容安全契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SafetyCheckRequest(BaseModel):
    """文本检查请求。"""

    text: str = Field(min_length=1, max_length=2000)
    scene: str = Field(default="chat", max_length=32)


class SafetyCheckResponse(BaseModel):
    """文本检查结果。"""

    allowed: bool
    action: str
    provider: str
    categories: list[str]
