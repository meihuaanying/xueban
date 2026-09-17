"""通用响应契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """全局错误响应：{ code, message, trace_id }。"""

    code: str = Field(description="稳定错误码，例如 AUTH_INVALID_CREDENTIALS")
    message: str = Field(description="面向用户的中文提示")
    trace_id: str | None = Field(default=None, description="链路追踪 ID（响应头同源）")


class OperationResult(BaseModel):
    """简单操作结果。"""

    ok: bool = True
