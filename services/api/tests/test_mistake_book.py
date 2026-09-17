"""错题本测试（T3.6 / F-18）：分组统计、筛选、重练、PDF 导出。"""

from __future__ import annotations

import uuid
from io import BytesIO

from httpx import AsyncClient
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    KnowledgePoint,
    MistakeBookEntry,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
)
from tests.helpers import headers_of, register


async def _seed_questions(
    sessionmaker: async_sessionmaker[AsyncSession], *, count: int = 2
) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    async with sessionmaker() as session:
        kp = KnowledgePoint(code="math.test.mb", name="方程", subject="math")
        session.add(kp)
        await session.flush()
        for index in range(count):
            question = Question(
                subject="math",
                stage="junior",
                qtype=QuestionType.FILL,
                stem=f"[方程] 解方程：{index + 1}x = {index + 1}",
                answer="1",
                analysis=f"两边同除以 {index + 1}，得到 x = 1。",
                status=QuestionStatus.PUBLISHED,
            )
            session.add(question)
            await session.flush()
            session.add(QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id))
            ids.append(question.id)
        await session.commit()
    return ids


async def _collect_mistakes(
    client: AsyncClient, headers: dict[str, str], question_ids: list[uuid.UUID]
) -> None:
    for question_id in question_ids:
        response = await client.post(
            "/v1/practice/answer",
            json={"question_id": str(question_id), "answer": "错误答案"},
            headers=headers,
        )
        assert response.status_code == 200, response.text


async def _set_reason(
    sessionmaker: async_sessionmaker[AsyncSession], question_id: uuid.UUID, reason: str
) -> None:
    async with sessionmaker() as session:
        entry = (
            await session.execute(
                select(MistakeBookEntry).where(MistakeBookEntry.question_id == question_id)
            )
        ).scalar_one()
        entry.error_reason = reason
        await session.commit()


async def test_list_groups_by_reason(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_ids = await _seed_questions(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    await _collect_mistakes(client, headers, question_ids)
    await _set_reason(sessionmaker, question_ids[0], "concept")

    response = await client.get("/v1/mistakes", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["active_count"] == 2
    assert body["mastered_count"] == 0
    assert len(body["entries"]) == 2
    summary = {item["reason"]: item["count"] for item in body["summary"]}
    assert summary.get("concept") == 1
    assert summary.get("unattributed") == 1
    labels = {item["reason"]: item["reason_label"] for item in body["summary"]}
    assert labels["concept"] == "概念不清"
    assert labels["unattributed"] == "未归因"


async def test_filter_by_reason(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_ids = await _seed_questions(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    await _collect_mistakes(client, headers, question_ids)
    await _set_reason(sessionmaker, question_ids[0], "computation")

    filtered = await client.get(
        "/v1/mistakes", params={"error_reason": "computation"}, headers=headers
    )
    assert filtered.status_code == 200
    assert filtered.json()["active_count"] == 2  # 总数不受筛选影响
    assert len(filtered.json()["entries"]) == 1
    assert filtered.json()["entries"][0]["error_reason_label"] == "计算失误"


async def test_pdf_export_contains_question_and_analysis(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_ids = await _seed_questions(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    await _collect_mistakes(client, headers, question_ids)

    response = await client.get("/v1/mistakes/export.pdf", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 2000

    reader = PdfReader(BytesIO(response.content))
    text = "".join(page.extract_text() or "" for page in reader.pages)
    compact = "".join(text.split())
    assert "错题" in compact
    assert "解方程" in compact
    assert "解析" in compact


async def test_pdf_export_empty_still_valid(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    response = await client.get("/v1/mistakes/export.pdf", headers=headers_of(payload))
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


async def test_mistake_isolation_between_users(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    question_ids = await _seed_questions(sessionmaker)
    owner = await register(client)
    intruder = await register(client)
    await _collect_mistakes(client, headers_of(owner), question_ids)

    listing = await client.get("/v1/mistakes", headers=headers_of(intruder))
    assert listing.json()["active_count"] == 0
    assert listing.json()["entries"] == []

    repractice = await client.post(
        "/v1/mistakes/repractice", json={"count": 5}, headers=headers_of(intruder)
    )
    assert repractice.json()["count"] == 0


async def test_mistake_book_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/v1/mistakes")).status_code == 401
    assert (await client.post("/v1/mistakes/repractice", json={})).status_code == 401
    assert (await client.get("/v1/mistakes/export.pdf")).status_code == 401
