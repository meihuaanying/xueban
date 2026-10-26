"""多端同步与离线幂等测试（M9 / T9.1~T9.2，F-39）。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import PracticeRecord, Question, QuestionStatus, QuestionType, User
from tests.helpers import headers_of, register, register_user


class WebSocketStop(Exception):
    """推送一帧后主动断开（测试用）。"""


class FakeWebSocket:
    """直连路由函数用的假 WebSocket（首帧携带令牌的新协议）。"""

    def __init__(
        self,
        app: object,
        first_frame: dict[str, object] | None = None,
        *,
        stop_after_push: bool = False,
    ) -> None:
        self.app = app
        self.first_frame = first_frame
        self.stop_after_push = stop_after_push
        self.sent: list[dict[str, object]] = []
        self.closed: int | None = None

    async def accept(self) -> None:
        return None

    async def receive_json(self) -> dict[str, object]:
        assert self.first_frame is not None
        return self.first_frame

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)
        if self.stop_after_push:
            raise WebSocketStop()

    async def close(self, code: int = 1000) -> None:
        self.closed = code


async def _seed_question(sessionmaker: async_sessionmaker[AsyncSession]) -> str:
    async with sessionmaker() as session:
        question = Question(
            subject="math",
            stage="junior",
            qtype=QuestionType.CHOICE,
            stem="同步测试题：计算 2 + 2 = ？",
            options={"A": "4", "B": "5"},
            answer="A",
            analysis="2+2=4。正确选项为 A。",
            difficulty=1,
            source="test",
            status=QuestionStatus.PUBLISHED,
        )
        session.add(question)
        await session.flush()
        question_id = str(question.id)
        await session.commit()
        return question_id


async def test_sync_state_version_stable_then_changes(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """F-39：版本号稳定；有新增数据后版本号变化。"""
    user = await register(client)
    first = await client.get("/v1/sync/state", headers=headers_of(user))
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["version"]
    assert body["summary"]["total_today"] >= 0
    assert body["channel"].startswith("sync:")

    second = await client.get("/v1/sync/state", headers=headers_of(user))
    assert second.json()["version"] == body["version"]

    # 产生练习数据 → 版本变化
    question_id = await _seed_question(sessionmaker)
    answered = await client.post(
        "/v1/practice/answer",
        json={"question_id": question_id, "answer": "A", "source": "practice"},
        headers=headers_of(user),
    )
    assert answered.status_code == 200
    third = await client.get("/v1/sync/state", headers=headers_of(user))
    assert third.json()["version"] != body["version"]


async def test_sync_state_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/v1/sync/state")
    assert response.status_code == 401


async def test_websocket_pushes_snapshot(client: AsyncClient) -> None:
    """F-39：WebSocket 首帧携带令牌，推送版本与摘要（3 秒内收到首帧）。"""
    user = await register(client)
    token = user["access_token"]

    # 直接调用路由函数（绕过真实网络），验证推送内容与鉴权
    from app.api.routes import sync as sync_route

    _app = client._transport.app  # type: ignore[attr-defined]
    fake = FakeWebSocket(_app, {"token": token}, stop_after_push=True)
    with pytest.raises(WebSocketStop):
        await sync_route.sync_ws(fake)  # type: ignore[arg-type]
    assert fake.sent and "version" in fake.sent[0]
    assert "summary" in fake.sent[0]


async def test_websocket_rejects_bad_token(client: AsyncClient) -> None:
    from app.api.routes import sync as sync_route

    _app = client._transport.app  # type: ignore[attr-defined]
    fake = FakeWebSocket(_app, {"token": "invalid-token"})
    await sync_route.sync_ws(fake)  # type: ignore[arg-type]
    assert fake.closed == 4401


async def test_websocket_rejects_disabled_user(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """停用账号的存量访问令牌不能建立同步推送连接（4401）。"""
    user = await register_user(client)
    token = user["access_token"]
    user_id = uuid.UUID(user["id"])

    async with sessionmaker() as session:
        record = await session.get(User, user_id)
        assert record is not None
        record.is_active = False
        await session.commit()

    from app.api.routes import sync as sync_route

    _app = client._transport.app  # type: ignore[attr-defined]
    fake = FakeWebSocket(_app, {"token": token})
    await sync_route.sync_ws(fake)  # type: ignore[arg-type]
    assert fake.closed == 4401


async def test_websocket_rejects_first_frame_without_token(client: AsyncClient) -> None:
    """首帧未携带 token 直接拒绝（4401）。"""
    from app.api.routes import sync as sync_route

    _app = client._transport.app  # type: ignore[attr-defined]
    fake = FakeWebSocket(_app, {})
    await sync_route.sync_ws(fake)  # type: ignore[arg-type]
    assert fake.closed == 4401


async def test_practice_answer_idempotent_replay(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """T9.2：同一 client_event_id 重放不重复计数（离线补齐无重复）。"""
    user = await register(client)
    question_id = await _seed_question(sessionmaker)
    event_id = uuid.uuid4().hex
    payload = {
        "question_id": question_id,
        "answer": "A",
        "source": "practice",
        "client_event_id": event_id,
    }
    first = await client.post("/v1/practice/answer", json=payload, headers=headers_of(user))
    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    assert first.json()["is_correct"] is True

    replay = await client.post("/v1/practice/answer", json=payload, headers=headers_of(user))
    assert replay.status_code == 200
    assert replay.json()["duplicate"] is True
    assert replay.json()["is_correct"] is True

    async with sessionmaker() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(PracticeRecord)
            .where(PracticeRecord.client_event_id == event_id)
        )
    assert count == 1
