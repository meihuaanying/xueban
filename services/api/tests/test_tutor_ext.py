"""讲解扩展测试（T3.5 / F-12~F-14）：多解法、类比、变式题与回炉。"""

from __future__ import annotations

import json
import uuid

import httpx
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import (
    ChatSession,
    KnowledgePoint,
    MasteryRecord,
    MistakeBookEntry,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
)
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from tests.helpers import headers_of, register


def _handler(content: str):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {"total_tokens": 32},
            },
        )

    return handler


def _install_llm(app: object, content: str) -> None:
    settings = Settings(
        litellm_base_url="http://llm.test",
        litellm_master_key="sk-test",
        llm_max_retries=0,
        llm_retry_backoff_seconds=0.0,
    )
    observability = ObservabilityService(settings)
    app.state.llm = LlmClient(  # type: ignore[attr-defined]
        settings, observability, transport=httpx.MockTransport(_handler(content))
    )


async def _seed_question(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    qtype: QuestionType = QuestionType.FILL,
    answer: str = "2",
) -> uuid.UUID:
    async with sessionmaker() as session:
        kp = KnowledgePoint(code="math.test.ext", name="一元一次方程", subject="math")
        session.add(kp)
        await session.flush()
        question = Question(
            subject="math",
            stage="junior",
            qtype=qtype,
            stem="解方程：2x + 3 = 7",
            options=(
                {"A": "1", "B": "2", "C": "3", "D": "4"}
                if qtype == QuestionType.CHOICE
                else None
            ),
            answer=answer,
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


# ---------- F-12 多解法 ----------


async def test_alt_solutions_with_sympy_verification(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(
        app,
        json.dumps(
            {
                "solutions": [
                    {
                        "title": "移项法",
                        "steps": ["两边同减 3 得 $2x = 4$", "两边同除以 2 得 $x = 2$"],
                        "scenario": "最通用的解法",
                    },
                    {
                        "title": "数轴法",
                        "steps": ["在数轴上找到满足方程的点，得到结果 $x = 2$"],
                        "scenario": "适合理解方程含义",
                    },
                ]
            },
            ensure_ascii=False,
        ),
    )
    session_id = await _create_session(client, headers, question_id)
    response = await client.post(
        f"/v1/tutor/{session_id}/alt-solutions", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["solutions"]) == 2
    assert body["checked_count"] == 2
    assert body["verified_count"] == 2
    assert all(item["answer_verified"] for item in body["solutions"])


async def test_alt_solutions_flags_wrong_math(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(
        app,
        json.dumps(
            {
                "solutions": [
                    {"title": "正确解", "steps": ["解得 $x = 2$"], "scenario": "常规"},
                    {"title": "错误解", "steps": ["解得 $x = 5$"], "scenario": "错误示范"},
                ]
            },
            ensure_ascii=False,
        ),
    )
    session_id = await _create_session(client, headers, question_id)
    response = await client.post(f"/v1/tutor/{session_id}/alt-solutions", headers=headers)
    body = response.json()
    assert body["verified_count"] == 1
    flags = {item["title"]: item["answer_verified"] for item in body["solutions"]}
    assert flags == {"正确解": True, "错误解": False}


async def test_alt_solutions_requires_two(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(
        app,
        json.dumps({"solutions": [{"title": "唯一解", "steps": ["$x=2$"], "scenario": "s"}]}),
    )
    session_id = await _create_session(client, headers, question_id)
    response = await client.post(f"/v1/tutor/{session_id}/alt-solutions", headers=headers)
    assert response.status_code == 502
    assert response.json()["code"] == "ALT_SOLUTIONS_BAD_OUTPUT"


async def test_alt_solutions_invalid_json(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(app, "这里不是 JSON")
    session_id = await _create_session(client, headers, question_id)
    response = await client.post(f"/v1/tutor/{session_id}/alt-solutions", headers=headers)
    assert response.status_code == 502


async def test_alt_solutions_solo_locked(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(app, "{}")
    session_id = await _create_session(client, headers, question_id)
    async with sessionmaker() as session:
        chat = await session.get(ChatSession, uuid.UUID(session_id))
        assert chat is not None
        chat.solo_locked = True
        await session.commit()
    response = await client.post(f"/v1/tutor/{session_id}/alt-solutions", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "TUTOR_SOLO_LOCKED"


# ---------- F-13 生活化类比 ----------


async def test_analogy_success(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(
        app,
        json.dumps(
            {
                "analogy": "解方程就像用天平称重，两边要同时增减同样的重量。",
                "mapping": "等式两边同减 3 就像天平两边同时拿走 3 克。",
                "caveat": "天平不能出现负数，但方程可以有。",
            },
            ensure_ascii=False,
        ),
    )
    session_id = await _create_session(client, headers, question_id)
    response = await client.post(f"/v1/tutor/{session_id}/analogy", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "天平" in body["analogy"]
    assert body["mapping"]
    assert body["caveat"]


async def test_analogy_missing_content(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(app, json.dumps({"analogy": ""}))
    session_id = await _create_session(client, headers, question_id)
    response = await client.post(f"/v1/tutor/{session_id}/analogy", headers=headers)
    assert response.status_code == 502
    assert response.json()["code"] == "ANALOGY_BAD_OUTPUT"


# ---------- F-14 变式题 ----------


async def test_variants_generation_and_storage(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(
        app,
        json.dumps(
            {
                "variants": [
                    {
                        "stem": "解方程：3x + 2 = 11",
                        "answer": "3",
                        "analysis": "移项后得 3x = 9，x = 3。",
                        "options": None,
                    },
                    {
                        "stem": "若 5x - 4 = 16，求 x。",
                        "answer": "4",
                        "analysis": "5x = 20，x = 4。",
                        "options": None,
                    },
                ]
            },
            ensure_ascii=False,
        ),
    )
    session_id = await _create_session(client, headers, question_id)
    response = await client.post(f"/v1/tutor/{session_id}/variants", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["variants"]) == 2
    assert "answer" not in body["variants"][0]

    async with sessionmaker() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(Question)
            .where(Question.source == "tutor-variant")
        )
        kp_links = await session.scalar(
            select(func.count()).select_from(QuestionKnowledgePoint)
        )
    assert count == 2
    assert kp_links == 3  # 原题 1 + 变式 2


async def test_variants_choice_requires_options(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker, qtype=QuestionType.CHOICE)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(
        app,
        json.dumps(
            {
                "variants": [
                    {
                        "stem": "选择正确答案",
                        "answer": "A",
                        "analysis": "略",
                        "options": None,
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    session_id = await _create_session(client, headers, question_id)
    response = await client.post(f"/v1/tutor/{session_id}/variants", headers=headers)
    assert response.status_code == 502
    assert response.json()["code"] == "VARIANTS_BAD_OUTPUT"


async def _generate_variant(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> tuple[dict[str, str], str, str]:
    """生成一道变式题，返回 (用户令牌, 讲解会话 id, 变式题 id)。"""
    question_id = await _seed_question(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    _install_llm(
        app,
        json.dumps(
            {
                "variants": [
                    {
                        "stem": "解方程：3x + 2 = 11",
                        "answer": "3",
                        "analysis": "x = 3。",
                        "options": None,
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    session_id = await _create_session(client, headers, question_id)
    response = await client.post(f"/v1/tutor/{session_id}/variants", headers=headers)
    assert response.status_code == 200, response.text
    variant_id = str(response.json()["variants"][0]["question_id"])
    return payload, session_id, variant_id


async def test_variant_answer_correct_records_mastery(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload, session_id, variant_id = await _generate_variant(client, app, sessionmaker)
    response = await client.post(
        f"/v1/tutor/{session_id}/variants/{variant_id}/answer",
        json={"answer": "3"},
        headers=headers_of(payload),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_correct"] is True
    assert body["back_to_tutor"] is None
    async with sessionmaker() as session:
        mastery_count = await session.scalar(select(func.count()).select_from(MasteryRecord))
    assert mastery_count == 1


async def test_variant_answer_wrong_back_to_tutor(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload, session_id, variant_id = await _generate_variant(client, app, sessionmaker)
    response = await client.post(
        f"/v1/tutor/{session_id}/variants/{variant_id}/answer",
        json={"answer": "错误答案"},
        headers=headers_of(payload),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_correct"] is False
    assert body["back_to_tutor"] is not None
    assert body["back_to_tutor"]["session_id"]
    assert "回炉" in body["back_to_tutor"]["message"]

    async with sessionmaker() as session:
        mistakes = await session.scalar(select(func.count()).select_from(MistakeBookEntry))
        sessions = await session.scalar(select(func.count()).select_from(ChatSession))
    assert mistakes == 1
    assert sessions == 2  # 原讲解会话 + 回炉会话


async def test_variant_answer_other_user_denied(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    _, session_id, variant_id = await _generate_variant(client, app, sessionmaker)
    intruder = await register(client)
    response = await client.post(
        f"/v1/tutor/{session_id}/variants/{variant_id}/answer",
        json={"answer": "3"},
        headers=headers_of(intruder),
    )
    assert response.status_code == 403


async def test_tutor_ext_requires_auth(client: AsyncClient) -> None:
    response = await client.post(f"/v1/tutor/{uuid.uuid4()}/alt-solutions")
    assert response.status_code == 401
