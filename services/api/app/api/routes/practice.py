"""练习路由（F-17/F-10）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import PracticeSource, User
from app.schemas.practice import (
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeGenerateRequest,
    PracticeGenerateResponse,
    PracticeQuestionOut,
)
from app.services import diagnosis_service, practice_service

router = APIRouter(prefix="/v1/practice", tags=["practice"])


@router.post(
    "/generate",
    response_model=PracticeGenerateResponse,
    summary="智能出题（F-17）",
)
async def generate(
    payload: PracticeGenerateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PracticeGenerateResponse:
    """薄弱知识点占比 ≥60%，近 7 天去重。"""
    practice_set = await practice_service.generate_practice(
        session,
        user=user,
        subject=payload.subject,
        stage=payload.stage,
        count=payload.count,
        knowledge_point_ids=payload.knowledge_point_ids,
    )
    questions: list[PracticeQuestionOut] = []
    for item in practice_set.items:
        names = await diagnosis_service.question_knowledge_point_names(
            session, item.question.id
        )
        questions.append(
            PracticeQuestionOut(
                id=item.question.id,
                stem=item.question.stem,
                qtype=item.question.qtype.value,
                options=item.question.options,
                difficulty=item.question.difficulty,
                knowledge_points=names,
                reason=item.reason,
            )
        )
    response = PracticeGenerateResponse(
        count=len(questions),
        weak_count=practice_set.weak_count,
        weak_ratio=practice_set.weak_ratio,
        questions=questions,
    )
    await session.commit()
    return response


@router.post(
    "/answer",
    response_model=PracticeAnswerResponse,
    summary="练习作答（错题自动归集 + FSRS 联动 + 动态难度）",
)
async def answer(
    payload: PracticeAnswerRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PracticeAnswerResponse:
    """判定作答并联动画像、错题本与复习卡。"""
    result = await practice_service.answer_question(
        session,
        user=user,
        question_id=payload.question_id,
        user_answer=payload.answer,
        source=PracticeSource(payload.source),
        client_event_id=payload.client_event_id,
    )
    response = PracticeAnswerResponse(
        is_correct=result.is_correct,
        correct_answer=result.correct_answer,
        next_difficulty=result.next_difficulty,
        mistake_collected=result.mistake_collected,
        mistake_removed=result.mistake_removed,
        card_due_at=result.card_due_at,
        explanation=result.explanation,
        duplicate=result.duplicate,
    )
    await session.commit()
    return response
