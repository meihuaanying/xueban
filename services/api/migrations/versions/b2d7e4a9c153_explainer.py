"""explainer：交互网页讲解的内容/作业/反馈三表（P1 §5）

Revision ID: b2d7e4a9c153
Revises: 4f1c9a7e2b30
Create Date: 2026-10-02

说明：``mode`` / ``status`` 的 CHECK 约束**不在这里手写**——模型上的
``SAEnum(..., create_constraint=True)`` 会自动生成 ``ck_<表>_<枚举名>``，
手写一份只会和它打架（枚举名大写、枚举值小写，插入时必然撞其中一边）。
这与 ``e1071bc28a6b_micro_lessons`` 的做法一致。

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b2d7e4a9c153"
down_revision = "4f1c9a7e2b30"
branch_labels = None
depends_on = None


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    op.create_table(
        "explainer_contents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("style_version", sa.String(length=16), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("html", sa.Text()),
        sa.Column("script", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("degraded", sa.Boolean(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("cache_key", name="uq_explainer_contents_cache_key"),
    )
    op.create_index("ix_explainer_contents_cache_key", "explainer_contents", ["cache_key"])
    op.create_index(
        "ix_explainer_contents_knowledge_point_id", "explainer_contents", ["knowledge_point_id"]
    )
    op.create_index("ix_explainer_contents_stage", "explainer_contents", ["stage"])

    op.create_table(
        "explainer_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["knowledge_point_id"], ["knowledge_points.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["content_id"], ["explainer_contents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_explainer_jobs_user_id", "explainer_jobs", ["user_id"])
    op.create_index("ix_explainer_jobs_knowledge_point_id", "explainer_jobs", ["knowledge_point_id"])
    op.create_index("ix_explainer_jobs_content_id", "explainer_jobs", ["content_id"])
    # 每日限额按 (user_id, created_at) 数窗口，加复合索引
    op.create_index("ix_explainer_jobs_user_created", "explainer_jobs", ["user_id", "created_at"])

    op.create_table(
        "explainer_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("understood", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(length=500)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_id"], ["explainer_contents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_explainer_feedback_user_id", "explainer_feedback", ["user_id"])
    op.create_index("ix_explainer_feedback_content_id", "explainer_feedback", ["content_id"])


def downgrade() -> None:
    op.drop_index("ix_explainer_feedback_content_id", table_name="explainer_feedback")
    op.drop_index("ix_explainer_feedback_user_id", table_name="explainer_feedback")
    op.drop_table("explainer_feedback")

    op.drop_index("ix_explainer_jobs_user_created", table_name="explainer_jobs")
    op.drop_index("ix_explainer_jobs_content_id", table_name="explainer_jobs")
    op.drop_index("ix_explainer_jobs_knowledge_point_id", table_name="explainer_jobs")
    op.drop_index("ix_explainer_jobs_user_id", table_name="explainer_jobs")
    op.drop_table("explainer_jobs")

    op.drop_index("ix_explainer_contents_stage", table_name="explainer_contents")
    op.drop_index("ix_explainer_contents_knowledge_point_id", table_name="explainer_contents")
    op.drop_index("ix_explainer_contents_cache_key", table_name="explainer_contents")
    op.drop_table("explainer_contents")