"""PDF 解析入库测试（T2.5）：分块元数据、100 页性能、失败降级。"""

from __future__ import annotations

import time

import pytest
from fpdf import FPDF
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Document, DocumentChunk, DocumentStatus, User
from app.services.embeddings import MockEmbeddingProvider
from app.services.ingest_service import (
    IngestError,
    IngestService,
    chunk_pages,
    extract_pdf_pages,
)
from tests.factories import UserFactory


def _make_pdf(pages: int) -> bytes:
    """生成指定页数的测试 PDF（英文正文，避免字体依赖）。"""
    pdf = FPDF()
    for index in range(pages):
        pdf.add_page()
        pdf.set_font("helvetica", size=12)
        for paragraph in range(3):
            text = (
                f"Page {index + 1} paragraph {paragraph + 1}: "
                "Learn math step by step and practice every day. " * 5
            )
            pdf.multi_cell(0, 8, text)
            pdf.ln(2)
    return bytes(pdf.output())


def test_chunk_pages_keeps_page_metadata() -> None:
    pages = ["Paragraph one is here.\n\nParagraph two is here." for _ in range(4)]
    chunks = chunk_pages(pages, max_chars=50, overlap=10)
    assert chunks
    for chunk in chunks:
        assert 1 <= chunk.page_from <= chunk.page_to <= 4
        assert chunk.content.strip()
        assert len(chunk.content) <= 200


def test_chunk_pages_handles_empty_pages() -> None:
    chunks = chunk_pages(["", "   ", "只有一页内容。"])
    assert len(chunks) == 1
    assert chunks[0].page_from == 3


def test_extract_pdf_invalid_bytes() -> None:
    with pytest.raises(IngestError):
        extract_pdf_pages(b"definitely-not-a-pdf")


async def test_ingest_pdf_100_pages_under_5_minutes(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    user: User = UserFactory()
    async with sessionmaker() as session:
        session.add(user)
        await session.flush()
        data = _make_pdf(100)
        service = IngestService(MockEmbeddingProvider())
        started = time.perf_counter()
        document = await service.ingest_pdf(
            session,
            user_id=user.id,
            title="百页讲义",
            filename="handout.pdf",
            data=data,
        )
        await session.commit()
        elapsed = time.perf_counter() - started
        chunk_count = await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
        )
        stored = await session.get(Document, document.id)

    assert stored is not None
    assert stored.page_count == 100
    assert stored.status == DocumentStatus.READY
    assert chunk_count == stored.chunk_count > 0
    assert elapsed < 300, f"100 页 PDF 入库耗时 {elapsed:.1f}s，超过 5 分钟预算"


async def test_ingest_marks_failed_on_embedding_error(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    class BrokenEmbedder:
        name = "broken"
        dims = 16

        async def embed(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("embedding service down")

    user: User = UserFactory()
    async with sessionmaker() as session:
        session.add(user)
        await session.flush()
        service = IngestService(BrokenEmbedder())
        raised = False
        try:
            await service.ingest_pdf(
                session,
                user_id=user.id,
                title="失败样张",
                filename="broken.pdf",
                data=_make_pdf(2),
            )
        except IngestError:
            raised = True
        assert raised is True
        await session.rollback()
