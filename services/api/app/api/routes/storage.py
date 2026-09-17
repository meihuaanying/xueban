"""对象存储路由：预签名直传/下载/删除。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import get_current_user
from app.errors import PermissionDeniedError
from app.models import User, UserRole
from app.schemas import (
    DeleteObjectResponse,
    PresignDownloadResponse,
    PresignUploadRequest,
    PresignUploadResponse,
)
from app.services.storage_service import StorageService, build_object_key, validate_upload

router = APIRouter(prefix="/v1/storage", tags=["storage"])


def _storage(request: Request) -> StorageService:
    """从应用状态获取存储服务。"""
    service: StorageService = request.app.state.storage
    return service


def _ensure_owner(user: User, key: str) -> None:
    """对象键归属校验（防止越权访问他人文件）。"""
    if user.role == UserRole.ADMIN:
        return
    if not key.startswith(f"u/{user.id}/"):
        raise PermissionDeniedError("无权访问该对象")


@router.post("/presign-upload", response_model=PresignUploadResponse, summary="申请上传凭证")
async def presign_upload(
    payload: PresignUploadRequest,
    request: Request,
    user: User = Depends(get_current_user),
) -> PresignUploadResponse:
    """校验类型/大小并返回预签名直传凭证。"""
    policy = validate_upload(payload.content_type, payload.size_bytes)
    service = _storage(request)
    key = build_object_key(user.id, policy.purpose, payload.filename, policy.content_type)
    presigned = await service.presign_upload(
        key=key, content_type=policy.content_type, max_bytes=policy.max_bytes
    )
    return PresignUploadResponse(
        key=key,
        url=str(presigned["url"]),
        fields={str(k): str(v) for k, v in presigned["fields"].items()},
        expires_in=request.app.state.settings.presign_expire_seconds,
        max_bytes=policy.max_bytes,
    )


@router.get("/presign-download", response_model=PresignDownloadResponse, summary="申请下载地址")
async def presign_download(
    request: Request,
    key: str = Query(min_length=1, max_length=512),
    user: User = Depends(get_current_user),
) -> PresignDownloadResponse:
    """返回预签名下载地址（仅限本人对象）。"""
    _ensure_owner(user, key)
    service = _storage(request)
    url = await service.presign_download(key=key)
    return PresignDownloadResponse(
        key=key, url=url, expires_in=request.app.state.settings.presign_expire_seconds
    )


@router.delete("/objects", response_model=DeleteObjectResponse, summary="删除对象")
async def delete_object(
    request: Request,
    key: str = Query(min_length=1, max_length=512),
    user: User = Depends(get_current_user),
) -> DeleteObjectResponse:
    """删除本人对象（管理员可删任意对象）。"""
    _ensure_owner(user, key)
    service = _storage(request)
    await service.delete_object(key=key)
    return DeleteObjectResponse(key=key)
