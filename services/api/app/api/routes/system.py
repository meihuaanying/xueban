"""系统路由：健康检查与服务信息。"""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import settings

router = APIRouter(tags=["system"])


@router.get("/healthz", summary="健康检查")
async def healthz() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok", "service": settings.app_name, "version": __version__}


@router.get("/v1/system/info", summary="服务信息")
async def system_info() -> dict[str, str]:
    """服务元信息。"""
    return {
        "service": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
    }
