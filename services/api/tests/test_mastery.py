"""BKT 学情画像测试（T3.1 / F-03）：算法数值、衰减、API 契约。"""

from __future__ import annotations

import uuid
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.models import KnowledgePoint, User
from app.services import mastery_service
from app.services.mastery_service import BktParams, apply_decay, bkt_update, mastery_level
from tests.factories import UserFactory
from tests.helpers import headers_of, register

# ---------- 算法单元 ----------


def test_bkt_correct_raises_mastery() -> None:
    value = bkt_update(0.30, True)
    assert 0.68 < value < 0.69, f"标准参数下答对应升到约 0.685，实际 {value}"


def test_bkt_incorrect_lowers_mastery() -> None:
    value = bkt_update(0.30, False)
    assert 0.24 < value < 0.25, f"标准参数下答错应降到约 0.243，实际 {value}"


def test_bkt_bounds() -> None:
    assert bkt_update(1.0, True) <= 1.0
    assert bkt_update(0.0, False) >= 0.0


def test_bkt_repeated_correct_converges() -> None:
    value = 0.30
    for _ in range(10):
        value = bkt_update(value, True)
    assert value > 0.95


def test_bkt_custom_params_exact() -> None:
    params = BktParams(p_guess=0.20, p_slip=0.05, p_transit=0.0)
    value = bkt_update(0.5, True, params)
    assert abs(value - 0.826087) < 0.001


def test_mastery_level_thresholds() -> None:
    assert mastery_level(0.0) == "red"
    assert mastery_level(0.599) == "red"
    assert mastery_level(0.6) == "yellow"
    assert mastery_level(0.799) == "yellow"
    assert mastery_level(0.8) == "green"
    assert mastery_level(1.0) == "green"


def test_apply_decay_without_history_keeps_value() -> None:
    assert apply_decay(0.9, None) == 0.9


def test_apply_decay_same_moment_keeps_value() -> None:
    now = utcnow()
    assert apply_decay(0.9, now, now=now) == 0.9


def test_apply_decay_half_life_returns_midpoint() -> None:
    now = utcnow()
    last = now - timedelta(days=30)
    value = apply_decay(0.9, last, now=now)
    assert abs(value - 0.6) < 1e-6, "半衰期 30 天应回到先验与当前值的中间点"


def test_apply_decay_future_timestamp_clamped() -> None:
    now = utcnow()
    assert apply_decay(0.9, now + timedelta(days=5), now=now) == 0.9


def test_mastery_average() -> None:
    assert mastery_service.mastery_average([]) is None
    points = [
        mastery_service.MasteryPoint(
            knowledge_point_id=uuid.uuid4(),
            code="a",
            name="甲",
            subject="math",
            stage="junior",
            mastery=0.5,
            level="red",
            total_attempts=1,
            correct_attempts=0,
            last_practiced_at=None,
        ),
        mastery_service.MasteryPoint(
            knowledge_point_id=uuid.uuid4(),
            code="b",
            name="乙",
            subject="math",
            stage="junior",
            mastery=0.9,
            level="green",
            total_attempts=2,
            correct_attempts=2,
            last_practiced_at=None,
        ),
    ]
    assert mastery_service.mastery_average(points) == 0.7


# ---------- 数据层 ----------


async def _add_kp(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    code: str = "math.junior.c01.t01",
    name: str = "正数与负数",
    subject: str = "math",
    stage: str = "junior",
) -> uuid.UUID:
    async with sessionmaker() as session:
        kp = KnowledgePoint(code=code, name=name, subject=subject, stage=stage)
        session.add(kp)
        await session.commit()
        return kp.id


