"""复习卡路由（F-19：到期查询与 FSRS 评分）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import Question, User
from app.schemas.practice import (
    QuestionBriefOut,
    ReviewCardOut,
    ReviewDueResponse,
    ReviewGradeRequest,
    ReviewGradeResponse,
)
from app.services import diagnosis_service, fsrs_service

router = APIRouter(prefix="/v1/review", tags=["review"])


@router.get("/due", response_model=ReviewDueResponse, summary="到期复习卡片（F-19）")
async def due(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReviewDueResponse:
    """返回已到期（含逾期）的复习卡片。"""
    cards = await fsrs_service.due_cards(session, user_id=user.id, limit=limit)
    total = await fsrs_service.due_count(session, user_id=user.id)
    payload: list[ReviewCardOut] = []
    for card in cards:
        question = await session.get(Question, card.question_id)
        if question is None:
            continue
        names = await diagnosis_service.question_knowledge_point_names(session, question.id)
        payload.append(
            ReviewCardOut(
                card_id=card.id,
                question=QuestionBriefOut(
                    id=question.id,
                    stem=question.stem,
                    qtype=question.qtype.value,
                    options=question.options,
                    difficulty=question.difficulty,
                    knowledge_points=names,
                ),
                state=card.state,
                reps=card.reps,
                lapses=card.lapses,
                difficulty=card.difficulty,
                due_at=card.due_at,
            )
        )
    return ReviewDueResponse(due_count=total, cards=payload)


@router.post(
    "/{card_id}/grade",
    response_model=ReviewGradeResponse,
    summary="FSRS 评分（1–4）",
)
async def grade(
    card_id: uuid.UUID,
    payload: ReviewGradeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReviewGradeResponse:
    """应用一次 FSRS 评分并返回下次间隔。"""
    card = await fsrs_service.grade_card(session, user=user, card_id=card_id, grade=payload.grade)
    assert card.due_at is not None
    response = ReviewGradeResponse(
        card_id=card.id,
        state=card.state,
        interval_days=card.stability,
        due_at=card.due_at,
        reps=card.reps,
        lapses=card.lapses,
        difficulty=card.difficulty,
    )
    await session.commit()
    return response
