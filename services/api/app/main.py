"""学伴后端服务入口：应用工厂、中间件与全局错误契约。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.routes import (
    admin,
    analytics,
    auth,
    billing,
    coach,
    diagnosis,
    exam,
    grading,
    lessons,
    mistakes,
    parents,
    plan,
    practice,
    profile,
    report,
    review,
    safety,
    storage,
    sync,
    system,
    tools,
    tutor,
)
from app.config import settings
from app.db import create_engine, create_sessionmaker
from app.errors import AppError
from app.logging_setup import setup_logging
from app.middleware import RequestLogMiddleware, TraceIdMiddleware
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from app.services.safety_service import SafetyService
from app.services.storage_service import StorageService

logger = logging.getLogger("xueban.app")


def _trace_id(request: Request) -> str | None:
    """读取请求 trace_id。"""
    value = getattr(request.state, "trace_id", None)
    return str(value) if value else None


def _error_payload(code: str, message: str, trace_id: str | None, **extra: Any) -> dict[str, Any]:
    """统一错误响应体。"""
    payload: dict[str, Any] = {"code": code, "message": message, "trace_id": trace_id}
    payload.update(extra)
    return payload


def register_exception_handlers(application: FastAPI) -> None:
    """注册全局异常处理器（错误契约：code/message/trace_id）。"""

    @application.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(exc.code, exc.message, _trace_id(request)),
        )

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else None
        location = ".".join(str(part) for part in first.get("loc", [])) if first else "request"
        detail = first.get("msg", "") if first else ""
        details = [
            {"loc": list(item.get("loc", [])), "msg": item.get("msg"), "type": item.get("type")}
            for item in errors
        ]
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "VALIDATION_ERROR",
                f"参数校验失败：{location} {detail}".strip(),
                _trace_id(request),
                details=details,
            ),
        )

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                f"HTTP_{exc.status_code}", str(exc.detail), _trace_id(request)
            ),
        )

    @application.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "未处理异常",
            extra={"trace_id": _trace_id(request), "context": {"path": request.url.path}},
        )
        return JSONResponse(
            status_code=500,
            content=_error_payload(
                "INTERNAL_ERROR", "服务暂时不可用，请稍后重试", _trace_id(request)
            ),
        )


def init_app_state(application: FastAPI) -> None:
    """初始化应用级服务（测试可直接复用）。"""
    application.state.settings = settings
    application.state.observability = ObservabilityService(settings)
    application.state.storage = StorageService(settings)
    application.state.safety = SafetyService(settings)
    application.state.llm = LlmClient(settings, application.state.observability)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """启动/关闭钩子：数据库引擎与服务生命周期。"""
    engine = create_engine(settings.database_url)
    application.state.engine = engine
    application.state.sessionmaker = create_sessionmaker(engine)
    init_app_state(application)
    if settings.is_development and settings.dev_admin_phone:
        from app.services import auth_service

        async with application.state.sessionmaker() as session:
            await auth_service.ensure_dev_admin(
                session,
                phone=settings.dev_admin_phone,
                password=settings.dev_admin_password,
            )
            await session.commit()
    try:
        yield
    finally:
        await application.state.llm.aclose()
        application.state.observability.flush()
        await engine.dispose()


def create_app() -> FastAPI:
    """应用工厂。"""
    setup_logging()
    application = FastAPI(
        title="学伴 API",
        version=__version__,
        description="学伴（XueBan）AI 学习软件后端服务",
        lifespan=lifespan,
    )
    # 中间件顺序：先日志后 trace（trace_id 由 TraceIdMiddleware 注入，日志读取它）；
    # CORS 最后添加 → 位于最外层，优先处理浏览器预检请求。
    application.add_middleware(RequestLogMiddleware)
    application.add_middleware(TraceIdMiddleware)
    cors_origins = [item.strip() for item in settings.cors_allow_origins.split(",") if item.strip()]
    if cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_exception_handlers(application)

    application.include_router(system.router)
    application.include_router(auth.router)
    application.include_router(billing.router)
    application.include_router(profile.router)
    application.include_router(report.router)
    application.include_router(analytics.router)
    application.include_router(diagnosis.router)
    application.include_router(exam.router)
    application.include_router(grading.router)
    application.include_router(mistakes.router)
    application.include_router(parents.router)
    application.include_router(lessons.router)
    application.include_router(plan.router)
    application.include_router(practice.router)
    application.include_router(review.router)
    application.include_router(tutor.router)
    application.include_router(coach.router)
    application.include_router(tools.router)
    application.include_router(sync.router)
    application.include_router(storage.router)
    application.include_router(safety.router)
    application.include_router(admin.router)
    return application


app = create_app()
