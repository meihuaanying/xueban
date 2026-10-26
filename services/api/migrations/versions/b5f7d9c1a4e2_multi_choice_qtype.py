"""多选题题型（新高考 19 题结构）。

SQLAlchemy 的 Enum(native_enum=False, create_constraint=True) 在建库时生成了
``ck_questions_question_type`` CHECK 约束，值清单固定在迁移里；新增枚举成员后
必须同步扩约束，否则插入会失败。

``op.f()`` 把约束名标记为最终名：target_metadata 带命名约定时，alembic 的
op.drop_constraint/create_check_constraint 会对名字再做一次模板展开，把
``ck_questions_question_type`` 变成「ck_questions_ck_questions_question_type」，
与库里的实际名字对不上。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5f7d9c1a4e2"
down_revision: str | None = "e8a3c5f2b7d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 与 app.models.content.QuestionType 的成员名一致（库里存的是枚举名，大写）
_CONSTRAINT_NAME = "ck_questions_question_type"
_CONDITION_WITH_MULTI = (
    "qtype IN ('CHOICE', 'MULTI_CHOICE', 'FILL', 'SHORT_ANSWER', 'ESSAY',"
    " 'PROGRAMMING', 'JUDGE', 'MATCH', 'ORAL', 'PICK_HANZI')"
)
_CONDITION_WITHOUT_MULTI = (
    "qtype IN ('CHOICE', 'FILL', 'SHORT_ANSWER', 'ESSAY', 'PROGRAMMING',"
    " 'JUDGE', 'MATCH', 'ORAL', 'PICK_HANZI')"
)


def _swap(condition: str) -> None:
    op.drop_constraint(op.f(_CONSTRAINT_NAME), "questions", type_="check")
    op.create_check_constraint(op.f(_CONSTRAINT_NAME), "questions", condition)


def upgrade() -> None:
    _swap(_CONDITION_WITH_MULTI)


def downgrade() -> None:
    leftover = op.get_bind().execute(
        sa.text("SELECT count(*) FROM questions WHERE qtype = 'MULTI_CHOICE'")
    ).scalar_one()
    if leftover:
        raise RuntimeError(f"仍有 {leftover} 道多选题，降级会破坏数据；请先清理后再降级")
    _swap(_CONDITION_WITHOUT_MULTI)
