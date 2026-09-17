"""文档入库服务：PDF 解析 → 分块（含页码）→ 向量化 → 入库（F-37 后端）。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentChunk, DocumentStatus
from app.services.embeddings import EmbeddingProvider

DEFAULT_MAX_CHARS = 600
DEFAULT_OVERLAP = 80


class IngestError(Exception):
    """文档解析/入库失败。"""


@dataclass(slots=True)
class ParsedChunk:
    """分块结果（含页码区间）。"""

    content: str
    page_from: int
    page_to: int


def extract_pdf_pages(data: bytes) -> list[str]:
    """提取 PDF 每页文本。"""
    try:
        reader = PdfReader(BytesIO(data))
        return [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pypdf 抛出的异常类型多样
        raise IngestError(f"PDF 解析失败：{exc}") from exc


def chunk_pages(
    pages: list[str], *, max_chars: int = DEFAULT_MAX_CHARS, overlap: int = DEFAULT_OVERLAP
) -> list[ParsedChunk]:
    """按段落合并分块，保留页码元数据与尾部重叠。"""
    chunks: list[ParsedChunk] = []
    buffer = ""
    buffer_page_from = 1
    buffer_page_to = 1

    for page_number, text in enumerate(pages, start=1):
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
        for paragraph in paragraphs:
            if not buffer:
                buffer = paragraph
                buffer_page_from = page_number
                buffer_page_to = page_number
                continue
            if len(buffer) + 1 + len(paragraph) > max_chars:
                chunks.append(
                    ParsedChunk(content=buffer, page_from=buffer_page_from, page_to=buffer_page_to)
                )
                tail = buffer[-overlap:] if overlap > 0 else ""
                buffer = f"{tail}\n{paragraph}".strip() if tail else paragraph
                buffer_page_from = page_number
                buffer_page_to = page_number
            else:
                buffer = f"{buffer}\n{paragraph}"
                buffer_page_to = page_number

    if buffer:
        chunks.append(
            ParsedChunk(content=buffer, page_from=buffer_page_from, page_to=buffer_page_to)
        )
    return chunks


class IngestService:
    """教材/讲义入库。"""

    def __init__(self, embedder: EmbeddingProvider) -> None:
        self._embedder = embedder

    async def ingest_pdf(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        title: str,
        filename: str,
        data: bytes,
        file_key: str | None = None,
    ) -> Document:
        """解析并入库一份 PDF。"""
        pages = extract_pdf_pages(data)
        chunks = chunk_pages(pages)
        document = Document(
            user_id=user_id,
            title=title,
            filename=filename,
            file_key=file_key,
            page_count=len(pages),
            chunk_count=len(chunks),
            status=DocumentStatus.PARSING,
            meta={"max_chars": DEFAULT_MAX_CHARS, "overlap": DEFAULT_OVERLAP},
        )
        session.add(document)
        await session.flush()

        if chunks:
            try:
                vectors = await self._embedder.embed([chunk.content for chunk in chunks])
            except Exception as exc:
                document.status = DocumentStatus.FAILED
                document.error = str(exc)[:500]
                await session.flush()
                raise IngestError(f"向量化失败：{exc}") from exc
        else:
            vectors = []

        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=chunk.content,
                    page_from=chunk.page_from,
                    page_to=chunk.page_to,
                    char_count=len(chunk.content),
                    embedding=vector,
                )
            )
        document.status = DocumentStatus.READY
        await session.flush()
        return document
