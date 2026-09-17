"""模考与独立测评测试（T3.8 / F-20/F-28）。"""

from __future__ import annotations

import uuid
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.models import (
    Exam,
    ExamAnswer,
    KnowledgePoint,
    LearningProfile,
    MasteryRecord,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
    User,
)
from tests.helpers import headers_of, register


async def _seed_bank(
    sessionmaker: async_sessionmaker[AsyncSession], *, count: int = 12
) -> list[tuple[uuid.UUID, str]]:
    """返回 (题目 id, 正确答案) 列表。"""
    items: list[tuple[uuid.UUID, str]] = []
    async with sessionmaker() as session:
        kp = KnowledgePoint(code="math.test.exam", name="综合", subject="math")
        session.add(kp)
        await session.flush()
        for index in range(count):
            question = Question(
                subject="math",
                stage="junior",
                qtype=QuestionType.FILL,
                stem=f"[综合] 第{index}题：{index} + 1 = ?",
                answer=str(index + 1),
                analysis="基础运算。",
                difficulty=(index % 5) + 1,
                status=QuestionStatus.PUBLISHED,
            )
            session.add(question)
            await session.flush()
            session.add(QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id))
            items.append((question.id, question.answer))
        await session.commit()
    return items


async def _create_exam(
    client: AsyncClient, headers: dict[str, str], *, count: int = 10
) -> dict[str, object]:
    response = await client.post(
        "/v1/exams", json={"subject": "math", "count": count}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_exam_returns_questions_without_answers(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    payload = await register(client)
    body = await _create_exam(client, headers_of(payload))
    assert len(body["questions"]) == 10
    assert body["deadline"] is not None
    assert "answer" not in body["questions"][0]
    assert body["questions"][0]["knowledge_points"] == ["综合"]


async def test_submit_all_correct_scores_100(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    created = await _create_exam(client, headers)
    exam_id = created["exam_id"]
    question_ids = [item["id"] for item in created["questions"]]
    answer_map = {str(question_id): answer for question_id, answer in bank}

    submitted = await client.post(
        f"/v1/exams/{exam_id}/submit",
        json={
            "answers": [
                {"question_id": qid, "answer": answer_map[qid]} for qid in question_ids
            ]
        },
        headers=headers,
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["status"] == "submitted"
    assert body["summary"]["score"] == 100.0
    assert body["summary"]["percentile"] == 100.0
    assert len(body["diagnoses"]) == 10
    assert all(item["is_correct"] for item in body["diagnoses"])

    async with sessionmaker() as session:
        answers = await session.scalar(select(func.count()).select_from(ExamAnswer))
        mastery = await session.scalar(select(func.count()).select_from(MasteryRecord))
    assert answers == 10
    assert mastery >= 1  # 同一知识点只保留一行掌握度（BKT 累计）


async def test_submit_partial_score(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    created = await _create_exam(client, headers)
    exam_id = created["exam_id"]
    question_ids = [item["id"] for item in created["questions"]]
    answer_map = {str(question_id): answer for question_id, answer in bank}

    answers = [
        {"question_id": question_ids[0], "answer": answer_map[question_ids[0]]},
        {"question_id": question_ids[1], "answer": answer_map[question_ids[1]]},
        {"question_id": question_ids[2], "answer": answer_map[question_ids[2]]},
        {"question_id": question_ids[3], "answer": "错误"},
        {"question_id": question_ids[4], "answer": "错误"},
    ]
    submitted = await client.post(
        f"/v1/exams/{exam_id}/submit", json={"answers": answers}, headers=headers
    )
    assert submitted.status_code == 200
    assert submitted.json()["summary"]["score"] == 30.0


async def test_submit_is_idempotent(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    created = await _create_exam(client, headers)
    exam_id = created["exam_id"]
    question_ids = [item["id"] for item in created["questions"]]
    answer_map = {str(question_id): answer for question_id, answer in bank}
    answers = [
        {"question_id": qid, "answer": answer_map[qid]} for qid in question_ids[:5]
    ]

    first = await client.post(
        f"/v1/exams/{exam_id}/submit", json={"answers": answers}, headers=headers
    )
    second = await client.post(
        f"/v1/exams/{exam_id}/submit", json={"answers": answers}, headers=headers
    )
    assert first.json()["summary"] == second.json()["summary"]
    async with sessionmaker() as session:
        answers_count = await session.scalar(select(func.count()).select_from(ExamAnswer))
    assert answers_count == 5


async def test_auto_submit_after_deadline(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    created = await _create_exam(client, headers)
    exam_id = created["exam_id"]

    async with sessionmaker() as session:
        exam = await session.get(Exam, uuid.UUID(str(exam_id)))
        assert exam is not None
        exam.meta = {**exam.meta, "deadline": (utcnow() - timedelta(minutes=1)).isoformat()}
        await session.commit()

    report = await client.get(f"/v1/exams/{exam_id}", headers=headers)
    assert report.status_code == 200
    body = report.json()
    assert body["status"] == "submitted"
    assert body["auto_submitted"] is True
    assert body["summary"]["score"] == 0.0


async def test_percentile_across_users(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    answer_map = {question_id: answer for question_id, answer in bank}

    # 先由 A 交出一份满分卷（作为对照样本）
    user_a = await register(client)
    headers_a = headers_of(user_a)
    created_a = await _create_exam(client, headers_a)
    submitted_a = await client.post(
        f"/v1/exams/{created_a['exam_id']}/submit",
        json={
            "answers": [
                {"question_id": item["id"], "answer": answer_map[uuid.UUID(item["id"])]}
                for item in created_a["questions"]
            ]
        },
        headers=headers_a,
    )
    assert submitted_a.json()["summary"]["score"] == 100.0
    assert submitted_a.json()["summary"]["percentile"] == 100.0

    # B 交全错卷 → 百分位应为 0（所有样本都高于它）
    user_b = await register(client)
    headers_b = headers_of(user_b)
    created_b = await _create_exam(client, headers_b)
    submitted_b = await client.post(
        f"/v1/exams/{created_b['exam_id']}/submit",
        json={
            "answers": [
                {"question_id": item["id"], "answer": "全部错误"}
                for item in created_b["questions"]
            ]
        },
        headers=headers_b,
    )
    assert submitted_b.json()["summary"]["score"] == 0.0
    assert submitted_b.json()["summary"]["percentile"] == 0.0


async def test_solo_assessment_blocks_hints(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)

    question_response = await client.post(
        "/v1/grading/objective",
        json={"question_id": str(bank[0][0]), "answer": "错误"},
        headers=headers,
    )
    session_id = question_response.json()["tutor_session_id"]
    assert session_id

    solo = await client.post(
        "/v1/assessments/solo",
        json={"subject": "math", "count": 5, "time_limit_minutes": 30},
        headers=headers,
    )
    assert solo.status_code == 201, solo.text
    assert solo.json()["kind"] == "solo"

    blocked = await client.post(f"/v1/tutor/{session_id}/hint", json={}, headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "TUTOR_SOLO_LOCKED"

    blocked_new = await client.post(
        "/v1/tutor/session", json={"question_id": str(bank[0][0])}, headers=headers
    )
    assert blocked_new.status_code == 403


async def test_solo_submit_records_independent_score_and_unlocks(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    solo = await client.post(
        "/v1/assessments/solo",
        json={"subject": "math", "count": 5, "time_limit_minutes": 30},
        headers=headers,
    )
    exam_id = solo.json()["exam_id"]
    answer_map = {str(question_id): answer for question_id, answer in bank}
    submitted = await client.post(
        f"/v1/exams/{exam_id}/submit",
        json={
            "answers": [
                {"question_id": item["id"], "answer": answer_map[item["id"]]}
                for item in solo.json()["questions"]
            ]
        },
        headers=headers,
    )
    assert submitted.status_code == 200
    assert submitted.json()["summary"]["independent"] is True

    async with sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.phone == payload["phone"]))
        ).scalar_one()
        profile = (
            await session.execute(
                select(LearningProfile).where(LearningProfile.user_id == user.id)
            )
        ).scalar_one_or_none()
    assert profile is not None
    assert profile.independent_score == 100.0

    allowed = await client.post(
        "/v1/tutor/session", json={"question_id": str(bank[0][0])}, headers=headers
    )
    assert allowed.status_code == 201


async def test_mock_exam_does_not_set_independent_score(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    created = await _create_exam(client, headers, count=5)
    await client.post(
        f"/v1/exams/{created['exam_id']}/submit",
        json={"answers": []},
        headers=headers,
    )
    async with sessionmaker() as session:
        profiles = await session.scalar(select(func.count()).select_from(LearningProfile))
    assert profiles == 0


async def test_exam_no_questions_returns_409(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/exams", json={"subject": "physics", "count": 5}, headers=headers_of(payload)
    )
    assert response.status_code == 409
    assert response.json()["code"] == "EXAM_NO_QUESTIONS"


async def test_exam_isolated_between_users(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    owner = await register(client)
    intruder = await register(client)
    created = await _create_exam(client, headers_of(owner))
    response = await client.get(
        f"/v1/exams/{created['exam_id']}", headers=headers_of(intruder)
    )
    assert response.status_code == 403


async def test_exam_requires_auth(client: AsyncClient) -> None:
    assert (await client.post("/v1/exams", json={"subject": "math"})).status_code == 401
    assert (
        await client.post("/v1/assessments/solo", json={"subject": "math"})
    ).status_code == 401
    assert (await client.get(f"/v1/exams/{uuid.uuid4()}")).status_code == 401
