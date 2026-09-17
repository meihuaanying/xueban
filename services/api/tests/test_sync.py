"""多端同步与离线幂等测试（M9 / T9.1~T9.2，F-39）。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import PracticeRecord, Question, QuestionStatus, QuestionType
from tests.helpers import headers_of, register


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
    """F-39：WebSocket 推送版本与摘要（3 秒内收到首帧）。"""
    user = await register(client)
    token = user["access_token"]

    class FakeWebSocket:
        def __init__(self) -> None:
            self.app = _app
            self.sent: list[dict[str, object]] = []
            self.closed: int | None = None
            self._first = True

        async def accept(self) -> None:
            return None

        async def send_json(self, payload: dict[str, object]) -> None:
            self.sent.append(payload)
            if self._first:
                self._first = False
                raise WebSocketStop()

        async def close(self, code: int = 1000) -> None:
            self.closed = code

    class WebSocketStop(Exception):
        pass

    # 直接调用路由函数（绕过真实网络），验证推送内容与鉴权
    from app.api.routes import sync as sync_route

    _app = client._transport.app  # type: ignore[attr-defined]
    fake = FakeWebSocket()
    with pytest.raises(WebSocketStop):
        await sync_route.sync_ws(fake, token=token)  # type: ignore[arg-type]
    assert fake.sent and "version" in fake.sent[0]
    assert "summary" in fake.sent[0]


async def test_websocket_rejects_bad_token(client: AsyncClient) -> None:
    from app.api.routes import sync as sync_route

    class FakeWebSocket:
        def __init__(self) -> None:
            self.app = client._transport.app  # type: ignore[attr-defined]
            self.closed: int | None = None

        async def close(self, code: int = 1000) -> None:
            self.closed = code

    fake = FakeWebSocket()
    await sync_route.sync_ws(fake, token="invalid-token")  # type: ignore[arg-type]
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
