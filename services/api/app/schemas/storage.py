"""对象存储契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PresignUploadRequest(BaseModel):
    """申请预签名直传。"""

    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=100)
    size_bytes: int = Field(gt=0)


class PresignUploadResponse(BaseModel):
    """预签名直传凭证。"""

    key: str
    url: str
    fields: dict[str, str]
    expires_in: int
    max_bytes: int


class PresignDownloadResponse(BaseModel):
    """预签名下载地址。"""

    key: str
    url: str
    expires_in: int


class DeleteObjectResponse(BaseModel):
    """删除结果。"""

    key: str
    deleted: bool = True
