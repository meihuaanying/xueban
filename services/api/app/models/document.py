"""文档与知识库模型（F-37 教材/讲义上传问答的存储层）。"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config import EMBEDDING_DIMS
from app.db import Base, TimestampMixin


class DocumentStatus(enum.StrEnum):
    """文档解析状态。"""

    PENDING = "pending"
    PARSING = "parsing"
    READY = "ready"
    FAILED = "failed"


class Document(Base, TimestampMixin):
    """上传的教材/讲义文档。"""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), default="pdf", nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255))
    file_key: Mapped[str | None] = mapped_column(String(512))
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(
            DocumentStatus,
            name="document_status",
            native_enum=False,
            length=20,
            create_constraint=True,
        ),
        default=DocumentStatus.PENDING,
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class DocumentChunk(Base, TimestampMixin):
    """文档分块（含页码元数据与向量）。"""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_index"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_from: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    page_to: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMS))
