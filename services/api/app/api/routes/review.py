"""复习卡路由（F-19：到期查询与 FSRS 评分；Anki 导出）。"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_not_locked
from app.models import (
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    ReviewCard,
    User,
)
from app.schemas.practice import (
    QuestionBriefOut,
    ReviewCardOut,
    ReviewDueResponse,
    ReviewGradeRequest,
    ReviewGradeResponse,
)
from app.services import anki_export, diagnosis_service, fsrs_service, mistake_scope
from app.services.anki_export import AnkiCard, build_anki_txt, card_back, card_front
from app.services.diagnosis_service import OBJECTIVE_QTYPES

router = APIRouter(prefix="/v1/review", tags=["review"])


@router.get(
    "/export.anki",
    summary="复习卡导出 Anki 文本（吸收 DeepTutor：闪卡导出到 Anki）",
)
async def export_anki(
    user: User = Depends(require_not_locked),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """把当前用户全部未暂停的客观题复习卡导出为 Anki 文本导入格式。

    复习调度仍以学伴 FSRS 为准；导出只是把题面/答案交给 Anki 自己的调度。
    """
    rows = (
        await session.execute(
            select(ReviewCard, Question)
            .join(Question, Question.id == ReviewCard.question_id)
            .where(
                ReviewCard.user_id == sa.bindparam("export_user"),
                ReviewCard.suspended.is_(False),
                Question.status == QuestionStatus.PUBLISHED,
                Question.qtype.in_(OBJECTIVE_QTYPES),
            )
            .order_by(ReviewCard.due_at),
            {"export_user": user.id},
        )
    ).all()
    question_ids = [question.id for _, question in rows]
    kp_names: dict[uuid.UUID, list[str]] = {}
    if question_ids:
        link_rows = (
            await session.execute(
                select(QuestionKnowledgePoint.question_id, KnowledgePoint.name)
                .join(
                    KnowledgePoint,
                    KnowledgePoint.id == QuestionKnowledgePoint.knowledge_point_id,
                )
                .where(QuestionKnowledgePoint.question_id.in_(question_ids))
            )
        ).all()
        for question_id, name in link_rows:
            kp_names.setdefault(question_id, []).append(name)

    cards = [
        AnkiCard(
            front=card_front(question.stem, question.options),
            back=card_back(question.answer, question.analysis),
            tags=[
                anki_export.QTYPE_LABELS.get(question.qtype.value, question.qtype.value),
                *kp_names.get(question.id, []),
            ],
        )
        for _, question in rows
    ]
    content = build_anki_txt(cards)
    await session.commit()
    return Response(
        content=content,
        media_type=anki_export.ANKI_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{anki_export.ANKI_FILENAME}"'
        },
    )


@router.get("/due", response_model=ReviewDueResponse, summary="到期复习卡片（F-19）")
async def due(
    limit: int = Query(default=20, ge=1, le=100),
    subject: str | None = Query(default=None, max_length=32),
    stage: str | None = Query(default=None, max_length=20),
    user: User = Depends(require_not_locked),
    session: AsyncSession = Depends(get_session),
) -> ReviewDueResponse:
    """返回已到期（含逾期）的复习卡片；subject/stage 收窄到当前选科与学段。"""
    cards = await mistake_scope.due_cards_scoped(
        session, user_id=user.id, limit=limit, subject=subject, stage=stage
    )
    total = await mistake_scope.due_count_scoped(
        session, user_id=user.id, subject=subject, stage=stage
    )
    payload: list[ReviewCardOut] = []
    for card in cards:
        question = await session.get(Question, card.question_id)
        if question is None:
            continue
        links = await diagnosis_service.question_knowledge_point_links(session, question.id)
        payload.append(
            ReviewCardOut(
                card_id=card.id,
                question=QuestionBriefOut(
                    id=question.id,
                    stem=question.stem,
                    qtype=question.qtype.value,
                    options=question.options,
                    difficulty=question.difficulty,
                    knowledge_points=[name for _, name in links],
                    knowledge_point_ids=[point_id.hex for point_id, _ in links],
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
    user: User = Depends(require_not_locked),
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
