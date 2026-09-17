"""智能出题与作答闭环测试（T3.6 / F-10/F-17）。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    KnowledgePoint,
    MistakeBookEntry,
    PracticeRecord,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
    User,
)
from app.services import mastery_service
from tests.helpers import headers_of, register


async def _seed_bank(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    weak_kps: int = 3,
    strong_kps: int = 3,
    per_kp: int = 3,
) -> dict[str, list[uuid.UUID]]:
    """播种题库：弱/强知识点各若干，每点若干题（难度 1~5 循环）。"""
    result: dict[str, list[uuid.UUID]] = {"weak": [], "strong": [], "questions": []}
    async with sessionmaker() as session:
        for group, count, prefix in (
            ("weak", weak_kps, "w"),
            ("strong", strong_kps, "s"),
        ):
            for k in range(count):
                kp = KnowledgePoint(
                    code=f"math.test.{prefix}{k:02d}",
                    name=f"{'薄弱' if group == 'weak' else '优势'}知识点{k}",
                    subject="math",
                    stage="junior",
                    sort_order=k,
                )
                session.add(kp)
                await session.flush()
                result[group].append(kp.id)
                for i in range(per_kp):
                    difficulty = (i % 5) + 1
                    question = Question(
                        subject="math",
                        stage="junior",
                        qtype=QuestionType.FILL,
                        stem=f"[{kp.name}] 第{i}题：{k}+{i} = ?",
                        answer=str(k + i),
                        analysis="基础运算。",
                        difficulty=difficulty,
                        status=QuestionStatus.PUBLISHED,
                    )
                    session.add(question)
                    await session.flush()
                    session.add(
                        QuestionKnowledgePoint(
                            question_id=question.id, knowledge_point_id=kp.id
                        )
                    )
                    result["questions"].append(question.id)
        await session.commit()
    return result


async def _mark_weak(
    sessionmaker: async_sessionmaker[AsyncSession], phone: str, kp_ids: list[uuid.UUID]
) -> None:
    async with sessionmaker() as session:
        user = (await session.execute(select(User).where(User.phone == phone))).scalar_one()
        for kp_id in kp_ids:
            for _ in range(4):
                await mastery_service.record_practice(
                    session, user_id=user.id, knowledge_point_id=kp_id, correct=False
                )
        await session.commit()


async def test_generate_prioritizes_weak_knowledge_points(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    await _mark_weak(sessionmaker, payload["phone"], bank["weak"])

    response = await client.post(
        "/v1/practice/generate",
        json={"subject": "math", "count": 5},
        headers=headers_of(payload),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 5
    assert body["weak_ratio"] >= 0.6, "薄弱知识点占比须不低于 60%"
    reasons = [item["reason"] for item in body["questions"]]
    assert reasons.count("weak") >= 3
    for item in body["questions"]:
        assert item["knowledge_points"]


async def test_generate_deduplicates_recent_questions(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker, weak_kps=1, strong_kps=1, per_kp=6)
    payload = await register(client)
    await _mark_weak(sessionmaker, payload["phone"], bank["weak"])
    headers = headers_of(payload)

    first = await client.post(
        "/v1/practice/generate", json={"subject": "math", "count": 4}, headers=headers
    )
    first_ids = [item["id"] for item in first.json()["questions"]]
    assert len(first_ids) == 4

    # 作答全部题目（近 7 天内不得再出）
    for question_id in first_ids:
        answer = await client.post(
            "/v1/practice/answer",
            json={"question_id": question_id, "answer": "不存在的答案"},
            headers=headers,
        )
        assert answer.status_code == 200

    second = await client.post(
        "/v1/practice/generate", json={"subject": "math", "count": 4}, headers=headers
    )
    second_ids = [item["id"] for item in second.json()["questions"]]
    assert not set(first_ids) & set(second_ids), "近 7 天做过的题不得重复出现"


async def test_generate_filters_by_knowledge_point(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker, weak_kps=2, strong_kps=2)
    payload = await register(client)
    await _mark_weak(sessionmaker, payload["phone"], bank["weak"])
    response = await client.post(
        "/v1/practice/generate",
        json={
            "subject": "math",
            "count": 3,
            "knowledge_point_ids": [str(bank["weak"][0])],
        },
        headers=headers_of(payload),
    )
    assert response.status_code == 200
    assert response.json()["count"] == 3


async def test_answer_correct_updates_card_without_mistake(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker, weak_kps=1, strong_kps=0, per_kp=1)
    payload = await register(client)
    async with sessionmaker() as session:
        question = (
            await session.execute(
                select(Question).where(Question.id == bank["questions"][0])
            )
        ).scalar_one()
    response = await client.post(
        "/v1/practice/answer",
        json={"question_id": str(question.id), "answer": question.answer},
        headers=headers_of(payload),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_correct"] is True
    assert body["mistake_collected"] is False
    assert body["card_due_at"] is not None
    assert body["next_difficulty"] >= 1


async def test_answer_wrong_collects_mistake(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker, weak_kps=1, strong_kps=0, per_kp=1)
    payload = await register(client)
    question_id = bank["questions"][0]
    response = await client.post(
        "/v1/practice/answer",
        json={"question_id": str(question_id), "answer": "错误答案"},
        headers=headers_of(payload),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_correct"] is False
    assert body["mistake_collected"] is True
    async with sessionmaker() as session:
        mistake_count = await session.scalar(
            select(func.count()).select_from(MistakeBookEntry)
        )
        record_count = await session.scalar(select(func.count()).select_from(PracticeRecord))
    assert mistake_count == 1
    assert record_count == 1


async def test_repractice_correct_removes_from_mistake_book(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker, weak_kps=1, strong_kps=0, per_kp=1)
    payload = await register(client)
    headers = headers_of(payload)
    question_id = bank["questions"][0]

    wrong = await client.post(
        "/v1/practice/answer",
        json={"question_id": str(question_id), "answer": "错误答案"},
        headers=headers,
    )
    assert wrong.json()["mistake_collected"] is True

    repractice = await client.post(
        "/v1/mistakes/repractice", json={"count": 5}, headers=headers
    )
    assert repractice.status_code == 200
    assert repractice.json()["count"] == 1

    async with sessionmaker() as session:
        question = await session.get(Question, question_id)
        assert question is not None
        answer = question.answer
    fixed = await client.post(
        "/v1/practice/answer",
        json={"question_id": str(question_id), "answer": answer, "source": "repractice"},
        headers=headers,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["is_correct"] is True
    assert fixed.json()["mistake_removed"] is True

    listing = await client.get("/v1/mistakes", headers=headers)
    assert listing.json()["active_count"] == 0
    assert listing.json()["mastered_count"] == 1


async def test_dynamic_difficulty_up_and_down(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker, weak_kps=2, strong_kps=0, per_kp=2)
    payload = await register(client)
    headers = headers_of(payload)
    async with sessionmaker() as session:
        questions = (
            (await session.execute(select(Question).order_by(Question.created_at)))
            .scalars()
            .all()
        )
    correct_question = questions[0]
    up = await client.post(
        "/v1/practice/answer",
        json={"question_id": str(correct_question.id), "answer": correct_question.answer},
        headers=headers,
    )
    assert up.json()["next_difficulty"] == min(5, correct_question.difficulty + 1)

    wrong_question = questions[1]
    down = await client.post(
        "/v1/practice/answer",
        json={"question_id": str(wrong_question.id), "answer": "错的"},
        headers=headers,
    )
    assert down.json()["next_difficulty"] == max(1, wrong_question.difficulty - 1)


async def test_answer_unknown_question(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/practice/answer",
        json={"question_id": str(uuid.uuid4()), "answer": "1"},
        headers=headers_of(payload),
    )
    assert response.status_code == 404


async def test_practice_requires_auth(client: AsyncClient) -> None:
    assert (
        await client.post("/v1/practice/generate", json={"subject": "math"})
    ).status_code == 401
    assert (
        await client.post(
            "/v1/practice/answer", json={"question_id": str(uuid.uuid4()), "answer": "1"}
        )
    ).status_code == 401
