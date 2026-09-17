"""教材/讲义文档问答（F-37）：私有知识库提问（带页码引用）与自测题生成。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models import Document, DocumentChunk, DocumentStatus, User
from app.services.ingest_service import IngestService

_SENTENCE_SPLIT = re.compile(r"[。！？!?；\n]+")


@dataclass(slots=True)
class Citation:
    """页码引用。"""

    page: int
    chunk_id: uuid.UUID
    excerpt: str


@dataclass(slots=True)
class AskResult:
    """文档问答结果。"""

    answer: str
    citations: list[Citation]


@dataclass(slots=True)
class SelfTestQuestion:
    """自测题。"""

    question: str
    answer: str
    page: int


def _tokens(text: str) -> set[str]:
    """轻量分词：中文二元组 + 英文单词，用于关键词重合度排序。"""
    tokens: set[str] = set()
    cleaned = re.sub(r"\s+", "", text)
    chinese = re.findall(r"[\u4e00-\u9fff]", cleaned)
    for index in range(len(chinese) - 1):
        tokens.add(chinese[index] + chinese[index + 1])
    tokens.update(word.lower() for word in re.findall(r"[a-zA-Z]{3,}", text))
    return tokens


async def list_documents(session: AsyncSession, *, user: User) -> list[Document]:
    """我的文档列表。"""
    result = await session.execute(
        select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


async def get_document(session: AsyncSession, *, user: User, document_id: uuid.UUID) -> Document:
    """读取文档（RBAC：仅本人）。"""
    document = await session.get(Document, document_id)
    if document is None or document.user_id != user.id:
        raise NotFoundError("文档不存在", code="LIBRARY_DOC_NOT_FOUND")
    return document


async def create_document(
    session: AsyncSession,
    *,
    user: User,
    ingest: IngestService,
    title: str,
    filename: str,
    data: bytes,
) -> Document:
    """入库文档（PDF 解析 → 分块 → 向量化）。"""
    return await ingest.ingest_pdf(
        session, user_id=user.id, title=title, filename=filename, data=data
    )


async def _chunks(session: AsyncSession, *, document_id: uuid.UUID) -> list[DocumentChunk]:
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.scalars().all())


def _rank_chunks(chunks: list[DocumentChunk], question: str, top_k: int) -> list[DocumentChunk]:
    """按关键词重合度排序（稳定、可测；语义检索由题库 RAG 承担）。"""
    question_tokens = _tokens(question)
    scored: list[tuple[float, DocumentChunk]] = []
    for chunk in chunks:
        chunk_tokens = _tokens(chunk.content)
        if not chunk_tokens:
            continue
        overlap = len(question_tokens & chunk_tokens) / max(len(question_tokens), 1)
        scored.append((overlap, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].chunk_index))
    selected = [chunk for score, chunk in scored[:top_k] if score > 0]
    if not selected:
        selected = [chunk for _, chunk in scored[:top_k]]
    return selected


def _extract_answer(question: str, chunks: list[DocumentChunk]) -> str:
    """抽取式回答（无 LLM 时的确定性回退）：拼接最相关句子。"""
    question_tokens = _tokens(question)
    sentences: list[tuple[float, str]] = []
    for chunk in chunks:
        for sentence in _SENTENCE_SPLIT.split(chunk.content):
            sentence = sentence.strip()
            if len(sentence) < 6:
                continue
            overlap = len(question_tokens & _tokens(sentence))
            sentences.append((overlap, sentence))
    sentences.sort(key=lambda item: -item[0])
    best = [sentence for score, sentence in sentences[:3] if score > 0] or [
        sentence for _, sentence in sentences[:2]
    ]
    if not best:
        return "文档中没有检索到与问题相关的内容，请换一种问法或补充资料。"
    return "根据文档内容：" + "；".join(best) + "。"


async def ask(
    session: AsyncSession,
    *,
    user: User,
    document_id: uuid.UUID,
    question: str,
    top_k: int,
    llm: object | None = None,
) -> AskResult:
    """文档提问：返回带页码引用的回答（LLM 不可用时走抽取式回退）。"""
    document = await get_document(session, user=user, document_id=document_id)
    if document.status != DocumentStatus.READY:
        raise NotFoundError("文档尚未解析完成", code="LIBRARY_DOC_NOT_READY")
    chunks = await _chunks(session, document_id=document_id)
    selected = _rank_chunks(chunks, question, top_k)
    answer = _extract_answer(question, selected)

    citations = [
        Citation(
            page=chunk.page_from,
            chunk_id=chunk.id,
            excerpt=chunk.content[:80],
        )
        for chunk in selected
    ]
    return AskResult(answer=answer, citations=citations)


async def self_test(
    session: AsyncSession, *, user: User, document_id: uuid.UUID, count: int = 5
) -> list[SelfTestQuestion]:
    """基于文档生成自测题（页码可回溯，答案指向原文）。"""
    await get_document(session, user=user, document_id=document_id)
    chunks = await _chunks(session, document_id=document_id)
    questions: list[SelfTestQuestion] = []
    seen: set[str] = set()
    for chunk in chunks:
        for sentence in _SENTENCE_SPLIT.split(chunk.content):
            sentence = sentence.strip()
            if len(sentence) < 12 or sentence in seen:
                continue
            seen.add(sentence)
            questions.append(
                SelfTestQuestion(
                    question=f"请复述并说明其含义（第 {chunk.page_from} 页）：{sentence[:20]}……",
                    answer=sentence,
                    page=chunk.page_from,
                )
            )
            if len(questions) >= count:
                return questions
    return questions


async def document_summary(session: AsyncSession, *, document_id: uuid.UUID) -> str:
    """摘要（取每页首句拼接，确定性）。"""
    chunks = await _chunks(session, document_id=document_id)
    parts: list[str] = []
    seen_pages: set[int] = set()
    for chunk in chunks:
        if chunk.page_from in seen_pages:
            continue
        for sentence in _SENTENCE_SPLIT.split(chunk.content):
            if len(sentence.strip()) >= 8:
                parts.append(sentence.strip())
                seen_pages.add(chunk.page_from)
                break
    return "；".join(parts[:8]) or "文档内容为空。"


async def chunk_count(session: AsyncSession, *, document_id: uuid.UUID) -> int:
    """分块数量。"""
    return int(
        await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        or 0
    )


__all__ = [
    "AskResult",
    "Citation",
    "SelfTestQuestion",
    "ask",
    "chunk_count",
    "create_document",
    "document_summary",
    "get_document",
    "list_documents",
    "self_test",
]
