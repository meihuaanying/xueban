"""守护型讲解测试（T3.4 / F-11 红线）：状态机、分层提示、SSE、求助层级记录。"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.errors import AppError
from app.models import (
    ChatMessage,
    ChatSession,
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
)
from app.services import tutor_service
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from app.services.tutor_service import build_hint_messages, next_hint_level
from tests.helpers import headers_of, register

# ---------- 状态机（红线：不可跳层） ----------


def test_next_hint_level_advances_one_step() -> None:
    assert next_hint_level(0) == 1
    assert next_hint_level(1) == 2
    assert next_hint_level(2) == 3


def test_next_hint_level_rejects_skipping() -> None:
    with pytest.raises(AppError) as excinfo:
        next_hint_level(0, requested=3)
    assert excinfo.value.code == "TUTOR_LEVEL_SKIPPED"
    with pytest.raises(AppError):
        next_hint_level(1, requested=3)


def test_next_hint_level_rejects_backwards() -> None:
    with pytest.raises(AppError) as excinfo:
        next_hint_level(2, requested=1)
    assert excinfo.value.code == "TUTOR_LEVEL_SKIPPED"


def test_next_hint_level_exhausted() -> None:
    with pytest.raises(AppError) as excinfo:
        next_hint_level(3)
    assert excinfo.value.code == "TUTOR_NO_MORE_HINTS"


def test_next_hint_level_requested_correct_passes() -> None:
    assert next_hint_level(0, requested=1) == 1
    assert next_hint_level(2, requested=3) == 3


# ---------- 提示词分层口径 ----------


def _question(options: dict[str, str] | None = None) -> Question:
    return Question(
        subject="math",
        stage="junior",
        qtype=QuestionType.CHOICE if options else QuestionType.FILL,
        stem="解方程：2x + 3 = 7",
        options=options,
        answer="2",
        analysis="移项后除以 2。",
        status=QuestionStatus.PUBLISHED,
    )


def test_level1_prompt_forbids_answer() -> None:
    messages = build_hint_messages(_question(), 1, [])
    content = messages[1]["content"]
    assert "不要给出或暗示最终答案" in content
    assert "第 1 层" in content
    assert messages[0]["content"] == tutor_service.TUTOR_SYSTEM_PROMPT


def test_level3_prompt_asks_full_solution() -> None:
    messages = build_hint_messages(_question(), 3, [])
    assert "完整解答" in messages[1]["content"]


def test_prompt_includes_history() -> None:
    messages = build_hint_messages(_question(), 2, ["先想想未知数在哪一边"])
    content = messages[1]["content"]
    assert "此前已给过的提示" in content
    assert "先想想未知数在哪一边" in content


def test_prompt_includes_options_block() -> None:
    messages = build_hint_messages(_question({"A": "1", "B": "2"}), 1, [])
    assert "A. 1" in messages[1]["content"]


# ---------- API ----------


def _handler(
    content: str = "先想一想：等号两边应该同时减去几？",
    *,
    captured: list[dict[str, object]] | None = None,
    stream_chunks: tuple[str, ...] = ("先", "想", "想"),
):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if captured is not None:
            captured.append(payload)
        if payload.get("stream"):
            lines = [
                f"data: {json.dumps({'choices': [{'delta': {'content': chunk}}]})}"
                for chunk in stream_chunks
            ]
            lines.append("data: [DONE]")
            body = ("\n\n".join(lines) + "\n\n").encode("utf-8")
            return httpx.Response(
                200, content=body, headers={"content-type": "text/event-stream"}
            )
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {"total_tokens": 12},
            },
        )

    return handler


def _install_llm(app: object, handler: object) -> None:
    settings = Settings(
        litellm_base_url="http://llm.test",
        litellm_master_key="sk-test",
        llm_max_retries=0,
        llm_retry_backoff_seconds=0.0,
    )
    observability = ObservabilityService(settings)
    app.state.llm = LlmClient(  # type: ignore[attr-defined]
        settings, observability, transport=httpx.MockTransport(handler)  # type: ignore[arg-type]
    )


async def _seed_question(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> uuid.UUID:
    async with sessionmaker() as session:
        kp = KnowledgePoint(code="math.test.tutor", name="一元一次方程", subject="math")
        session.add(kp)
        await session.flush()
        question = Question(
            subject="math",
            stage="junior",
            qtype=QuestionType.FILL,
            stem="解方程：2x + 3 = 7",
            answer="2",
            analysis="移项后除以 2。",
            status=QuestionStatus.PUBLISHED,
        )
        session.add(question)
        await session.flush()
        session.add(QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id))
        await session.commit()
        return question.id


async def _create_session(
    client: AsyncClient, headers: dict[str, str], question_id: uuid.UUID
) -> str:
    response = await client.post(
        "/v1/tutor/session", json={"question_id": str(question_id)}, headers=headers
    )
    assert response.status_code == 201, response.text
    return str(response.json()["session_id"])


async def test_start_session_red_line(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    response = await client.post(
        "/v1/tutor/session", json={"question_id": str(question_id)}, headers=headers_of(payload)
    )
    assert response.status_code == 201
    body = response.json()
    assert body["hint_level"] == 0
    assert body["question"]["knowledge_points"] == ["一元一次方程"]
    assert "answer" not in body
    assert "answer" not in body["question"]


async def test_start_session_unknown_question(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/tutor/session", json={"question_id": str(uuid.uuid4())}, headers=headers_of(payload)
    )
    assert response.status_code == 404


async def test_hint_three_levels_flow(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(app, _handler())
    session_id = await _create_session(client, headers, question_id)

    first = await client.post(f"/v1/tutor/{session_id}/hint", json={}, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["level"] == 1
    assert first.json()["level_name"] == "思路提示"
    assert first.json()["next_level"] == 2

    second = await client.post(f"/v1/tutor/{session_id}/hint", json={}, headers=headers)
    assert second.json()["level"] == 2

    third = await client.post(
        f"/v1/tutor/{session_id}/hint", json={"level": 3}, headers=headers
    )
    assert third.json()["level"] == 3
    assert third.json()["next_level"] is None

    async with sessionmaker() as session:
        chat = await session.get(ChatSession, uuid.UUID(session_id))
        assert chat is not None and chat.hint_level == 3
        count = await session.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == chat.id)
        )
        assert count == 3

    exhausted = await client.post(f"/v1/tutor/{session_id}/hint", json={}, headers=headers)
    assert exhausted.status_code == 400
    assert exhausted.json()["code"] == "TUTOR_NO_MORE_HINTS"


async def test_hint_skip_rejected(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(app, _handler())
    session_id = await _create_session(client, headers, question_id)

    response = await client.post(
        f"/v1/tutor/{session_id}/hint", json={"level": 3}, headers=headers
    )
    assert response.status_code == 400
    assert response.json()["code"] == "TUTOR_LEVEL_SKIPPED"

    # 先到第 2 层再申请第 4 层（schema 拦截）
    await client.post(f"/v1/tutor/{session_id}/hint", json={}, headers=headers)
    await client.post(f"/v1/tutor/{session_id}/hint", json={}, headers=headers)
    invalid_level = await client.post(
        f"/v1/tutor/{session_id}/hint", json={"level": 4}, headers=headers
    )
    assert invalid_level.status_code == 422


async def test_hint_solo_locked_denied(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(app, _handler())
    session_id = await _create_session(client, headers, question_id)

    async with sessionmaker() as session:
        chat = await session.get(ChatSession, uuid.UUID(session_id))
        assert chat is not None
        chat.solo_locked = True
        await session.commit()

    response = await client.post(f"/v1/tutor/{session_id}/hint", json={}, headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "TUTOR_SOLO_LOCKED"


async def test_hint_other_user_denied(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    owner = await register(client)
    intruder = await register(client)
    _install_llm(app, _handler())
    session_id = await _create_session(client, headers_of(owner), question_id)
    response = await client.post(
        f"/v1/tutor/{session_id}/hint", json={}, headers=headers_of(intruder)
    )
    assert response.status_code == 403


async def test_hint_unknown_session(client: AsyncClient, app: object) -> None:
    payload = await register(client)
    _install_llm(app, _handler())
    response = await client.post(
        f"/v1/tutor/{uuid.uuid4()}/hint", json={}, headers=headers_of(payload)
    )
    assert response.status_code == 404


async def test_hint_requires_auth(client: AsyncClient) -> None:
    response = await client.post(f"/v1/tutor/{uuid.uuid4()}/hint", json={})
    assert response.status_code == 401


async def test_hint_prompt_contains_history(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    captured: list[dict[str, object]] = []
    _install_llm(app, _handler(captured=captured))
    session_id = await _create_session(client, headers, question_id)

    await client.post(f"/v1/tutor/{session_id}/hint", json={}, headers=headers)
    await client.post(f"/v1/tutor/{session_id}/hint", json={}, headers=headers)
    assert len(captured) == 2
    second_messages = captured[1]["messages"]
    assert isinstance(second_messages, list)
    assert "此前已给过的提示" in str(second_messages[-1])


async def test_stream_hint_sse(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(app, _handler(stream_chunks=("先", "想", "想")))
    session_id = await _create_session(client, headers, question_id)

    response = await client.post(
        f"/v1/tutor/{session_id}/hint/stream", json={}, headers=headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: start" in body
    assert "event: delta" in body
    assert "event: done" in body
    assert "先想想" in body

    async with sessionmaker() as session:
        chat = await session.get(ChatSession, uuid.UUID(session_id))
        assert chat is not None and chat.hint_level == 1
        count = await session.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == chat.id)
        )
    assert count == 1


async def test_stream_hint_skip_rejected_before_stream(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(app, _handler())
    session_id = await _create_session(client, headers, question_id)
    response = await client.post(
        f"/v1/tutor/{session_id}/hint/stream", json={"level": 3}, headers=headers
    )
    assert response.status_code == 400
    assert response.json()["code"] == "TUTOR_LEVEL_SKIPPED"
