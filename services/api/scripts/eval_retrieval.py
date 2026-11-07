"""检索评测脚本（T2.4）：30 问 recall@5 ≥ 90%。

指标口径吸收 DeepTutor `kb eval`（Recall@k / Precision@k / MRR / nDCG@k，
全部为排序结果的纯函数）；T2.4 的「recall@5」即这里的 hit_rate@5（至少一个
gold 命中的 query 占比），门禁语义不变。

用法（services/api 目录）：
    .venv/Scripts/python scripts/eval_retrieval.py
"""

from __future__ import annotations

import asyncio
import random
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import database_session
from retrieval_metrics import (
    hit_at_k,
    mean,
    mrr_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from sqlalchemy import select

from app.config import settings
from app.models import KnowledgePoint, QuestionKnowledgePoint
from app.services.embeddings import get_embedding_provider
from app.services.rerank import get_rerank_provider
from app.services.retrieval_service import RetrievalService

QUERY_COUNT = 30
TOP_K = 5
RECALL_TARGET = 0.9


@dataclass(slots=True)
class EvalReport:
    """一次评测的聚合指标与未命中明细。"""

    queries: int
    hit_rate: float
    recall: float
    precision: float
    mrr: float
    ndcg: float
    misses: list[str]


async def evaluate() -> EvalReport:
    """执行评测，返回聚合指标；每问 gold = 该知识点名下全部 PUBLISHED 题目。"""
    async with database_session() as session:
        service = RetrievalService(
            get_embedding_provider(settings),
            get_rerank_provider(settings),
            rerank_enabled=settings.rerank_provider != "none",
        )
        knowledge_points = (
            (
                await session.execute(
                    select(KnowledgePoint).where(
                        KnowledgePoint.code.like("math.junior.%"),
                        KnowledgePoint.code.not_like("%.basic"),
                        KnowledgePoint.code.not_like("%.apply"),
                    )
                )
            )
            .scalars()
            .all()
        )
        kp_ids = {kp.id for kp in knowledge_points}
        pairs = (
            await session.execute(
                select(
                    QuestionKnowledgePoint.knowledge_point_id,
                    QuestionKnowledgePoint.question_id,
                )
            )
        ).all()
        ground_truth: dict[uuid.UUID, set[uuid.UUID]] = {}
        for kp_id, question_id in pairs:
            if kp_id in kp_ids:
                ground_truth.setdefault(kp_id, set()).add(question_id)

        candidates = [kp for kp in knowledge_points if ground_truth.get(kp.id)]
        rng = random.Random(42)
        rng.shuffle(candidates)
        queries = candidates[:QUERY_COUNT]

        misses: list[str] = []
        hit_rates: list[float] = []
        recalls: list[float] = []
        precisions: list[float] = []
        mrrs: list[float] = []
        ndcgs: list[float] = []
        for kp in queries:
            results = await service.search_questions(session, kp.name, subject="math", top_k=TOP_K)
            ranked = [str(item.question.id) for item in results]
            gold = {str(item) for item in ground_truth[kp.id]}
            hit_rates.append(hit_at_k(ranked, gold, TOP_K))
            recalls.append(recall_at_k(ranked, gold, TOP_K))
            precisions.append(precision_at_k(ranked, gold, TOP_K))
            mrrs.append(mrr_at_k(ranked, gold, TOP_K))
            ndcgs.append(ndcg_at_k(ranked, gold, TOP_K))
            if hit_rates[-1] == 0.0:
                misses.append(kp.name)
        return EvalReport(
            queries=len(queries),
            hit_rate=mean(hit_rates),
            recall=mean(recalls),
            precision=mean(precisions),
            mrr=mean(mrrs),
            ndcg=mean(ndcgs),
            misses=misses,
        )


def main() -> int:
    """入口。"""
    report = asyncio.run(evaluate())
    print(
        f"检索评测：query 数={report.queries} "
        f"hit_rate@{TOP_K}={report.hit_rate:.1%} recall@{TOP_K}={report.recall:.1%} "
        f"precision@{TOP_K}={report.precision:.1%} MRR@{TOP_K}={report.mrr:.3f} "
        f"nDCG@{TOP_K}={report.ndcg:.3f} "
        f"（embedding={settings.embedding_provider} rerank={settings.rerank_provider}）"
    )
    for name in report.misses:
        print(f"  未命中：{name}")
    if report.hit_rate < RECALL_TARGET:
        print(f"未达目标 {RECALL_TARGET:.0%}")
        return 1
    print("RECALL_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
