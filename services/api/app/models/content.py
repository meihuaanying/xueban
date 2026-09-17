"""题库与知识图谱模型（M2 导入，M3 消费）。"""

from __future__ import annotations

import enum
import uuid
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config import EMBEDDING_DIMS
from app.db import Base, TimestampMixin


class QuestionType(enum.StrEnum):
    """题目题型。"""

    CHOICE = "choice"
    FILL = "fill"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"
    PROGRAMMING = "programming"


class QuestionStatus(enum.StrEnum):
    """题目审核三态（F-44）。"""

    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"


class KnowledgePoint(Base, TimestampMixin):
    """知识点（树 + 学科/学段）。"""

    __tablename__ = "knowledge_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(20), default="junior", nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="SET NULL")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class KnowledgeEdge(Base, TimestampMixin):
    """知识点前置依赖边：from 是 to 的前置。"""

    __tablename__ = "knowledge_edges"
    __table_args__ = (
        UniqueConstraint("from_id", "to_id", name="uq_knowledge_edges_from_to"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    to_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )


class MistakeTag(Base, TimestampMixin):
    """错因标签（概念不清/审题偏差/计算失误/方法缺失/迁移薄弱）。"""

    __tablename__ = "mistake_tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="generic", nullable=False)


class Question(Base, TimestampMixin):
    """题目（含解析与标注、检索向量）。"""

    __tablename__ = "questions"
    __table_args__ = (
        Index(
            "ix_questions_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(20), default="junior", nullable=False)
    qtype: Mapped[QuestionType] = mapped_column(
        SAEnum(
            QuestionType, name="question_type", native_enum=False, length=20, create_constraint=True
        ),
        nullable=False,
    )
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    analysis: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    source: Mapped[str] = mapped_column(String(128), default="self-built", nullable=False)
    status: Mapped[QuestionStatus] = mapped_column(
        SAEnum(
            QuestionStatus,
            name="question_status",
            native_enum=False,
            length=20,
            create_constraint=True,
        ),
        default=QuestionStatus.DRAFT,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMS))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class QuestionKnowledgePoint(Base):
    """题目-知识点关联。"""

    __tablename__ = "question_knowledge_points"
    __table_args__ = (
        UniqueConstraint("question_id", "knowledge_point_id", name="uq_question_kp_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class QuestionMistakeTag(Base):
    """题目-错因标签关联。"""

    __tablename__ = "question_mistake_tags"
    __table_args__ = (
        UniqueConstraint("question_id", "mistake_tag_id", name="uq_question_tag_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    mistake_tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mistake_tags.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