async def _add_user(sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    user: User = UserFactory()
    async with sessionmaker() as session:
        session.add(user)
        await session.commit()
        return user.id


async def test_record_practice_upserts(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    kp_id = await _add_kp(sessionmaker)
    user_id = await _add_user(sessionmaker)
    async with sessionmaker() as session:
        first = await mastery_service.record_practice(
            session, user_id=user_id, knowledge_point_id=kp_id, correct=True
        )
        await session.commit()
        first_mastery = first.mastery
        second = await mastery_service.record_practice(
            session, user_id=user_id, knowledge_point_id=kp_id, correct=False
        )
        await session.commit()
    assert first_mastery > 0.3
    assert second.total_attempts == 2
    assert second.correct_attempts == 1
    assert second.mastery < first_mastery


async def test_overview_sorted_and_filtered(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    easy = await _add_kp(sessionmaker, code="math.junior.c01.t01", name="较易")
    hard = await _add_kp(sessionmaker, code="math.junior.c01.t02", name="较难")
    await _add_kp(
        sessionmaker,
        code="english.adult_en.c01.t01",
        name="词汇",
        subject="english",
        stage="adult",
    )
    user_id = await _add_user(sessionmaker)
    async with sessionmaker() as session:
        for _ in range(4):
            await mastery_service.record_practice(
                session, user_id=user_id, knowledge_point_id=easy, correct=True
            )
        await mastery_service.record_practice(
            session, user_id=user_id, knowledge_point_id=hard, correct=False
        )
        await session.commit()
        math_points = await mastery_service.get_mastery_overview(
            session, user_id=user_id, subject="math"
        )
        english_points = await mastery_service.get_mastery_overview(
            session, user_id=user_id, subject="english"
        )
    assert [point.name for point in math_points] == ["较难", "较易"]  # 升序（薄弱优先）
    assert english_points == []


async def test_overview_applies_decay(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    kp_id = await _add_kp(sessionmaker)
    user_id = await _add_user(sessionmaker)
    async with sessionmaker() as session:
        for _ in range(5):
            await mastery_service.record_practice(
                session, user_id=user_id, knowledge_point_id=kp_id, correct=True
            )
        await session.commit()
        points_before = await mastery_service.get_mastery_overview(session, user_id=user_id)
        stored_before = points_before[0].mastery

        record = (
            await session.execute(
                select(mastery_service.MasteryRecord).where(
                    mastery_service.MasteryRecord.user_id == user_id
                )
            )
        ).scalar_one()
        record.last_practiced_at = utcnow() - timedelta(days=90)
        await session.commit()
        points_after = await mastery_service.get_mastery_overview(session, user_id=user_id)
    assert points_after[0].mastery < stored_before


# ---------- API ----------


async def test_mastery_api_empty_state(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.get("/v1/profile/mastery", headers=headers_of(payload))
    assert response.status_code == 200
    body = response.json()
    assert body["has_data"] is False
    assert body["points"] == []
    assert body["average_mastery"] is None


async def test_mastery_api_populated(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    kp_id = await _add_kp(sessionmaker)
    async with sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.phone == payload["phone"]))
        ).scalar_one()
        await mastery_service.record_practice(
            session, user_id=user.id, knowledge_point_id=kp_id, correct=False
        )
        await session.commit()
    response = await client.get("/v1/profile/mastery", headers=headers_of(payload))
    body = response.json()
    assert body["has_data"] is True
    assert len(body["points"]) == 1
    assert body["points"][0]["level"] in {"red", "yellow", "green"}
    assert body["red_count"] + body["yellow_count"] + body["green_count"] == 1
    assert body["average_mastery"] is not None


async def test_mastery_api_subject_filter(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    math_id = await _add_kp(sessionmaker)
    english_id = await _add_kp(
        sessionmaker, code="english.adult_en.c01.t01", name="词汇", subject="english", stage="adult"
    )
    async with sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.phone == payload["phone"]))
        ).scalar_one()
        await mastery_service.record_practice(
            session, user_id=user.id, knowledge_point_id=math_id, correct=True
        )
        await mastery_service.record_practice(
            session, user_id=user.id, knowledge_point_id=english_id, correct=True
        )
        await session.commit()
    response = await client.get(
        "/v1/profile/mastery", params={"subject": "english"}, headers=headers_of(payload)
    )
    body = response.json()
    assert len(body["points"]) == 1
    assert body["points"][0]["subject"] == "english"


async def test_mastery_api_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/v1/profile/mastery")
    assert response.status_code == 401
