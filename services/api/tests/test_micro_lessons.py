"""微课测试（T3.5 / F-16）：讲解稿字数约束、失败重试、音频直链。"""

from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import KnowledgePoint, MicroLessonStatus
from app.services import lesson_service
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from app.services.storage_service import StorageService
from app.services.tts import MockTtsProvider, TtsError, VendorTtsProvider
from tests.helpers import headers_of, register

GOOD_SCRIPT = "同学们好，这节课我们学习一元一次方程。" * 40  # ≈ 760 字


def _handler(content: str):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {"total_tokens": 400},
            },
        )

    return handler


def _llm(content: str) -> LlmClient:
    settings = Settings(
        litellm_base_url="http://llm.test",
        litellm_master_key="sk-test",
        llm_max_retries=0,
        llm_retry_backoff_seconds=0.0,
    )
    observability = ObservabilityService(settings)
    return LlmClient(settings, observability, transport=httpx.MockTransport(_handler(content)))


async def _seed_kp(sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with sessionmaker() as session:
        kp = KnowledgePoint(code="math.test.lesson", name="一元一次方程", subject="math")
        session.add(kp)
        await session.commit()
        return kp.id


async def test_create_lesson_unknown_kp(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/micro-lessons",
        json={"knowledge_point_id": str(uuid.uuid4())},
        headers=headers_of(payload),
    )
    assert response.status_code == 404


async def test_create_lesson_pending(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    kp_id = await _seed_kp(sessionmaker)
    payload = await register(client)
    response = await client.post(
        "/v1/micro-lessons",
        json={"knowledge_point_id": str(kp_id)},
        headers=headers_of(payload),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["lesson_id"]
    assert "微课" in body["title"]


async def test_generate_lesson_success_and_audio(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    kp_id = await _seed_kp(sessionmaker)
    payload = await register(client)
    created = await client.post(
        "/v1/micro-lessons",
        json={"knowledge_point_id": str(kp_id)},
        headers=headers_of(payload),
    )
    lesson_id = uuid.UUID(created.json()["lesson_id"])

    llm = _llm(GOOD_SCRIPT)
    try:
        async with sessionmaker() as session:
            lesson = await lesson_service.generate_micro_lesson(
                session,
                lesson_id=lesson_id,
                llm=llm,
                tts=MockTtsProvider(),
                storage=StorageService(Settings()),
            )
            await session.commit()
    finally:
        await llm.aclose()

    assert lesson.status == MicroLessonStatus.READY
    assert lesson.script is not None
    assert 600 <= lesson.char_count <= 1000
    assert lesson.audio_key is not None
    assert lesson.audio_mime == "audio/wav"

    audio = await client.get(
        f"/v1/micro-lessons/{lesson_id}/audio", headers=headers_of(payload)
    )
    assert audio.status_code == 200, audio.text
    body = audio.json()
    assert body["mime"] == "audio/wav"
    async with httpx.AsyncClient() as raw:
        fetched = await raw.get(body["url"])
    assert fetched.status_code == 200
    assert fetched.content[:4] == b"RIFF"


async def test_generate_lesson_length_violation_fails_after_retries(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    kp_id = await _seed_kp(sessionmaker)
    payload = await register(client)
    created = await client.post(
        "/v1/micro-lessons",
        json={"knowledge_point_id": str(kp_id)},
        headers=headers_of(payload),
    )
    lesson_id = uuid.UUID(created.json()["lesson_id"])

    llm = _llm("太短了")
    try:
        async with sessionmaker() as session:
            lesson = await lesson_service.generate_micro_lesson(
                session,
                lesson_id=lesson_id,
                llm=llm,
                tts=MockTtsProvider(),
                storage=StorageService(Settings()),
            )
            await session.commit()
    finally:
        await llm.aclose()

    assert lesson.status == MicroLessonStatus.FAILED
    assert lesson.retries == 3
    assert lesson.error is not None and "字数" in lesson.error

    audio = await client.get(
        f"/v1/micro-lessons/{lesson_id}/audio", headers=headers_of(payload)
    )
    assert audio.status_code == 409
    assert audio.json()["code"] == "MICRO_LESSON_NOT_READY"


async def test_generate_lesson_tts_failure(
    sessionmaker: async_sessionmaker[AsyncSession],
    client: AsyncClient,
) -> None:
    kp_id = await _seed_kp(sessionmaker)
    payload = await register(client)
    created = await client.post(
        "/v1/micro-lessons",
        json={"knowledge_point_id": str(kp_id)},
        headers=headers_of(payload),
    )
    lesson_id = uuid.UUID(created.json()["lesson_id"])

    llm = _llm(GOOD_SCRIPT)
    try:
        async with sessionmaker() as session:
            lesson = await lesson_service.generate_micro_lesson(
                session,
                lesson_id=lesson_id,
                llm=llm,
                tts=VendorTtsProvider(""),  # 未接入 → 抛 TtsError
                storage=StorageService(Settings()),
            )
            await session.commit()
    finally:
        await llm.aclose()

    assert lesson.status == MicroLessonStatus.FAILED
    assert lesson.error is not None and "音频合成失败" in lesson.error


async def test_audio_other_user_denied(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    kp_id = await _seed_kp(sessionmaker)
    owner = await register(client)
    intruder = await register(client)
    created = await client.post(
        "/v1/micro-lessons",
        json={"knowledge_point_id": str(kp_id)},
        headers=headers_of(owner),
    )
    lesson_id = created.json()["lesson_id"]
    response = await client.get(
        f"/v1/micro-lessons/{lesson_id}/audio", headers=headers_of(intruder)
    )
    assert response.status_code == 403


async def test_micro_lesson_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/micro-lessons", json={"knowledge_point_id": str(uuid.uuid4())}
    )
    assert response.status_code == 401


def test_worker_registers_micro_lesson_task() -> None:
    from app.worker import WorkerSettings, generate_micro_lesson

    assert generate_micro_lesson in WorkerSettings.functions


def test_mock_tts_produces_wav() -> None:
    provider = MockTtsProvider()
    data, mime = asyncio.run(provider.synthesize("测试文本"))
    assert mime == "audio/wav"
    assert data[:4] == b"RIFF"


def test_vendor_tts_not_implemented() -> None:
    provider = VendorTtsProvider("key")
    with pytest.raises(TtsError):
        asyncio.run(provider.synthesize("测试"))
