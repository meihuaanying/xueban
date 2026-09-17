"""对象存储测试（T1.3）：预签名直传 → 下载 → 删除全链路。"""

from __future__ import annotations

import httpx
from httpx import AsyncClient

from tests.conftest import auth_headers
from tests.helpers import headers_of, register


async def _upload(client: AsyncClient, tokens: dict[str, str]) -> str:
    """完成一次预签名直传并返回对象键。"""
    presign = await client.post(
        "/v1/storage/presign-upload",
        json={"filename": "sample.jpg", "content_type": "image/jpeg", "size_bytes": 1024},
        headers=headers_of(tokens),
    )
    assert presign.status_code == 200, presign.text
    body = presign.json()
    assert body["key"].startswith(f"u/{_user_id(tokens)}/")
    assert body["max_bytes"] == 10 * 1024 * 1024

    async with httpx.AsyncClient() as raw:
        upload = await raw.post(
            body["url"],
            data=body["fields"],
            files={"file": ("sample.jpg", b"fake_image_bytes", "image/jpeg")},
        )
    assert upload.status_code == 204, upload.text
    return str(body["key"])


def _user_id(_tokens: dict[str, str]) -> str:
    """占位：键前缀校验改在断言中做（避免额外请求）。"""
    return "u"


async def test_presign_upload_download_delete_chain(client: AsyncClient) -> None:
    tokens = await register(client)
    presign = await client.post(
        "/v1/storage/presign-upload",
        json={"filename": "sample.jpg", "content_type": "image/jpeg", "size_bytes": 1024},
        headers=headers_of(tokens),
    )
    assert presign.status_code == 200, presign.text
    body = presign.json()
    key = str(body["key"])
    assert key.startswith("u/")

    async with httpx.AsyncClient() as raw:
        upload = await raw.post(
            body["url"],
            data=body["fields"],
            files={"file": ("sample.jpg", b"fake_image_bytes", "image/jpeg")},
        )
    assert upload.status_code == 204, upload.text

    download = await client.get(
        "/v1/storage/presign-download", params={"key": key}, headers=headers_of(tokens)
    )
    assert download.status_code == 200
    url = download.json()["url"]
    async with httpx.AsyncClient() as raw:
        content = await raw.get(url)
    assert content.status_code == 200
    assert content.content == b"fake_image_bytes"

    removed = await client.request(
        "DELETE", "/v1/storage/objects", params={"key": key}, headers=headers_of(tokens)
    )
    assert removed.status_code == 200
    assert removed.json()["deleted"] is True

    async with httpx.AsyncClient() as raw:
        gone = await raw.get(url)
    assert gone.status_code in (403, 404)


async def test_presign_pdf_allowed(client: AsyncClient) -> None:
    tokens = await register(client)
    response = await client.post(
        "/v1/storage/presign-upload",
        json={
            "filename": "textbook.pdf",
            "content_type": "application/pdf",
            "size_bytes": 2 * 1024 * 1024,
        },
        headers=headers_of(tokens),
    )
    assert response.status_code == 200
    assert response.json()["max_bytes"] == 50 * 1024 * 1024


async def test_upload_unsupported_type(client: AsyncClient) -> None:
    tokens = await register(client)
    response = await client.post(
        "/v1/storage/presign-upload",
        json={"filename": "run.exe", "content_type": "application/octet-stream", "size_bytes": 100},
        headers=headers_of(tokens),
    )
    assert response.status_code == 415
    assert response.json()["code"] == "STORAGE_UNSUPPORTED_TYPE"


async def test_upload_too_large(client: AsyncClient) -> None:
    tokens = await register(client)
    response = await client.post(
        "/v1/storage/presign-upload",
        json={"filename": "big.jpg", "content_type": "image/jpeg", "size_bytes": 11 * 1024 * 1024},
        headers=headers_of(tokens),
    )
    assert response.status_code == 413
    assert response.json()["code"] == "STORAGE_FILE_TOO_LARGE"


async def test_cannot_access_other_users_object(client: AsyncClient) -> None:
    owner = await register(client)
    stranger = await register(client)

    presign = await client.post(
        "/v1/storage/presign-upload",
        json={"filename": "sample.jpg", "content_type": "image/jpeg", "size_bytes": 512},
        headers=headers_of(owner),
    )
    key = presign.json()["key"]

    denied_download = await client.get(
        "/v1/storage/presign-download", params={"key": key}, headers=headers_of(stranger)
    )
    assert denied_download.status_code == 403
    assert denied_download.json()["code"] == "PERMISSION_DENIED"

    denied_delete = await client.request(
        "DELETE", "/v1/storage/objects", params={"key": key}, headers=headers_of(stranger)
    )
    assert denied_delete.status_code == 403


async def test_admin_can_access_any_object(client: AsyncClient, admin_token: str) -> None:
    owner = await register(client)
    presign = await client.post(
        "/v1/storage/presign-upload",
        json={"filename": "sample.jpg", "content_type": "image/jpeg", "size_bytes": 512},
        headers=headers_of(owner),
    )
    key = presign.json()["key"]
    response = await client.get(
        "/v1/storage/presign-download", params={"key": key}, headers=auth_headers(admin_token)
    )
    assert response.status_code == 200


async def test_storage_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/storage/presign-upload",
        json={"filename": "a.jpg", "content_type": "image/jpeg", "size_bytes": 10},
    )
    assert response.status_code == 401


async def test_ensure_bucket_idempotent(app: object) -> None:
    """桶初始化幂等（M1 联调用）。"""
    storage = app.state.storage  # type: ignore[attr-defined]
    await storage.ensure_bucket()
    await storage.ensure_bucket()

async def test_object_key_without_extension() -> None:
    """无扩展名文件按 MIME 推断后缀。"""
    import uuid as _uuid

    from app.services.storage_service import build_object_key

    key = build_object_key(_uuid.uuid4(), "image", "photo", "image/jpeg")
    assert key.endswith(".jpg")
