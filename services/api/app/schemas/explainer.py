"""Explainer 契约（P1 / §5.5）。

四个端点的返回体统一带 ``status``，前端据此区分「生成中」与「已就绪」，
不必自己猜 HTTP 状态码以外的事情。
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExplainerGenerateRequest(BaseModel):
    """生成讲解。``knowledge_id`` 接受课程编码或库内 UUID。"""

    knowledge_id: str = Field(min_length=1, max_length=64)
    mode: Literal["interactive", "video"] = "interactive"


class ExplainerContentOut(BaseModel):
    """已生成内容（含消毒后的 HTML）。"""

    id: uuid.UUID
    knowledge_id: str
    stage: str
    title: str
    status: str
    #: 消毒后的单文件 HTML；未就绪时为空串。
    html: str = ""
    #: True 表示这是 §5.4 的图文分步降级产物（交互页没生成出来）。
    degraded: bool = False
    byte_size: int = 0
    #: 教学脚本（≤4 幕），供前端做无脚本兜底与朗读。
    script: dict[str, Any] = Field(default_factory=dict)
    #: §5.4 的渲染超时（秒），前端超时要切降级视图。
    render_timeout_seconds: int = 60


class ExplainerGenerateResponse(BaseModel):
    """202 形态：任务已入队，前端轮询 ``GET /v1/explainer/{job_id}``。"""

    job_id: uuid.UUID
    status: str
    cache_hit: bool = False
    content: ExplainerContentOut | None = None


class ExplainerJobResponse(BaseModel):
    """任务进度。"""

    job_id: uuid.UUID
    status: str
    error: str | None = None
    content: ExplainerContentOut | None = None


class ExplainerContentResponse(BaseModel):
    """直接取内容。"""

    content: ExplainerContentOut


class ExplainerFeedbackRequest(BaseModel):
    """「看懂了 / 还是不懂」。"""

    content_id: uuid.UUID
    understood: bool
    note: str | None = Field(default=None, max_length=500)


class ExplainerFeedbackResponse(BaseModel):
    """反馈已记录。"""

    feedback_id: uuid.UUID
    content_id: uuid.UUID
    understood: bool
    #: 累计「看懂了 / 还是不懂」次数，供后续画像与人工排查用。
    understood_count: int
    confused_count: int