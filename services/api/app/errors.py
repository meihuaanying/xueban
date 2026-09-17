"""统一业务错误类型：全局错误响应契约 { code, message, trace_id }。"""

from typing import Any


class AppError(Exception):
    """业务错误基类：携带 HTTP 状态码与稳定错误码。"""

    status_code: int = 400
    code: str = "APP_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class AuthError(AppError):
    """认证/授权类错误。"""

    status_code = 401
    code = "AUTH_UNAUTHORIZED"


class PermissionDeniedError(AppError):
    """权限不足。"""

    status_code = 403
    code = "PERMISSION_DENIED"


class NotFoundError(AppError):
    """资源不存在。"""

    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    """资源冲突（如重复注册）。"""

    status_code = 409
    code = "CONFLICT"


class UnsupportedMediaTypeError(AppError):
    """不支持的文件类型。"""

    status_code = 415
    code = "UNSUPPORTED_MEDIA_TYPE"


class FileTooLargeError(AppError):
    """文件超过大小限制。"""

    status_code = 413
    code = "FILE_TOO_LARGE"


class RateLimitedError(AppError):
    """触发限流。"""

    status_code = 429
    code = "RATE_LIMITED"


class BillingError(AppError):
    """订阅/计费类错误。"""

    status_code = 400
    code = "BILLING_ERROR"


class LlmError(AppError):
    """LLM 调用类错误。"""

    status_code = 502
    code = "LLM_ERROR"
