"""elementary question types

新增 P1 / §6.2 小学题型：judge（判断）、match（连线）、oral（口算）、
pick_hanzi（点选识字）。列本身是 native_enum=False 的 VARCHAR(20)，
无需改列类型，只需重建 CHECK 约束让它接受新取值。

Revision ID: 4f1c9a7e2b30
Revises: d88898187de6
Create Date: 2026-10-02 10:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f1c9a7e2b30"
down_revision: str | None = "d88898187de6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 初始迁移 82fa741c89f2 用的是枚举「成员名」（大写）。SQLAlchemy 对
# native_enum=False 的 SAEnum 默认存 .name 而非 .value，所以这里必须用大写，
# 否则约束与实际写入值不一致，所有插入都会违反 CHECK。
ALL_TYPES = (
    "CHOICE",
    "FILL",
    "SHORT_ANSWER",
    "ESSAY",
    "PROGRAMMING",
    "JUDGE",
    "MATCH",
    "ORAL",
    "PICK_HANZI",
)


def upgrade() -> None:
    """放宽 question_type 的 CHECK 约束，加入小学题型。"""
    op.drop_constraint("question_type", "questions", type_="check")
    op.create_check_constraint(
        "question_type", "questions", sa.column("qtype").in_(ALL_TYPES)
    )


def downgrade() -> None:
    """收回小学题型；已有数据会阻止回退，这属于预期（不要静默删题）。"""
    op.execute(
        sa.text(
            "DELETE FROM questions WHERE qtype IN ('JUDGE', 'MATCH', 'ORAL', 'PICK_HANZI')"
        )
    )
    op.drop_constraint("question_type", "questions", type_="check")
    op.create_check_constraint(
        "question_type",
        "questions",
        sa.column("qtype").in_(
            ("CHOICE", "FILL", "SHORT_ANSWER", "ESSAY", "PROGRAMMING")
        ),
    )
