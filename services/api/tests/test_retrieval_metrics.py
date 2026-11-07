"""检索评测指标单测（吸收 DeepTutor kb eval 口径）。"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_SPEC = importlib.util.spec_from_file_location(
    "retrieval_metrics", _SCRIPTS / "retrieval_metrics.py"
)
assert _SPEC is not None and _SPEC.loader is not None
_metrics = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("retrieval_metrics", _metrics)
_SPEC.loader.exec_module(_metrics)


def test_precision_and_recall_at_k() -> None:
    ranked = ["a", "b", "c", "d", "e"]
    gold = {"a", "c"}
    assert _metrics.precision_at_k(ranked, gold, 5) == 0.4
    assert _metrics.recall_at_k(ranked, gold, 5) == 1.0
    assert _metrics.recall_at_k(ranked, gold, 1) == 0.5
    # 空输入与非法 k 都返回 0，不抛错
    assert _metrics.precision_at_k([], gold, 5) == 0.0
    assert _metrics.recall_at_k(ranked, set(), 5) == 0.0


def test_hit_at_k_matches_t24_semantics() -> None:
    """T2.4 的 recall@5 = 至少一个 gold 命中的 query 占比。"""
    assert _metrics.hit_at_k(["x", "y"], {"y"}, 2) == 1.0
    assert _metrics.hit_at_k(["x", "y"], {"z"}, 2) == 0.0


def test_mrr_and_ndcg() -> None:
    assert _metrics.mrr_at_k(["a", "b", "c"], {"b"}, 3) == 0.5
    assert _metrics.mrr_at_k(["a", "b", "c"], {"z"}, 3) == 0.0
    # 单个 gold 排第 1 → nDCG=1；排第 2 → 1/log2(3)
    assert _metrics.ndcg_at_k(["a"], {"a"}, 1) == 1.0
    expected = 1.0 / math.log2(3)
    assert _metrics.ndcg_at_k(["x", "a"], {"a"}, 2) == expected
    # gold 多于 k 时理想 DCG 按 k 截断
    assert _metrics.ndcg_at_k(["a", "b"], {"a", "b", "c"}, 2) == 1.0
    assert _metrics.ndcg_at_k([], {"a"}, 5) == 0.0
