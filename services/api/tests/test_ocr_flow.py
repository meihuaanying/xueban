"""OCR 流程测试（M8 / T8.1，F-04 / F-36）：识别匹配、降级路径与步骤定位。"""

from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models import Question, QuestionStatus, QuestionType
from app.services import ocr_client
from tests.helpers import headers_of, register

MATCH_STEM = "计算 18 乘以 5 等于多少？"


async def _seed_question(sessionmaker: async_sessionmaker[AsyncSession]) -> str:
    async with sessionmaker() as session:
        question = Question(
            subject="math",
            stage="junior",
            qtype=QuestionType.CHOICE,
            stem=MATCH_STEM,
            options={"A": "90", "B": "88", "C": "91", "D": "92"},
            answer="A",
            analysis="按乘法口诀计算。正确选项为 A。",
            difficulty=2,
            source="test",
            status=QuestionStatus.PUBLISHED,
        )
        session.add(question)
        await session.flush()
        question_id = str(question.id)
        await session.commit()
        return question_id


async def test_photo_search_matches_question_without_answer(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_id = await _seed_question(sessionmaker)
    user = await register(client)
    response = await client.post(
        "/v1/tools/photo-search",
        json={"ocr_text": MATCH_STEM, "subject": "math"},
        headers=headers_of(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["match_found"] is True
    assert body["question_id"] == question_id
    assert body["tutor_entry"] == "/v1/tutor/session"
    # 红线：响应中不得出现答案或解析
    raw = response.text
    assert '"answer"' not in raw
    assert "正确选项为 A" not in raw


async def test_photo_search_no_match_guides_tutor(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_question(sessionmaker)
    user = await register(client)
    response = await client.post(
        "/v1/tools/photo-search",
        json={"ocr_text": "完全无关的一段文字内容测试", "subject": "math"},
        headers=headers_of(user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["match_found"] is False
    assert body["tutor_entry"] == "/v1/tutor/session"


async def test_photo_search_degradation_path(client: AsyncClient) -> None:
    """无文本且无图片（或 OCR 不可用）→ 降级提示，不阻塞流程。"""
    user = await register(client)
    response = await client.post(
        "/v1/tools/photo-search",
        json={"image_key": "uploads/unknown.jpg", "subject": "math"},
        headers=headers_of(user),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert body["degradation_hint"]
    assert "手动" in body["degradation_hint"]


async def test_ocr_service_call_contract() -> None:
    """OCR 服务契约：真实调用走 HTTP（MockTransport 断言请求/响应映射）。"""
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append({"url": str(request.url), "body": request.content.decode()})
        return httpx.Response(200, json={"text": "从图片识别的题目文本", "confidence": 0.93})

    result = await ocr_client.recognize(
        settings=settings,
        image_key="uploads/handwriting.png",
        ocr_text=None,
        transport=httpx.MockTransport(handler),
    )
    assert result.degraded is False
    assert result.text == "从图片识别的题目文本"
    assert captured and captured[0]["url"].endswith("/v1/ocr")


async def test_ocr_service_failure_degrades() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(501, json={"detail": "not implemented"})

    result = await ocr_client.recognize(
        settings=settings,
        image_key="uploads/handwriting.png",
        ocr_text=None,
        transport=httpx.MockTransport(handler),
    )
    assert result.degraded is True
    assert result.hint


async def test_handwriting_locates_first_error() -> None:
    """F-04：定位第几步出错（数学步骤数值敏感）。"""
    reference = "2x + 3 = 7\n2x = 4\nx = 2"
    transcript = "2x + 3 = 7\n2x = 5\nx = 2.5"
    result = await ocr_client.diagnose_handwriting(
        settings=settings,
        image_key=None,
        ocr_text=transcript,
        reference_solution=reference,
    )
    assert result.degraded is False
    assert result.first_error_step == 1
    assert result.steps[0].is_error is False
    assert result.steps[1].is_error is True
    assert "第 2 步" in result.advice

    correct = await ocr_client.diagnose_handwriting(
        settings=settings,
        image_key=None,
        ocr_text=reference,
        reference_solution=reference,
    )
    assert correct.first_error_step is None
    assert "一致" in correct.advice


async def test_handwriting_degraded_without_text() -> None:
    result = await ocr_client.diagnose_handwriting(
        settings=settings,
        image_key=None,
        ocr_text=None,
        reference_solution="x = 2",
    )
    assert result.degraded is True
    assert "人工确认" in result.advice


async def test_handwriting_api(client: AsyncClient) -> None:
    user = await register(client)
    response = await client.post(
        "/v1/diagnosis/handwriting",
        json={
            "ocr_text": "2x + 3 = 7\n2x = 5\nx = 2.5",
            "reference_solution": "2x + 3 = 7\n2x = 4\nx = 2",
        },
        headers=headers_of(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["first_error_step"] == 1
    assert body["degraded"] is False


@pytest.mark.parametrize("image_key", [None, "uploads/x.png"])
async def test_recognize_prefers_confirmed_text(image_key: str | None) -> None:
    result = await ocr_client.recognize(
        settings=settings, image_key=image_key, ocr_text="人工确认的文本"
    )
    assert result.degraded is False
    assert result.text == "人工确认的文本"
    assert result.confidence == 1.0
