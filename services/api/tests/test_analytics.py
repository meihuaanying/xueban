"""埋点与行为画像测试（T3.10 / F-05）。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AnalyticsEvent,
    ChatMessage,
    ChatRole,
    ChatScene,
    ChatSession,
    KnowledgePoint,
    LearningProfile,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
    User,
)
from tests.helpers import headers_of, register


async def _seed_bank(
    sessionmaker: async_sessionmaker[AsyncSession], *, count: int = 4
) -> list[tuple[uuid.UUID, str]]:
    items: list[tuple[uuid.UUID, str]] = []
    async with sessionmaker() as session:
        kp = KnowledgePoint(code="math.test.analytics", name="方程", subject="math")
        session.add(kp)
        await session.flush()
        for index in range(count):
            question = Question(
                subject="math",
                stage="junior",
                qtype=QuestionType.FILL,
                stem=f"[方程] 第{index}题",
                answer="1",
                analysis="略。",
                status=QuestionStatus.PUBLISHED,
            )
            session.add(question)
            await session.flush()
            session.add(QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id))
            items.append((question.id, question.answer))
        await session.commit()
    return items


async def test_record_events_batch(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/analytics/events",
        json={
            "events": [
                {"name": "answer.change", "payload": {"question_id": "q1", "from": "A", "to": "B"}},
                {"name": "study.session", "payload": {"duration_seconds": 620}},
            ]
        },
        headers=headers_of(payload),
    )
    assert response.status_code == 200, response.text
    assert response.json()["recorded"] == 2
    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(AnalyticsEvent))
    assert count == 2


async def test_record_events_invalid_name(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/analytics/events",
        json={"events": [{"name": "非法事件名", "payload": {}}]},
        headers=headers_of(payload),
    )
    assert response.status_code == 422


async def test_record_events_empty_and_oversize(client: AsyncClient) -> None:
    payload = await register(client)
    empty = await client.post(
        "/v1/analytics/events", json={"events": []}, headers=headers_of(payload)
    )
    assert empty.status_code == 422
    too_many = await client.post(
        "/v1/analytics/events",
        json={"events": [{"name": "test.event"} for _ in range(101)]},
        headers=headers_of(payload),
    )
    assert too_many.status_code == 422


async def test_behavior_default_balanced(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.get("/v1/profile/behavior", headers=headers_of(payload))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["learning_style"] == "balanced"
    assert body["learning_style_label"] == "均衡型"
    assert body["evidence"]["rules"]


async def test_behavior_independent(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    for question_id, answer in bank:
        await client.post(
            "/v1/practice/answer",
            json={"question_id": str(question_id), "answer": answer},
            headers=headers,
        )
    await client.post(
        "/v1/analytics/events",
        json={"events": [{"name": "study.session", "payload": {"duration_seconds": 900}}]},
        headers=headers,
    )
    response = await client.get("/v1/profile/behavior", headers=headers)
    body = response.json()
    assert body["learning_style"] == "independent"
    assert body["evidence"]["accuracy"] == 1.0
    assert body["evidence"]["study_seconds"] == 900


async def test_behavior_impulsive(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    for question_id, answer in bank[:2]:
        await client.post(
            "/v1/practice/answer",
            json={"question_id": str(question_id), "answer": answer},
            headers=headers,
        )
    await client.post(
        "/v1/analytics/events",
        json={"events": [{"name": "answer.change"} for _ in range(5)]},
        headers=headers,
    )
    response = await client.get("/v1/profile/behavior", headers=headers)
    assert response.json()["learning_style"] == "impulsive"


async def test_behavior_guided(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)

    # 两次求助（直接落库两条 assistant 消息，hint_level>=1）
    async with sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.phone == payload["phone"]))
        ).scalar_one()
        chat = ChatSession(user_id=user.id, scene=ChatScene.TUTOR)
        session.add(chat)
        await session.flush()
        for level in (1, 2):
            session.add(
                ChatMessage(
                    session_id=chat.id,
                    role=ChatRole.ASSISTANT,
                    content="提示",
                    hint_level=level,
                )
            )
        await session.commit()

    # 两次练习（1 对 1 错 → 求助率 2/2 = 100%）
    await client.post(
        "/v1/practice/answer",
        json={"question_id": str(bank[0][0]), "answer": bank[0][1]},
        headers=headers,
    )
    await client.post(
        "/v1/practice/answer",
        json={"question_id": str(bank[1][0]), "answer": "错误"},
        headers=headers,
    )

    response = await client.get("/v1/profile/behavior", headers=headers)
    body = response.json()
    assert body["learning_style"] == "guided"
    assert body["evidence"]["hint_requests"] == 2


async def test_behavior_persists_profile(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    await client.get("/v1/profile/behavior", headers=headers_of(payload))
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
    assert profile.learning_style == "balanced"


async def test_analytics_requires_auth(client: AsyncClient) -> None:
    assert (
        await client.post("/v1/analytics/events", json={"events": [{"name": "test.event"}]})
    ).status_code == 401
    assert (await client.get("/v1/profile/behavior")).status_code == 401
