"""RAG 检索服务：题目向量化 + pgvector 相似检索 + 重排。"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Question, QuestionStatus
from app.services.embeddings import EmbeddingProvider
from app.services.rerank import RerankProvider

logger = logging.getLogger("xueban.retrieval")


@dataclass(slots=True)
class RetrievedQuestion:
    """检索结果条目。"""

    question: Question
    score: float


class RetrievalService:
    """题目检索：embedding 召回 + 可选 rerank 精排。"""

    def __init__(
        self,
        embedder: EmbeddingProvider,
        reranker: RerankProvider | None = None,
        *,
        rerank_enabled: bool = True,
    ) -> None:
        self._embedder = embedder
        self._reranker = reranker
        self._rerank_enabled = rerank_enabled and reranker is not None

    @staticmethod
    def _index_text(question: Question) -> str:
        """索引文本：学科 + 题干（题干含知识点关键词时可被词面召回）。"""
        return f"{question.subject} {question.stem}"

    async def index_questions(self, session: AsyncSession, questions: Sequence[Question]) -> int:
        """为题目生成并写入向量。"""
        if not questions:
            return 0
        vectors = await self._embedder.embed([self._index_text(item) for item in questions])
        for question, vector in zip(questions, vectors, strict=True):
            question.embedding = vector
        await session.flush()
        return len(questions)

    def _base_query(self, subject: str | None) -> Select[tuple[Question]]:
        stmt = select(Question).where(
            Question.embedding.is_not(None),
            Question.status == QuestionStatus.PUBLISHED,
        )
        if subject:
            stmt = stmt.where(Question.subject == subject)
        return stmt

    async def search_questions(
        self,
        session: AsyncSession,
        query: str,
        *,
        subject: str | None = None,
        top_k: int = 5,
        candidate_k: int | None = None,
        use_rerank: bool = True,
    ) -> list[RetrievedQuestion]:
        """检索相似题目。"""
        candidate_count = candidate_k or max(top_k * 4, 20)
        query_vector = (await self._embedder.embed([query]))[0]

        stmt = self._base_query(subject)
        distance = Question.embedding.cosine_distance(query_vector).label("distance")
        stmt = stmt.add_columns(distance).order_by(distance).limit(candidate_count)
        rows = (await session.execute(stmt)).all()
        if not rows:
            return []

        candidates: list[RetrievedQuestion] = [
            RetrievedQuestion(question=row[0], score=1.0 - float(row[1])) for row in rows
        ]

        if self._rerank_enabled and self._reranker is not None and len(candidates) > top_k:
            ranking = await self._reranker.rerank(
                query, [item.question.stem for item in candidates]
            )
            best = max((score for _, score in ranking), default=1.0) or 1.0
            ranked: list[RetrievedQuestion] = []
            for index, score in ranking[:top_k]:
                if 0 <= index < len(candidates):
                    ranked.append(
                        RetrievedQuestion(question=candidates[index].question, score=score / best)
                    )
            logger.info(
                "检索完成（含重排）",
                extra={"context": {"query_len": len(query), "candidates": len(candidates)}},
            )
            return ranked

        return candidates[:top_k]
