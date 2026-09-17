"""复盘测试（T3.9 / F-27/F-29/F-30）：周报幂等与分享、日历、冲刺包。"""

from __future__ import annotations

from datetime import date

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
    WeeklyReport,
)
from app.services.report_service import week_start_of
from tests.helpers import headers_of, register


def test_week_start_of() -> None:
    assert week_start_of(date(2026, 9, 16)) == date(2026, 9, 14)  # 周三 → 周一
    assert week_start_of(date(2026, 9, 14)) == date(2026, 9, 14)  # 周一 → 自身
    assert week_start_of(date(2026, 9, 20)) == date(2026, 9, 14)  # 周日 → 上周一


async def _seed_bank(
    sessionmaker: async_sessionmaker[AsyncSession], *, count: int = 4
) -> list[tuple[object, str]]:
    items: list[tuple[object, str]] = []
    async with sessionmaker() as session:
        kp = KnowledgePoint(code="math.test.report", name="方程", subject="math")
        session.add(kp)
        await session.flush()
        for index in range(count):
            question = Question(
                subject="math",
                stage="junior",
                qtype=QuestionType.FILL,
                stem=f"[方程] 第{index}题：{index} + 1 = ?",
                answer=str(index + 1),
                analysis="基础运算。",
                status=QuestionStatus.PUBLISHED,
            )
            session.add(question)
            await session.flush()
            session.add(QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id))
            items.append((question.id, question.answer))
        await session.commit()
    return items


async def test_weekly_report_content_and_idempotency(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)

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

    first = await client.get("/v1/reports/weekly", headers=headers)
    assert first.status_code == 200, first.text
    body = first.json()
    report = body["report"]
    assert report["practice"]["total"] == 2
    assert report["practice"]["accuracy"] == 50.0
    assert report["mistakes_new"] == 1
    assert report["suggestions"]
    assert body["week_start"] <= body["week_end"]

    second = await client.get("/v1/reports/weekly", headers=headers)
    assert second.json()["week_start"] == body["week_start"]
    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(WeeklyReport))
    assert count == 1


async def test_share_link_and_revoke(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)

    share = await client.post("/v1/reports/weekly/share", headers=headers)
    assert share.status_code == 200, share.text
    token = share.json()["token"]

    # 免登录读取
    shared = await client.get(f"/v1/reports/shared/{token}")
    assert shared.status_code == 200
    assert shared.json()["report"]["week_start"]

    revoked = await client.delete(f"/v1/reports/shares/{token}", headers=headers)
    assert revoked.status_code == 204
    after = await client.get(f"/v1/reports/shared/{token}")
    assert after.status_code == 404

    # 他人的分享不可吊销
    other = await register(client)
    share2 = await client.post("/v1/reports/weekly/share", headers=headers)
    token2 = share2.json()["token"]
    denied = await client.delete(f"/v1/reports/shares/{token2}", headers=headers_of(other))
    assert denied.status_code == 404


async def test_calendar_stats(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)
    await client.post(
        "/v1/practice/answer",
        json={"question_id": str(bank[0][0]), "answer": bank[0][1]},
        headers=headers,
    )
    today = await client.get("/v1/plan/today", headers=headers)
    for task in today.json()["tasks"]:
        await client.post(f"/v1/plan/tasks/{task['id']}/complete", headers=headers)

    from app.db import utcnow

    now = utcnow().date()
    response = await client.get(
        "/v1/stats/calendar",
        params={"year": now.year, "month": now.month},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["days"]) >= 28
    today_row = next(item for item in body["days"] if item["day"] == now.isoformat())
    assert today_row["practice_count"] == 1
    assert today_row["studied"] is True
    assert body["streak_days"] >= 1
    assert body["max_practice"] >= 1


async def test_calendar_invalid_month(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.get(
        "/v1/stats/calendar", params={"year": 2026, "month": 13}, headers=headers_of(payload)
    )
    assert response.status_code == 422


async def test_sprint_requires_plan(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.get("/v1/exam-prep/sprint", headers=headers_of(payload))
    assert response.status_code == 400
    assert response.json()["code"] == "EXAM_PREP_NO_PLAN"


async def test_sprint_package_content(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    bank = await _seed_bank(sessionmaker)
    payload = await register(client)
    headers = headers_of(payload)

    from datetime import timedelta

    from app.db import utcnow

    exam_date = (utcnow().date() + timedelta(days=30)).isoformat()
    plan = await client.post(
        "/v1/plan/exam-countdown",
        json={"exam_date": exam_date, "target_score": 90},
        headers=headers,
    )
    assert plan.status_code == 201

    # 制造高频错题 + 未掌握知识点
    for _ in range(2):
        await client.post(
            "/v1/practice/answer",
            json={"question_id": str(bank[0][0]), "answer": "错误"},
            headers=headers,
        )

    response = await client.get("/v1/exam-prep/sprint", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["remaining_days"] <= 30
    assert len(body["high_freq_mistakes"]) >= 1
    assert len(body["unmastered_knowledge_points"]) >= 1
    assert len(body["predicted_paper"]) >= 1


async def test_reports_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/v1/reports/weekly")).status_code == 401
    assert (await client.post("/v1/reports/weekly/share")).status_code == 401
    calendar = await client.get(
        "/v1/stats/calendar", params={"year": 2026, "month": 1}
    )
    assert calendar.status_code == 401
    assert (await client.get("/v1/exam-prep/sprint")).status_code == 401
