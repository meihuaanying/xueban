"""检索评测脚本（T2.4）：30 问 recall@5 ≥ 90%。

用法（services/api 目录）：
    .venv/Scripts/python scripts/eval_retrieval.py
"""

from __future__ import annotations

import asyncio
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import database_session
from sqlalchemy import select

from app.config import settings
from app.models import KnowledgePoint, QuestionKnowledgePoint
from app.services.embeddings import get_embedding_provider
from app.services.rerank import get_rerank_provider
from app.services.retrieval_service import RetrievalService

QUERY_COUNT = 30
TOP_K = 5
RECALL_TARGET = 0.9


async def evaluate() -> tuple[float, list[str], int]:
    """执行评测，返回 (recall, 未命中说明, 查询数)。"""
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

        hits = 0
        misses: list[str] = []
        for kp in queries:
            results = await service.search_questions(session, kp.name, subject="math", top_k=TOP_K)
            result_ids = {item.question.id for item in results}
            if result_ids & ground_truth[kp.id]:
                hits += 1
            else:
                misses.append(kp.name)
        recall = hits / len(queries) if queries else 0.0
        return recall, misses, len(queries)


def main() -> int:
    """入口。"""
    recall, misses, count = asyncio.run(evaluate())
    print(
        f"检索评测：query 数={count} recall@{TOP_K}={recall:.1%} "
        f"（embedding={settings.embedding_provider} rerank={settings.rerank_provider}）"
    )
    for name in misses:
        print(f"  未命中：{name}")
    if recall < RECALL_TARGET:
        print(f"未达目标 {RECALL_TARGET:.0%}")
        return 1
    print("RECALL_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
