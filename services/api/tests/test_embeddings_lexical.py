"""词面向量（lexical）与余弦相似度测试（P1 / §6.2 去重）。

这些用例锁住三件事：
1. 同一文本向量完全确定（判重与入库必须可复现，不能每次跑出不同结论）；
2. 近重复题干相似度确实 >0.95（§6.2 的判重阈值要有意义）；
3. 不同题干相似度明显更低（不能把阈值调成"什么都能判重"）。
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services.embeddings import (
    LexicalEmbeddingProvider,
    MockEmbeddingProvider,
    cosine_similarity,
    get_embedding_provider,
)

DEDUP_THRESHOLD = 0.95


def _settings(provider: str) -> Settings:
    return Settings(embedding_provider=provider)


# ---------------------------------------------------------------- 工厂


def test_factory_defaults_to_mock() -> None:
    assert get_embedding_provider(_settings("mock")).name == "mock"


def test_factory_selects_lexical() -> None:
    assert get_embedding_provider(_settings("lexical")).name == "lexical"


def test_factory_selects_siliconflow() -> None:
    assert get_embedding_provider(_settings("siliconflow")).name == "siliconflow"


def test_factory_unknown_falls_back_to_mock() -> None:
    assert get_embedding_provider(_settings("不存在的供应商")).name == "mock"


# ---------------------------------------------------------------- 确定性


async def test_lexical_is_deterministic_and_normalized() -> None:
    provider = LexicalEmbeddingProvider(dims=256)
    first = await provider.embed(["20 以内进位加法"])
    second = await provider.embed(["20 以内进位加法"])
    assert first == second, "同文本必须得到完全相同的向量，否则判重不可复现"
    norm = sum(value * value for value in first[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-6


async def test_lexical_empty_text_is_zero_vector() -> None:
    provider = LexicalEmbeddingProvider(dims=64)
    [vector] = await provider.embed(["   "])
    assert vector == [0.0] * 64
    assert cosine_similarity(vector, vector) == 0.0


async def test_lexical_batch_preserves_order_and_length() -> None:
    provider = LexicalEmbeddingProvider(dims=128)
    texts = ["认识钟表", "整时和半时", "20 以内退位减法"]
    vectors = await provider.embed(texts)
    assert len(vectors) == len(texts)
    for text, vector in zip(texts, vectors, strict=True):
        assert (await provider.embed([text]))[0] == vector


# ---------------------------------------------------------------- 判重语义


async def test_near_duplicate_stems_exceed_threshold() -> None:
    """同一考点的近重复题干必须能被 0.95 阈值抓到。"""
    provider = LexicalEmbeddingProvider(dims=2048)
    original = "小明有 8 个苹果，又买来 5 个，小明现在有多少个苹果？"
    duplicate = "小明有8个苹果，又买来5个，小明现在有多少个苹果"
    [left, right] = await provider.embed([original, duplicate])
    assert cosine_similarity(left, right) > DEDUP_THRESHOLD


async def test_distinct_stems_stay_below_threshold() -> None:
    """不同题目不能被误判为重复。"""
    provider = LexicalEmbeddingProvider(dims=2048)
    [left, right] = await provider.embed(
        [
            "20 以内进位加法：9 + 5 = ?",
            "钟面上分针指向 6，时针指向 3，现在是几时？",
        ]
    )
    assert cosine_similarity(left, right) < DEDUP_THRESHOLD


async def test_identical_stems_are_perfectly_similar() -> None:
    provider = LexicalEmbeddingProvider(dims=512)
    [left, right] = await provider.embed(["同样的题干", "同样的题干"])
    assert cosine_similarity(left, right) == pytest.approx(1.0, abs=1e-9)


async def test_repeated_token_not_dominant() -> None:
    """次线性 TF：同一词重复 10 次不应让相似度冲到 1.0 以外或压倒其他信号。"""
    provider = LexicalEmbeddingProvider(dims=1024)
    [left, right] = await provider.embed(
        ["苹果 苹果 苹果 苹果 苹果 苹果 苹果 苹果 苹果 苹果 香蕉", "苹果 香蕉"]
    )
    assert 0.0 < cosine_similarity(left, right) < 1.0


async def test_lexical_distinguishes_from_mock() -> None:
    """lexical 与 mock 确实不是同一个东西换名字。"""
    text = "20 以内进位加法：9 + 5 = ?"
    lexical = LexicalEmbeddingProvider(dims=2048)
    mock = MockEmbeddingProvider(dims=2048)
    [lex_a] = await lexical.embed([text])
    [mock_a] = await mock.embed([text])
    assert lexical.name == "lexical"
    assert mock.name == "mock"
    assert lex_a != mock_a


# ---------------------------------------------------------------- 余弦工具


def test_cosine_mismatched_dims_returns_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_cosine_orthogonal_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_with_zero_vector_returns_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
