"""RAG 供应商契约测试：硅基流动 bge-m3 / bge-reranker（mock HTTP）。"""

from __future__ import annotations

from typing import Any

import pytest

from app.services import embeddings as embeddings_module
from app.services import rerank as rerank_module
from app.services.embeddings import EmbeddingError, SiliconFlowEmbeddingProvider
from app.services.rerank import RerankError, SiliconFlowRerankProvider


class FakeResponse:
    """假 HTTP 响应。"""

    def __init__(self, status_code: int, payload: Any, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self) -> Any:
        return self._payload


class FakeAsyncClient:
    """假 httpx 客户端。"""

    response: FakeResponse | None = None
    last_payload: dict[str, Any] | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def post(self, url: str, json: dict[str, Any], headers: dict[str, str]) -> FakeResponse:
        FakeAsyncClient.last_payload = json
        assert FakeAsyncClient.response is not None
        return FakeAsyncClient.response


async def test_siliconflow_embedding_success(monkeypatch: pytest.MonkeyPatch) -> None:
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    FakeAsyncClient.response = FakeResponse(
        200, {"data": [{"embedding": vector} for vector in vectors]}
    )
    monkeypatch.setattr(embeddings_module.httpx, "AsyncClient", FakeAsyncClient)
    provider = SiliconFlowEmbeddingProvider("sk-test", dims=3)
    result = await provider.embed(["甲", "乙"])
    assert result == vectors
    assert FakeAsyncClient.last_payload is not None
    assert FakeAsyncClient.last_payload["model"] == "BAAI/bge-m3"


async def test_siliconflow_embedding_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.response = FakeResponse(500, {}, text="server error")
    monkeypatch.setattr(embeddings_module.httpx, "AsyncClient", FakeAsyncClient)
    provider = SiliconFlowEmbeddingProvider("sk-test", dims=3)
    with pytest.raises(EmbeddingError):
        await provider.embed(["甲"])


async def test_siliconflow_embedding_bad_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.response = FakeResponse(200, {"data": []})
    monkeypatch.setattr(embeddings_module.httpx, "AsyncClient", FakeAsyncClient)
    provider = SiliconFlowEmbeddingProvider("sk-test", dims=3)
    with pytest.raises(EmbeddingError):
        await provider.embed(["甲"])


async def test_siliconflow_embedding_empty_input() -> None:
    provider = SiliconFlowEmbeddingProvider("sk-test")
    assert await provider.embed([]) == []


async def test_siliconflow_rerank_success(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.response = FakeResponse(
        200,
        {
            "results": [
                {"index": 1, "relevance_score": 0.2},
                {"index": 0, "relevance_score": 0.9},
            ]
        },
    )
    monkeypatch.setattr(rerank_module.httpx, "AsyncClient", FakeAsyncClient)
    provider = SiliconFlowRerankProvider("sk-test")
    results = await provider.rerank("二次函数", ["甲文档", "乙文档"])
    assert results[0] == (0, 0.9)
    assert results[1] == (1, 0.2)


async def test_siliconflow_rerank_requires_key() -> None:
    provider = SiliconFlowRerankProvider("")
    with pytest.raises(RerankError):
        await provider.rerank("查询", ["文档"])


async def test_siliconflow_rerank_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.response = FakeResponse(429, {}, text="rate limited")
    monkeypatch.setattr(rerank_module.httpx, "AsyncClient", FakeAsyncClient)
    provider = SiliconFlowRerankProvider("sk-test")
    with pytest.raises(RerankError):
        await provider.rerank("查询", ["文档"])


async def test_siliconflow_rerank_empty_documents() -> None:
    provider = SiliconFlowRerankProvider("sk-test")
    assert await provider.rerank("查询", []) == []


async def test_mock_rerank_orders_by_overlap() -> None:
    from app.services.rerank import MockRerankProvider

    provider = MockRerankProvider()
    results = await provider.rerank("二次函数 最值", ["二次函数的最值问题", "完全无关的内容"])
    assert results[0][0] == 0
    assert results[0][1] > results[1][1]
