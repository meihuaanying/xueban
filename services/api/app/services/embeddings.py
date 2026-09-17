"""Embedding 供应商：mock（词面哈希，离线可用）与硅基流动 bge-m3。"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx

from app.config import EMBEDDING_DIMS, Settings


class EmbeddingError(Exception):
    """向量化失败。"""


class EmbeddingProvider(Protocol):
    """向量化接口。"""

    name: str
    dims: int

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化。"""
        ...


def tokenize(text: str) -> list[str]:
    """中英混合分词：拉丁词 + 中文二元组。"""
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9]+", lowered)
    cjk_tokens: list[str] = []
    for sequence in re.findall(r"[\u4e00-\u9fff]+", lowered):
        if len(sequence) == 1:
            cjk_tokens.append(sequence)
        else:
            cjk_tokens.extend(sequence[i : i + 2] for i in range(len(sequence) - 1))
    return latin + cjk_tokens


class MockEmbeddingProvider:
    """本地词面哈希向量（带符号哈希，L2 归一化）。

    用途：离线开发与词面召回验证；语义检索质量以真实 bge-m3 为准。
    """

    name = "mock"

    def __init__(self, dims: int = EMBEDDING_DIMS) -> None:
        self.dims = dims

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dims
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dims
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]


class SiliconFlowEmbeddingProvider:
    """硅基流动 bge-m3（OpenAI 兼容 /embeddings）。"""

    name = "siliconflow"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "BAAI/bge-m3",
        base_url: str = "https://api.siliconflow.cn/v1",
        dims: int = EMBEDDING_DIMS,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.dims = dims
        self.timeout_seconds = timeout_seconds

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            raise EmbeddingError("硅基流动 API Key 未配置（SILICONFLOW_API_KEY）")
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                json={"model": self.model, "input": texts},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        if response.status_code >= 400:
            raise EmbeddingError(
                f"Embedding 接口错误（{response.status_code}）：{response.text[:200]}"
            )
        payload = response.json()
        items = payload.get("data")
        if not isinstance(items, list) or len(items) != len(texts):
            raise EmbeddingError("Embedding 返回结构与请求不匹配")
        vectors: list[list[float]] = []
        for item in items:
            embedding = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(embedding, list):
                raise EmbeddingError("Embedding 返回缺少向量")
            vectors.append([float(value) for value in embedding])
        return vectors


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """按配置选择向量化供应商。"""
    if settings.embedding_provider == "siliconflow":
        return SiliconFlowEmbeddingProvider(settings.siliconflow_api_key)
    return MockEmbeddingProvider()
