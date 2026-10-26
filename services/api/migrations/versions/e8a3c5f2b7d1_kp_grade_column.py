"""知识点表补 grade 列（全学段扩展：stage 收敛为 primary/junior/senior）

Revision ID: e8a3c5f2b7d1
Revises: c4f1a2b7d9e0
Create Date: 2026-10-26

背景：题库管线此前把一二年级题写成 stage="grade1_2"，与前端学段
（primary/junior/senior）断裂。本次收敛：
- knowledge_points 增 grade 列（grade1~12，旧自动展开图谱的知识点为 NULL）；
- 已有课程树知识点按课程数据回填 grade，并把历史 stage="grade1_2"
  一并改写为 primary（stage_for_grade 的权威映射）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8a3c5f2b7d1"
down_revision: str | None = "c4f1a2b7d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_points",
        sa.Column("grade", sa.String(length=8), nullable=True),
    )
    op.create_index("ix_knowledge_points_grade", "knowledge_points", ["grade"])

    # 回填：课程树里已有的知识点按 code 精确回填年级与学段。
    # 迁移内不 import app 包（alembic 环境与运行环境解耦），映射在这里内联。
    conn = op.get_bind()
    curriculum_rows: list[tuple[str, str, str]] = _curriculum_rows()
    for code, grade, stage in curriculum_rows:
        conn.execute(
            sa.text(
                "UPDATE knowledge_points SET grade = :grade, stage = :stage"
                " WHERE code = :code AND (grade IS DISTINCT FROM :grade"
                " OR stage IS DISTINCT FROM :stage)"
            ),
            {"code": code, "grade": grade, "stage": stage},
        )
    # 历史遗留：任何 stage='grade1_2' 的行（课程树之外不太可能存在）统一归 primary。
    conn.execute(
        sa.text("UPDATE knowledge_points SET stage = 'primary' WHERE stage = 'grade1_2'")
    )
    # 题目的 stage 必须随知识点一起迁移：只改 KP 不改题，会让旧小学题
    # 永久查不到（诊断/练习按 Question.stage 精确过滤），且管线计数把它们
    # 算作「已有题」从而跳过补题——等于旧内容隐形丢失。
    conn.execute(
        sa.text("UPDATE questions SET stage = 'primary' WHERE stage = 'grade1_2'")
    )

    # 迁移后自检：不允许残留任何 grade1_2（KP 或题目）。发现即中止迁移，
    # 避免「迁移成功但数据不可达」的静默失败。
    leftover_kp = conn.execute(
        sa.text("SELECT count(*) FROM knowledge_points WHERE stage = 'grade1_2'")
    ).scalar_one()
    leftover_q = conn.execute(
        sa.text("SELECT count(*) FROM questions WHERE stage = 'grade1_2'")
    ).scalar_one()
    if leftover_kp or leftover_q:
        raise RuntimeError(
            f"stage 迁移未完成：knowledge_points 残留 {leftover_kp} 行、"
            f"questions 残留 {leftover_q} 行仍为 grade1_2"
        )


def downgrade() -> None:
    op.drop_index("ix_knowledge_points_grade", table_name="knowledge_points")
    op.drop_column("knowledge_points", "grade")


def _curriculum_rows() -> list[tuple[str, str, str]]:
    """读取课程 JSON 的 (code, grade, stage) 三元组。

    独立解析而不是复用 app.data.curriculum：alembic 迁移须在无应用配置的
    环境下可执行，且只需这一个扁平视图。
    """
    import json
    from pathlib import Path

    stage_for_grade: dict[str, str] = {
        **{f"grade{i}": "primary" for i in range(1, 7)},
        **{f"grade{i}": "junior" for i in range(7, 10)},
        **{f"grade{i}": "senior" for i in range(10, 13)},
    }
    rows: list[tuple[str, str, str]] = []
    curriculum_dir = (
        Path(__file__).resolve().parents[2] / "app" / "data" / "curriculum"
    )
    for path in sorted(curriculum_dir.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for stage_block in raw.get("stages", []):
            grade = stage_block.get("grade", "")
            stage = stage_for_grade.get(grade)
            if stage is None:
                continue
            for unit in stage_block.get("units", []):
                for point in unit.get("knowledge_points", []):
                    point_id = point.get("id")
                    if isinstance(point_id, str) and point_id:
                        rows.append((point_id, grade, stage))
    return rows
