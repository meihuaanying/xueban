"""RAG 检索测试（T2.4）：流水线正确性与召回评测。"""

from __future__ import annotations

import random
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.data.demo_questions import generate_math_records
from app.models import (
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
)
from app.services.embeddings import (
    EmbeddingError,
    MockEmbeddingProvider,
    SiliconFlowEmbeddingProvider,
    get_embedding_provider,
)
from app.services.import_service import import_questions
from app.services.rerank import MockRerankProvider, get_rerank_provider
from app.services.retrieval_service import RetrievalService


def _service() -> RetrievalService:
    return RetrievalService(MockEmbeddingProvider(), MockRerankProvider())


async def test_retrieval_finds_relevant_question(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    from scripts.seed_knowledge_graph import seed

    await seed()
    async with sessionmaker() as session:
        kp = (
            await session.execute(
                select(KnowledgePoint).where(KnowledgePoint.code == "math.junior.c01.t01")
            )
        ).scalar_one()
        questions = [
            Question(
                subject="math",
                stage="junior",
                qtype=QuestionType.FILL,
                stem=f"[{kp.name}] 计算：-3 + 5 = ?",
                answer="2",
                analysis="用数轴计算。",
                status=QuestionStatus.PUBLISHED,
            ),
            Question(
                subject="math",
                stage="junior",
                qtype=QuestionType.FILL,
                stem="[轴对称的性质] 说明轴对称图形的对应点连线性质。",
                answer="垂直平分",
                analysis="对应点连线被对称轴垂直平分。",
                status=QuestionStatus.PUBLISHED,
            ),
        ]
        session.add_all(questions)
        await session.flush()
        service = _service()
        indexed = await service.index_questions(session, questions)
        await session.commit()
        assert indexed == 2

        results = await service.search_questions(session, kp.name, subject="math", top_k=1)
    assert results, "应检索到结果"
    assert results[0].question.stem.startswith(f"[{kp.name}]")


async def test_search_returns_empty_without_embeddings(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with sessionmaker() as session:
        service = _service()
        results = await service.search_questions(session, "不存在的内容", subject="math", top_k=3)
    assert results == []


def test_embedding_provider_factory_defaults_to_mock() -> None:
    provider = get_embedding_provider(settings)
    assert provider.name == "mock"


def test_rerank_factory_defaults_to_mock() -> None:
    provider = get_rerank_provider(settings)
    assert provider.name == "mock"


async def test_siliconflow_embedding_requires_key() -> None:
    provider = SiliconFlowEmbeddingProvider("")
    with pytest.raises(EmbeddingError):
        await provider.embed(["测试"])


async def test_mock_embedding_is_deterministic_and_normalized() -> None:
    provider = MockEmbeddingProvider(dims=64)
    first = await provider.embed(["二次函数的最值"])
    second = await provider.embed(["二次函数的最值"])
    assert first == second
    norm = sum(value * value for value in first[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-6


async def test_recall_on_demo_corpus(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """演示语料 recall@5 ≥ 90%（词面召回，语义召回待真实 bge-m3）。"""
    from scripts.seed_knowledge_graph import seed

    await seed()
    records = generate_math_records(per_kp=1)
    rows = [(index, dict(record)) for index, record in enumerate(records, start=1)]
    async with sessionmaker() as session:
        report = await import_questions(session, rows)
        await session.commit()
        assert report.ok and report.imported >= 80

        pending = (
            (
                await session.execute(
                    select(Question).where(
                        Question.embedding.is_(None),
                        Question.status == QuestionStatus.PUBLISHED,
                    )
                )
            )
            .scalars()
            .all()
        )
        service = _service()
        await service.index_questions(session, list(pending))
        await session.commit()

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
        rng = random.Random(7)
        rng.shuffle(candidates)
        queries = candidates[:20]
        hits = 0
        for kp in queries:
            results = await service.search_questions(session, kp.name, subject="math", top_k=5)
            if {item.question.id for item in results} & ground_truth[kp.id]:
                hits += 1
    recall = hits / len(queries)
    assert recall >= 0.9, f"recall@5={recall:.1%} 未达标"


async def test_question_embedding_column_roundtrip(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with sessionmaker() as session:
        question = Question(
            subject="math",
            stage="junior",
            qtype=QuestionType.FILL,
            stem="[测试] 1 + 1 = ?",
            answer="2",
            analysis="基础加法。",
            status=QuestionStatus.PUBLISHED,
        )
        session.add(question)
        await session.flush()
        service = _service()
        await service.index_questions(session, [question])
        await session.commit()
        stored = await session.scalar(
            select(func.count()).select_from(Question).where(Question.embedding.is_not(None))
        )
    assert stored == 1
