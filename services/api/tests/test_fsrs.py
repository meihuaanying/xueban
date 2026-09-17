"""FSRS 调度测试（T3.6 / F-19）：评分 1–4 间隔、状态迁移、API。"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.errors import AppError, NotFoundError
from app.models import (
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
    ReviewCard,
    User,
)
from app.services import fsrs_service
from app.services.fsrs_service import (
    STATE_LEARNING,
    STATE_NEW,
    STATE_RELEARNING,
    STATE_REVIEW,
    adjust_difficulty,
    schedule,
)
from tests.helpers import headers_of, register

# ---------- 纯函数：新卡评分 1~4 ----------


def test_new_card_grade1_again() -> None:
    outcome = schedule(state=STATE_NEW, stability=0.0, difficulty=5.0, reps=0, lapses=0, grade=1)
    assert outcome.state == STATE_LEARNING
    assert outcome.stability == 0.4
    assert outcome.due_at - utcnow() < timedelta(minutes=11)


def test_new_card_grade2_hard() -> None:
    outcome = schedule(state=STATE_NEW, stability=0.0, difficulty=5.0, reps=0, lapses=0, grade=2)
    assert outcome.interval_days == 0.8
    assert outcome.state == STATE_LEARNING


def test_new_card_grade3_good() -> None:
    outcome = schedule(state=STATE_NEW, stability=0.0, difficulty=5.0, reps=0, lapses=0, grade=3)
    assert outcome.interval_days == 1.6
    assert outcome.state == STATE_LEARNING


def test_new_card_grade4_easy_becomes_review() -> None:
    outcome = schedule(state=STATE_NEW, stability=0.0, difficulty=5.0, reps=0, lapses=0, grade=4)
    assert outcome.interval_days == 3.2
    assert outcome.state == STATE_REVIEW


def test_review_card_intervals() -> None:
    base = dict(state=STATE_REVIEW, stability=10.0, difficulty=5.0, reps=5, lapses=0)
    assert schedule(**base, grade=2).interval_days == 12.0  # Hard
    assert schedule(**base, grade=3).interval_days == 20.0  # Good
    assert schedule(**base, grade=4).interval_days == 30.0  # Easy


def test_review_again_goes_relearning() -> None:
    outcome = schedule(
        state=STATE_REVIEW, stability=10.0, difficulty=5.0, reps=5, lapses=0, grade=1
    )
    assert outcome.state == STATE_RELEARNING
    assert outcome.interval_days == 5.0
    assert outcome.lapses == 1
    assert outcome.due_at - utcnow() < timedelta(minutes=11)


def test_learning_grade3_promotes_to_review() -> None:
    outcome = schedule(
        state=STATE_LEARNING, stability=1.0, difficulty=5.0, reps=1, lapses=0, grade=3
    )
    assert outcome.state == STATE_REVIEW
    assert outcome.interval_days == 1.8


def test_learning_again_stays_learning() -> None:
    outcome = schedule(
        state=STATE_LEARNING, stability=1.0, difficulty=5.0, reps=1, lapses=0, grade=1
    )
    assert outcome.state == STATE_LEARNING
    assert outcome.interval_days == 0.6


def test_reps_increment() -> None:
    outcome = schedule(state=STATE_REVIEW, stability=2.0, difficulty=5.0, reps=7, lapses=0, grade=3)
    assert outcome.reps == 8


def test_difficulty_adjustment_and_clamp() -> None:
    assert adjust_difficulty(5.0, 4) == 5.5
    assert adjust_difficulty(5.0, 1) == 4.0
    assert adjust_difficulty(1.0, 1) == 1.0
    assert adjust_difficulty(10.0, 4) == 10.0


def test_invalid_grade_rejected() -> None:
    with pytest.raises(AppError) as excinfo:
        schedule(state=STATE_NEW, stability=0.0, difficulty=5.0, reps=0, lapses=0, grade=5)
    assert excinfo.value.code == "REVIEW_INVALID_GRADE"


# ---------- 数据层 ----------


async def _seed_question(sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with sessionmaker() as session:
        kp = KnowledgePoint(code="math.test.fsrs", name="方程", subject="math")
        session.add(kp)
        await session.flush()
        question = Question(
            subject="math",
            stage="junior",
            qtype=QuestionType.FILL,
            stem="解方程：x + 1 = 2",
            answer="1",
            analysis="x = 1。",
            status=QuestionStatus.PUBLISHED,
        )
        session.add(question)
        await session.flush()
        session.add(QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id))
        await session.commit()
        return question.id


async def test_update_card_for_answer_creates_and_schedules(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    question_id = await _seed_question(sessionmaker)
    user = User(phone="13900000001")
    async with sessionmaker() as session:
        session.add(user)
        await session.flush()
        user_id = user.id

        card = await fsrs_service.update_card_for_answer(
            session, user_id=user_id, question_id=question_id, correct=True
        )
        await session.commit()
        assert card.state == STATE_LEARNING
        assert card.reps == 1
        first_due = card.due_at

        card = await fsrs_service.update_card_for_answer(
            session, user_id=user_id, question_id=question_id, correct=False
        )
        await session.commit()
    assert card.reps == 2
    assert card.due_at is not None and first_due is not None


async def test_due_cards_and_count(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    question_id = await _seed_question(sessionmaker)
    user = User(phone="13900000002")
    async with sessionmaker() as session:
        session.add(user)
        await session.flush()
        user_id = user.id
        card = await fsrs_service.update_card_for_answer(
            session, user_id=user_id, question_id=question_id, correct=True
        )
        card.due_at = utcnow() - timedelta(days=1)
        await session.commit()

        due = await fsrs_service.due_cards(session, user_id=user_id)
        count = await fsrs_service.due_count(session, user_id=user_id)
    assert len(due) == 1
    assert count == 1


async def test_grade_card_ownership(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    question_id = await _seed_question(sessionmaker)
    async with sessionmaker() as session:
        owner = User(phone="13900000003")
        intruder = User(phone="13900000004")
        session.add_all([owner, intruder])
        await session.flush()
        card = await fsrs_service.update_card_for_answer(
            session, user_id=owner.id, question_id=question_id, correct=True
        )
        await session.commit()
        card_id = card.id

        with pytest.raises(NotFoundError):
            await fsrs_service.grade_card(session, user=intruder, card_id=card_id, grade=3)


# ---------- API ----------


async def test_review_due_and_grade_api(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)

    empty = await client.get("/v1/review/due", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["due_count"] == 0

    # 作答一次（自动建卡）后把到期时间提前
    answered = await client.post(
        "/v1/practice/answer",
        json={"question_id": str(question_id), "answer": "1"},
        headers=headers,
    )
    assert answered.status_code == 200, answered.text
    async with sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.phone == payload["phone"]))
        ).scalar_one()
        card = (
            await session.execute(select(ReviewCard).where(ReviewCard.user_id == user.id))
        ).scalar_one()
        card.due_at = utcnow() - timedelta(days=1)
        await session.commit()
        card_id = card.id

    due = await client.get("/v1/review/due", headers=headers)
    body = due.json()
    assert body["due_count"] == 1
    assert body["cards"][0]["question"]["stem"].startswith("解方程")

    graded = await client.post(
        f"/v1/review/{card_id}/grade", json={"grade": 3}, headers=headers
    )
    assert graded.status_code == 200, graded.text
    graded_body = graded.json()
    assert graded_body["state"] == "review"
    assert graded_body["interval_days"] > 0

    invalid = await client.post(f"/v1/review/{card_id}/grade", json={"grade": 5}, headers=headers)
    assert invalid.status_code == 422


async def test_review_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/v1/review/due")).status_code == 401
    assert (
        await client.post(f"/v1/review/{uuid.uuid4()}/grade", json={"grade": 3})
    ).status_code == 401
