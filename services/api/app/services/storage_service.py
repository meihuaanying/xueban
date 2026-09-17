"""对象存储服务：MinIO（S3 兼容）预签名直传 + 类型/大小白名单。"""

from __future__ import annotations

import asyncio
import mimetypes
import uuid
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config as BotoConfig

from app.config import Settings
from app.errors import FileTooLargeError, UnsupportedMediaTypeError


@dataclass(frozen=True, slots=True)
class UploadPolicy:
    """上传白名单策略。"""

    content_type: str
    max_bytes: int
    purpose: str


MB = 1024 * 1024

ALLOWED_UPLOADS: dict[str, tuple[int, str]] = {
    # content_type -> (最大字节数, 用途)
    "image/jpeg": (10 * MB, "image"),
    "image/png": (10 * MB, "image"),
    "image/webp": (10 * MB, "image"),
    "image/heic": (10 * MB, "image"),
    "application/pdf": (50 * MB, "document"),
    "audio/mpeg": (20 * MB, "audio"),
    "audio/mp4": (20 * MB, "audio"),
    "audio/wav": (20 * MB, "audio"),
    "audio/x-m4a": (20 * MB, "audio"),
}


def validate_upload(content_type: str, size_bytes: int) -> UploadPolicy:
    """校验上传类型与大小；非法类型 415，超限 413。"""
    normalized = content_type.split(";")[0].strip().lower()
    entry = ALLOWED_UPLOADS.get(normalized)
    if entry is None:
        raise UnsupportedMediaTypeError(
            f"不支持的文件类型：{content_type}", code="STORAGE_UNSUPPORTED_TYPE"
        )
    max_bytes, purpose = entry
    if size_bytes <= 0:
        raise FileTooLargeError("文件大小非法", code="STORAGE_INVALID_SIZE")
    if size_bytes > max_bytes:
        raise FileTooLargeError(
            f"文件超过大小限制（{max_bytes // MB}MB）", code="STORAGE_FILE_TOO_LARGE"
        )
    return UploadPolicy(content_type=normalized, max_bytes=max_bytes, purpose=purpose)


def _guess_extension(content_type: str, filename: str) -> str:
    """推断对象键后缀（优先文件名，其次 MIME 映射）。"""
    if "." in filename:
        suffix = "." + filename.rsplit(".", 1)[-1].lower()
        if len(suffix) <= 6 and suffix.isascii():
            return suffix
    extension = mimetypes.guess_extension(content_type) or ""
    return ".jpg" if extension == ".jpe" else extension


def build_object_key(user_id: uuid.UUID, purpose: str, filename: str, content_type: str) -> str:
    """生成用户隔离的对象键：u/<user_id>/<purpose>/<uuid><ext>。"""
    extension = _guess_extension(content_type, filename)
    return f"u/{user_id}/{purpose}/{uuid.uuid4().hex}{extension}"


class StorageService:
    """MinIO/S3 操作封装（boto3 同步调用放入线程池）。"""

    def __init__(self, settings: Settings, *, client: Any = None) -> None:
        self._settings = settings
        if client is not None:
            self._client: Any = client
        else:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region,
                config=BotoConfig(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                    retries={"max_attempts": 2},
                ),
            )

    @property
    def bucket(self) -> str:
        """当前桶名。"""
        return self._settings.s3_bucket

    async def ensure_bucket(self) -> None:
        """确保桶存在（本地开发幂等）。"""

        def _ensure() -> None:
            existing = {item["Name"] for item in self._client.list_buckets().get("Buckets", [])}
            if self.bucket not in existing:
                self._client.create_bucket(Bucket=self.bucket)

        await asyncio.to_thread(_ensure)

    async def presign_upload(
        self,
        *,
        key: str,
        content_type: str,
        max_bytes: int,
    ) -> dict[str, Any]:
        """生成预签名 POST 直传（含 content-length-range 条件，服务端强制大小上限）。"""

        def _presign() -> dict[str, Any]:
            result: dict[str, Any] = self._client.generate_presigned_post(
                Bucket=self.bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, max_bytes],
                ],
                ExpiresIn=self._settings.presign_expire_seconds,
            )
            return result

        return await asyncio.to_thread(_presign)

    async def presign_download(self, *, key: str) -> str:
        """生成预签名下载地址。"""

        def _presign() -> str:
            url: str = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=self._settings.presign_expire_seconds,
            )
            return url

        return await asyncio.to_thread(_presign)

    async def download_bytes(self, *, key: str) -> bytes:
        """下载对象字节（F-37 文档入库）。"""

        def _get() -> bytes:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"].read()
            return bytes(body)

        return await asyncio.to_thread(_get)

    async def upload_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        """服务端直接上传字节（用于 TTS 音频等生成物）。"""

        def _put() -> None:
            self._client.put_object(
                Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
            )

        await asyncio.to_thread(_put)

    async def delete_object(self, *, key: str) -> None:
        """删除对象。"""

        def _delete() -> None:
            self._client.delete_object(Bucket=self.bucket, Key=key)

        await asyncio.to_thread(_delete)
