"""Rerank 供应商：mock（词面重叠）与硅基流动 bge-reranker-v2-m3。"""

from __future__ import annotations

from typing import Protocol

import httpx

from app.config import Settings
from app.services.embeddings import tokenize


class RerankError(Exception):
    """重排失败。"""


class RerankProvider(Protocol):
    """重排接口：返回 (候选索引, 分数)，按分数降序。"""

    name: str

    async def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        """对候选文档重排。"""
        ...


class MockRerankProvider:
    """词面 Jaccard 相似度重排（离线）。"""

    name = "mock"

    async def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        query_tokens = set(tokenize(query))
        scored: list[tuple[int, float]] = []
        for index, document in enumerate(documents):
            document_tokens = set(tokenize(document))
            if not query_tokens or not document_tokens:
                score = 0.0
            else:
                score = len(query_tokens & document_tokens) / len(query_tokens | document_tokens)
            scored.append((index, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored


class SiliconFlowRerankProvider:
    """硅基流动 bge-reranker-v2-m3。"""

    name = "siliconflow"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "BAAI/bge-reranker-v2-m3",
        base_url: str = "https://api.siliconflow.cn/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        if not documents:
            return []
        if not self.api_key:
            raise RerankError("硅基流动 API Key 未配置（SILICONFLOW_API_KEY）")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/rerank",
                json={
                    "model": self.model,
                    "query": query,
                    "documents": documents,
                    "top_n": len(documents),
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        if response.status_code >= 400:
            raise RerankError(f"Rerank 接口错误（{response.status_code}）：{response.text[:200]}")
        payload = response.json()
        items = payload.get("results")
        if not isinstance(items, list):
            raise RerankError("Rerank 返回结构异常")
        results: list[tuple[int, float]] = []
        for item in items:
            if isinstance(item, dict):
                results.append((int(item.get("index", 0)), float(item.get("relevance_score", 0.0))))
        results.sort(key=lambda item: item[1], reverse=True)
        return results


def get_rerank_provider(settings: Settings) -> RerankProvider:
    """按配置选择重排供应商。"""
    if settings.rerank_provider == "siliconflow":
        return SiliconFlowRerankProvider(settings.siliconflow_api_key)
    return MockRerankProvider()
