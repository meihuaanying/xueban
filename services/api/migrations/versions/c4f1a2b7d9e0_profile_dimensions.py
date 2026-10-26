"""学习画像三维字段（认知/行为/情感）

Revision ID: c4f1a2b7d9e0
Revises: b2d7e4a9c153
Create Date: 2026-10-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4f1a2b7d9e0"
down_revision: str | None = "b2d7e4a9c153"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("cognitive_profile", "behavioral_profile", "affective_profile"):
        op.add_column(
            "learning_profiles",
            sa.Column(
                column,
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    for column in ("affective_profile", "behavioral_profile", "cognitive_profile"):
        op.drop_column("learning_profiles", column)
