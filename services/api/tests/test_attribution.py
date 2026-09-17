"""错因归因测试（T3.2 / F-02）：解析契约、五类枚举、API 行为。"""

from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.errors import LlmError
from app.models import (
    MistakeBookEntry,
    Question,
    QuestionStatus,
    QuestionType,
    User,
)
from app.services.attribution_service import parse_attribution
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from tests.helpers import headers_of, register

# ---------- 解析契约 ----------


def test_parse_plain_json() -> None:
    reason, confidence, explanation = parse_attribution(
        '{"reason": "concept", "confidence": 0.8, "explanation": "概念混淆"}'
    )
    assert reason == "concept"
    assert confidence == 0.8
    assert explanation == "概念混淆"


def test_parse_code_fence() -> None:
    reason, _, _ = parse_attribution(
        '```json\n{"reason": "computation", "confidence": 0.5, "explanation": "算错"}\n```'
    )
    assert reason == "computation"


def test_parse_with_extra_text() -> None:
    reason, _, _ = parse_attribution(
        '分析结果如下：{"reason": "method", "confidence": 0.6, "explanation": "步骤不全"} 以上。'
    )
    assert reason == "method"


def test_parse_invalid_reason_raises() -> None:
    with pytest.raises(LlmError) as excinfo:
        parse_attribution('{"reason": "laziness", "confidence": 0.9}')
    assert excinfo.value.code == "ATTRIBUTION_BAD_OUTPUT"


def test_parse_non_dict_raises() -> None:
    with pytest.raises(LlmError):
        parse_attribution("[1, 2, 3]")


def test_parse_confidence_clamped() -> None:
    _, confidence, _ = parse_attribution('{"reason": "reading", "confidence": 5}')
    assert confidence == 1.0
    _, confidence_low, _ = parse_attribution('{"reason": "reading", "confidence": "bad"}')
    assert confidence_low == 0.0


# ---------- API ----------


def _handler(payload: str, status_code: int = 200):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if status_code != 200:
            return httpx.Response(status_code, text=payload)
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content": payload}}],
                "usage": {"total_tokens": 10},
            },
        )

    return handler


def _install_llm(app: object, payload: str, status_code: int = 200) -> None:
    """把应用级 LLM 客户端替换为 MockTransport 版本。"""
    settings = Settings(
        litellm_base_url="http://llm.test",
        litellm_master_key="sk-test",
        llm_max_retries=0,
        llm_retry_backoff_seconds=0.0,
    )
    observability = ObservabilityService(settings)
    app.state.llm = LlmClient(  # type: ignore[attr-defined]
        settings, observability, transport=httpx.MockTransport(_handler(payload, status_code))
    )


async def _seed_entry(
    sessionmaker: async_sessionmaker[AsyncSession], phone: str
) -> uuid.UUID:
    async with sessionmaker() as session:
        user = (await session.execute(select(User).where(User.phone == phone))).scalar_one()
        question = Question(
            subject="math",
            stage="junior",
            qtype=QuestionType.FILL,
            stem="计算：3 + 4 = ?",
            answer="7",
            analysis="直接相加。",
            status=QuestionStatus.PUBLISHED,
        )
        session.add(question)
        await session.flush()
        entry = MistakeBookEntry(
            user_id=user.id, question_id=question.id, wrong_answer="8", source="practice"
        )
        session.add(entry)
        await session.commit()
        return entry.id


async def test_attribute_success(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    entry_id = await _seed_entry(sessionmaker, payload["phone"])
    _install_llm(
        app,
        '{"reason": "computation", "confidence": 0.92, "explanation": "思路正确但加法出错"}',
    )
    response = await client.post(
        f"/v1/mistakes/{entry_id}/attribute", headers=headers_of(payload)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reason"] == "computation"
    assert body["reason_label"] == "计算失误"
    assert body["confidence"] == 0.92
    async with sessionmaker() as session:
        entry = await session.get(MistakeBookEntry, entry_id)
    assert entry is not None
    assert entry.error_reason == "computation"


async def test_attribute_invalid_output_502(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    entry_id = await _seed_entry(sessionmaker, payload["phone"])
    _install_llm(app, "我不知道怎么判断")
    response = await client.post(
        f"/v1/mistakes/{entry_id}/attribute", headers=headers_of(payload)
    )
    assert response.status_code == 502
    assert response.json()["code"] == "ATTRIBUTION_BAD_OUTPUT"


async def test_attribute_llm_failure_503(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    entry_id = await _seed_entry(sessionmaker, payload["phone"])
    _install_llm(app, "upstream boom", status_code=500)
    response = await client.post(
        f"/v1/mistakes/{entry_id}/attribute", headers=headers_of(payload)
    )
    assert response.status_code == 503
    assert response.json()["code"] == "LLM_UPSTREAM_ERROR"


async def test_attribute_other_user_denied(
    client: AsyncClient, app: object, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    owner = await register(client)
    intruder = await register(client)
    entry_id = await _seed_entry(sessionmaker, owner["phone"])
    _install_llm(app, '{"reason": "concept", "confidence": 0.5, "explanation": "x"}')
    response = await client.post(
        f"/v1/mistakes/{entry_id}/attribute", headers=headers_of(intruder)
    )
    assert response.status_code == 403


async def test_attribute_entry_not_found(
    client: AsyncClient, app: object
) -> None:
    payload = await register(client)
    _install_llm(app, '{"reason": "concept", "confidence": 0.5, "explanation": "x"}')
    response = await client.post(
        f"/v1/mistakes/{uuid.uuid4()}/attribute", headers=headers_of(payload)
    )
    assert response.status_code == 404


async def test_attribute_requires_auth(client: AsyncClient) -> None:
    response = await client.post(f"/v1/mistakes/{uuid.uuid4()}/attribute")
    assert response.status_code == 401
