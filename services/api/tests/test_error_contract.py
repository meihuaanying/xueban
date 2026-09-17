"""全局错误契约测试：{ code, message, trace_id }。"""

from __future__ import annotations

from httpx import AsyncClient


async def test_missing_token_returns_401_contract(client: AsyncClient) -> None:
    response = await client.get("/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_MISSING_TOKEN"
    assert body["message"]
    assert body["trace_id"] == response.headers["X-Trace-Id"]


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_TOKEN"


async def test_validation_error_contract(client: AsyncClient) -> None:
    response = await client.post("/v1/auth/register", json={"phone": "123", "password": "short"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["trace_id"]
    assert isinstance(body["details"], list)
    assert body["details"]


async def test_not_found_contract(client: AsyncClient) -> None:
    response = await client.get("/v1/not-exists")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "HTTP_404"
    assert body["trace_id"]


async def test_unsupported_type_contract(client: AsyncClient, admin_token: str) -> None:
    """storage 类型校验返回 415 且错误码稳定。"""
    from tests.conftest import auth_headers

    response = await client.post(
        "/v1/storage/presign-upload",
        json={"filename": "a.exe", "content_type": "application/x-msdownload", "size_bytes": 100},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 415
    assert response.json()["code"] == "STORAGE_UNSUPPORTED_TYPE"
