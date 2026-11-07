"""检索评测指标（吸收 DeepTutor kb eval 口径）。

DeepTutor 的 `kb eval` 报告 Recall@k / Precision@k / MRR / nDCG@k，且全部是
对排序结果的纯函数、无需模型裁判。本模块实现同一组指标（二元相关），
供 `eval_retrieval.py` 与测试复用。
"""

from __future__ import annotations

import math


def precision_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    """前 k 个结果中命中 gold 的比例；k<=0 或无结果返回 0。"""
    if k <= 0 or not ranked:
        return 0.0
    top = ranked[:k]
    hits = sum(1 for item in top if item in gold)
    return hits / len(top)


def recall_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    """gold 中被前 k 个结果覆盖的比例；gold 为空返回 0。"""
    if not gold:
        return 0.0
    top = set(ranked[:k]) if k > 0 else set()
    return len(top & gold) / len(gold)


def hit_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    """前 k 个结果是否至少命中一个 gold（T2.4 的旧 recall 口径）。"""
    if not gold or k <= 0:
        return 0.0
    return 1.0 if set(ranked[:k]) & gold else 0.0


def mrr_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    """首个 gold 命中位次的倒数；未命中为 0。"""
    if not gold or k <= 0:
        return 0.0
    for position, item in enumerate(ranked[:k], start=1):
        if item in gold:
            return 1.0 / position
    return 0.0


def ndcg_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    """二元相关 nDCG@k；gold 为空返回 0。"""
    if not gold or k <= 0:
        return 0.0
    dcg = sum(
        1.0 / math.log2(position + 1)
        for position, item in enumerate(ranked[:k], start=1)
        if item in gold
    )
    ideal_hits = min(len(gold), k)
    idcg = sum(1.0 / math.log2(position + 1) for position in range(1, ideal_hits + 1))
    if idcg <= 0:
        return 0.0
    return dcg / idcg


def mean(values: list[float]) -> float:
    """空列表返回 0 的均值。"""
    return sum(values) / len(values) if values else 0.0
