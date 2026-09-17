"""健康检查与系统接口测试。"""

from __future__ import annotations

from httpx import AsyncClient


async def test_healthz_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "xueban-api"
    assert body["version"] == "0.1.0"


async def test_openapi_available(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "学伴 API"


async def test_docs_available(client: AsyncClient) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


async def test_system_info(client: AsyncClient) -> None:
    response = await client.get("/v1/system/info")
    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "testing"


async def test_trace_id_header_present(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.headers.get("X-Trace-Id")


async def test_trace_id_reuses_upstream(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"X-Trace-Id": "trace-from-upstream"})
    assert response.headers["X-Trace-Id"] == "trace-from-upstream"
