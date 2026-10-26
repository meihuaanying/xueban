"""年级出题范围（grade_scope）：全学段扩展的年级过滤契约。

守住两件事：
1. 年级值必须先过白名单，非法值不得进入任何查询；
2. 按年级取到的知识点集合只包含该年级的人教版课程知识点，
   旧自动展开图谱（grade 为 NULL）不混进来。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import NotFoundError
from app.models import KnowledgePoint
from app.services.grade_scope import knowledge_point_ids_for_grade, validate_grade


def test_validate_grade_accepts_all_twelve() -> None:
    for index in range(1, 13):
        assert validate_grade(f"grade{index}") == f"grade{index}"


@pytest.mark.parametrize("bad", ["grade0", "grade13", "grade", "kindergarten", ""])
def test_validate_grade_rejects_unknown(bad: str) -> None:
    with pytest.raises(NotFoundError) as caught:
        validate_grade(bad)
    assert caught.value.code == "GRADE_INVALID"


async def test_knowledge_point_ids_for_grade_scopes_exactly(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    g7_id = uuid.uuid4()
    g10_id = uuid.uuid4()
    legacy_id = uuid.uuid4()
    async with sessionmaker() as session:
        session.add_all(
            [
                KnowledgePoint(
                    id=g7_id, code="g7m-linear", name="一元一次方程", subject="math",
                    stage="junior", grade="grade7",
                ),
                KnowledgePoint(
                    id=g10_id, code="g10m-quadratic", name="一元二次方程", subject="math",
                    stage="senior", grade="grade10",
                ),
                # 旧自动展开图谱：没有年级，不应出现在任何年级集合里
                KnowledgePoint(
                    id=legacy_id, code="junior.math.ch01.t01", name="旧图谱知识点",
                    subject="math", stage="junior", grade=None,
                ),
            ]
        )
        await session.commit()

        ids = await knowledge_point_ids_for_grade(session, grade="grade7")
        assert ids == {g7_id}
        senior_ids = await knowledge_point_ids_for_grade(session, grade="grade10")
        assert senior_ids == {g10_id}

        # 清理，避免污染同库内其他用例（conftest 的 clean_database 兜底）
        await session.execute(
            delete(KnowledgePoint).where(
                KnowledgePoint.id.in_([g7_id, g10_id, legacy_id])
            )
        )
        await session.commit()
