"""explainer video columns (P3 §5.3)

Revision ID: f7a1c2d3e4b5
Revises: b5f7d9c1a4e2
Create Date: 2026-10-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a1c2d3e4b5"
down_revision: str | None = "b5f7d9c1a4e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("explainer_contents", sa.Column("video_key", sa.String(length=300), nullable=True))
    op.add_column(
        "explainer_contents", sa.Column("video_mime", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "explainer_contents",
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("explainer_contents", "duration_seconds")
    op.drop_column("explainer_contents", "video_mime")
    op.drop_column("explainer_contents", "video_key")
