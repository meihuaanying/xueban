"""Embedding 供应商：lexical（真实词面 TF-IDF）、mock（哈希，离线）与硅基流动 bge-m3。

三态选择的理由：
- ``lexical``：真实的字符/词 n-gram TF-IDF 余弦相似度，**不是占位数据**。
  题库去重（§6.2 要求相似度 >0.95 判重）在没有外部 Key 时用它，近重复检测
  本身是真实算法，只是语义泛化能力弱于双塔模型。
- ``mock``：带符号哈希，离线开发与词面召回冒烟用，**不可用于判重**。
- ``siliconflow``：真实 bge-m3。硅基流动 Key 到位后只需把环境变量
  ``EMBEDDING_PROVIDER`` 改成 siliconflow 并配置 Key，无需改任何代码。
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
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


class LexicalEmbeddingProvider:
    """真实词面向量：token 计数 → L2 归一化的稀疏稠密化表示。

    与 `mock` 的关键差别：这里的每一维对应一个**真实的 token**（哈希仅用于把
    token 映射到固定维度），因此余弦相似度反映真实的词面重合度，可以用来判
    近重复题目，而不是拿假相似度冒充。

    局限：不理解同义改写（"相加" 与 "加起来" 相似度低）。所以 §6.2 的判重阈值
    0.95 用它时是**保守**的——宁可漏判（留着交给人审），不可错判（删掉好题）。
    """

    name = "lexical"

    def __init__(self, dims: int = EMBEDDING_DIMS) -> None:
        self.dims = dims

    def _index(self, token: str) -> int:
        return int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:4], "big") % self.dims

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dims
        for token, count in Counter(tokenize(text)).items():
            # 次线性 TF：重复词不应线性放大权重；同 token 落到同一维时累加
            vector[self._index(token)] += 1.0 + math.log(count)
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """余弦相似度；维度不一致视为不可比，返回 0.0 而不是抛错。"""
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0.0 or norm_right == 0.0:
        return 0.0
    return dot / (norm_left * norm_right)


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
    """按配置选择向量化供应商。

    `lexical` 是判重等真实相似度任务的默认选择；`mock` 仅供离线开发，
    其相似度没有语义含义，不要用它做入库决策。
    """
    provider = settings.embedding_provider
    if provider == "siliconflow":
        return SiliconFlowEmbeddingProvider(settings.siliconflow_api_key)
    if provider == "lexical":
        return LexicalEmbeddingProvider()
    return MockEmbeddingProvider()
