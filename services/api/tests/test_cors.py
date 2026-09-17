"""CORS 预检与跨域响应头测试（官网直连注册链路）。"""

from __future__ import annotations

from httpx import AsyncClient

ORIGIN = "http://localhost:3000"


async def test_preflight_allows_web_origin(client: AsyncClient) -> None:
    response = await client.options(
        "/v1/auth/register",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "POST" in response.headers["access-control-allow-methods"]


async def test_simple_request_has_allow_origin(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"Origin": ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


async def test_unknown_origin_not_allowed(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"Origin": "http://evil.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
