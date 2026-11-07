"""复习卡 Anki 导出测试（吸收 DeepTutor：闪卡导出到 Anki）。"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
    ReviewCard,
)
from app.services import fsrs_service
from tests.helpers import headers_of, register


async def _current_user_id(
    sessionmaker: async_sessionmaker[AsyncSession], phone: str
) -> uuid.UUID:
    from app.services import auth_service

    async with sessionmaker() as session:
        user = await auth_service.get_user_by_phone(session, phone)
        assert user is not None
        return user.id


async def _seed_card_question(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    user_id: uuid.UUID,
    qtype: QuestionType,
    stem: str,
    answer: str,
    options: dict[str, str] | None = None,
    kp_name: str = "测试知识点",
) -> uuid.UUID:
    """播种一张复习卡对应的题目，返回 question_id。"""
    async with sessionmaker() as session:
        kp = KnowledgePoint(
            code=f"math.test.anki.{uuid.uuid4().hex[:8]}",
            name=kp_name,
            subject="math",
            stage="junior",
        )
        session.add(kp)
        await session.flush()
        question = Question(
            subject="math",
            stage="junior",
            qtype=qtype,
            stem=stem,
            answer=answer,
            options=options,
            analysis="两边同除以 2。",
            status=QuestionStatus.PUBLISHED,
        )
        session.add(question)
        await session.flush()
        session.add(
            QuestionKnowledgePoint(question_id=question.id, knowledge_point_id=kp.id)
        )
        session.add(
            ReviewCard(
                user_id=user_id,
                question_id=question.id,
                state=fsrs_service.STATE_REVIEW,
                stability=1.0,
                difficulty=5.0,
                due_at=None,
            )
        )
        await session.commit()
        return question.id


async def _suspend_card(
    sessionmaker: async_sessionmaker[AsyncSession], question_id: uuid.UUID
) -> None:
    async with sessionmaker() as session:
        card = (
            await session.execute(
                select(ReviewCard).where(ReviewCard.question_id == question_id)
            )
        ).scalar_one()
        card.suspended = True
        await session.commit()


async def test_export_contains_cards_and_mathjax(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    user_id = await _current_user_id(sessionmaker, payload["phone"])
    await _seed_card_question(
        sessionmaker,
        user_id=user_id,
        qtype=QuestionType.CHOICE,
        stem="解方程 $2x = 8$，x = ？",
        answer="4",
        options={"A": "2", "B": "4", "C": "6", "D": "8"},
        kp_name="一元一次方程",
    )
    await _seed_card_question(
        sessionmaker,
        user_id=user_id,
        qtype=QuestionType.FILL,
        stem="12 + 7 = ？",
        answer="19",
    )

    response = await client.get("/v1/review/export.anki", headers=headers_of(payload))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/plain")
    assert "attachment" in response.headers["content-disposition"]
    body = response.text
    assert body.startswith("#separator:tab\n#html:true\n#deck:学伴::复习\n#tags column:3\n")
    # LaTeX 定界符转成 Anki 的 MathJax 定界符
    assert r"\(2x = 8\)" in body
    # 选项进题面、答案/解析进背面、标签含题型与知识点
    assert "A. 2" in body
    assert "答案：4" in body
    assert "解析：两边同除以 2。" in body
    assert "单选" in body and "一元一次方程" in body
    # 两行数据，每行三列
    data_lines = [line for line in body.splitlines() if not line.startswith("#")]
    assert len(data_lines) == 2
    assert all(line.count("\t") == 2 for line in data_lines)


async def test_export_excludes_suspended_and_subjective(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    user_id = await _current_user_id(sessionmaker, payload["phone"])
    kept = await _seed_card_question(
        sessionmaker, user_id=user_id, qtype=QuestionType.FILL, stem="1 + 1 = ？", answer="2"
    )
    await _suspend_card(sessionmaker, kept)

    # 解答题即使误建了卡也不导出：它没有确定性的「答案面」
    await _seed_card_question(
        sessionmaker,
        user_id=user_id,
        qtype=QuestionType.SHORT_ANSWER,
        stem="证明 1+1=2。",
        answer="略。",
    )

    response = await client.get("/v1/review/export.anki", headers=headers_of(payload))
    assert response.status_code == 200
    data_lines = [line for line in response.text.splitlines() if not line.startswith("#")]
    assert data_lines == [], "暂停卡与解答题都不应导出"


async def test_export_isolated_between_users(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    owner = await register(client)
    intruder = await register(client)
    owner_id = await _current_user_id(sessionmaker, owner["phone"])
    await _seed_card_question(
        sessionmaker, user_id=owner_id, qtype=QuestionType.FILL, stem="3 × 3 = ？", answer="9"
    )

    response = await client.get("/v1/review/export.anki", headers=headers_of(intruder))
    assert response.status_code == 200
    data_lines = [line for line in response.text.splitlines() if not line.startswith("#")]
    assert data_lines == []
