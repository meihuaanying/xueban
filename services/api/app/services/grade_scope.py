"""年级出题范围（全学段扩展，2026-10）。

把「按教材年级出题」收窄成知识点 id 集合：诊断、练习、学习规划共用。
年级值来自请求参数，入口先过白名单（GRADE_NAMES 的 key），查询一律用
显式绑定参数（bindparam），用户输入不参与任何 SQL 字符串构造。
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.curriculum import GRADE_NAMES
from app.errors import NotFoundError
from app.models import KnowledgePoint


def validate_grade(grade: str) -> str:
    """年级白名单校验（grade1~12）：非法值直接 404，绝不进任何查询。"""
    if grade not in GRADE_NAMES:
        raise NotFoundError(
            f"未知年级：{grade}（合法值 grade1~grade12）", code="GRADE_INVALID"
        )
    return grade


async def knowledge_point_ids_for_grade(
    session: AsyncSession, *, grade: str
) -> set[uuid.UUID]:
    """该年级（人教版课程树）在库内的知识点 id 集合。

    旧自动展开图谱的知识点 grade 为 NULL，天然不在集合里——年级过滤
    意味着「按教材进度出题」，这是刻意的。
    """
    validated = validate_grade(grade)
    rows = (
        await session.execute(
            select(KnowledgePoint.id).where(
                KnowledgePoint.grade == sa.bindparam("kp_grade")
            ),
            {"kp_grade": validated},
        )
    ).scalars().all()
    return set(rows)


__all__ = ["knowledge_point_ids_for_grade", "validate_grade"]
