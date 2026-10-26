"""诊断的年级过滤（全学段扩展）。

两件事必须钉住：
1. 带 grade 时只在课程树该年级的知识点范围内出题；
2. 年级题库未建时回退学段题库（与前端空态文案「先用已有学段的题练一练」一致）。
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
)
from tests.helpers import headers_of, register


async def _seed_bank(sessionmaker: async_sessionmaker[AsyncSession], *, kp_count: int = 5) -> None:
    """旧学段题库：知识点 grade 为 NULL（grade 列引入前的内容形态）。"""
    async with sessionmaker() as session:
        for k in range(kp_count):
            kp = KnowledgePoint(
                code="math.test.bank" + str(k).zfill(2),
                name="知识点" + str(k),
                subject="math",
                stage="junior",
                sort_order=k,
            )
            session.add(kp)
            await session.flush()
            for i in range(4):
                question = Question(
                    subject="math",
                    stage="junior",
                    qtype=QuestionType.FILL,
                    stem="第" + str(i) + "题：" + str(k) + "+" + str(i) + " = ?",
                    answer=str(k + i),
                    analysis="基础加法。",
                    difficulty=(i % 4) + 1,
                    status=QuestionStatus.PUBLISHED,
                )
                session.add(question)
                await session.flush()
                session.add(
                    QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id)
                )
        await session.commit()


async def _seed_grade_bank(
    sessionmaker: async_sessionmaker[AsyncSession], *, grade: str, prefix: str
) -> uuid.UUID:
    """造一个指定年级的知识点 + 4 道题，返回知识点 id。"""
    async with sessionmaker() as session:
        kp = KnowledgePoint(
            code="math." + prefix + ".grade",
            name=prefix + " 知识点",
            subject="math",
            stage="junior",
            grade=grade,
            sort_order=0,
        )
        session.add(kp)
        await session.flush()
        for i in range(4):
            question = Question(
                subject="math",
                stage="junior",
                qtype=QuestionType.FILL,
                stem="[" + prefix + "] 第" + str(i) + "题：" + str(i) + "+1 = ?",
                answer=str(i + 1),
                analysis="基础加法。",
                difficulty=i + 1,
                status=QuestionStatus.PUBLISHED,
            )
            session.add(question)
            await session.flush()
            session.add(
                QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id)
            )
        await session.commit()
        return kp.id


async def test_diagnosis_grade_scope_limits_candidates(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """带 grade 时只在课程树该年级的知识点范围内出题。"""
    grade7_kp = await _seed_grade_bank(sessionmaker, grade="grade7", prefix="g7")
    await _seed_grade_bank(sessionmaker, grade="grade8", prefix="g8")
    payload = await register(client)

    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "grade": "grade7", "target_count": 20},
        headers=headers_of(payload),
    )
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["question"]["knowledge_point_ids"] == [grade7_kp.hex]


async def test_diagnosis_grade_falls_back_when_grade_bank_empty(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """年级题库未建时回退学段题库（空态文案承诺的行为）。"""
    await _seed_bank(sessionmaker)
    payload = await register(client)

    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "grade": "grade7", "target_count": 20},
        headers=headers_of(payload),
    )
    assert started.status_code == 201, started.text
    assert started.json()["question"]["id"]


async def test_diagnosis_next_question_stays_in_grade_scope(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """首题按年级收窄后，后续题必须留在同一范围（跨年级串题是回归）。

    一、二年级同属 primary、七至九年级同属 junior：只按 stage 选题时，
    grade7 诊断从第 2 题起会抽到 grade9。这里用两个同 stage 的年级造题，
    断言第二题仍只挂 grade7 的知识点。
    """
    grade7_kp = await _seed_grade_bank(sessionmaker, grade="grade7", prefix="g7b")
    await _seed_grade_bank(sessionmaker, grade="grade8", prefix="g8b")
    payload = await register(client)
    headers = headers_of(payload)

    started = await client.post(
        "/v1/diagnosis/start",
        json={"subject": "math", "stage": "junior", "grade": "grade7", "target_count": 20},
        headers=headers,
    )
    assert started.status_code == 201, started.text
    body = started.json()
    exam_id = body["exam_id"]
    question = body["question"]

    answered = await client.post(
        f"/v1/diagnosis/{exam_id}/answer",
        json={"question_id": question["id"], "answer": "wrong-on-purpose"},
        headers=headers,
    )
    assert answered.status_code == 200, answered.text
    next_question = answered.json()["next_question"]
    assert next_question is not None, "20 题诊断不应在第 1 题后就结束"
    assert set(next_question["knowledge_point_ids"]) <= {grade7_kp.hex}
