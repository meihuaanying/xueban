"""错题路由（F-02 归因 / F-18 错题本列表、重练、PDF 导出）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas.diagnosis import AttributionResponse
from app.schemas.practice import (
    MistakeEntryOut,
    MistakeListResponse,
    MistakeRepracticeRequest,
    MistakeRepracticeResponse,
    MistakeSummaryItem,
    QuestionBriefOut,
)
from app.services import diagnosis_service, mistake_book_service
from app.services.attribution_service import attribute_mistake

router = APIRouter(prefix="/v1/mistakes", tags=["mistakes"])


@router.get("", response_model=MistakeListResponse, summary="错题本列表（按错因分组，F-18）")
async def list_mistakes(
    state: str | None = Query(default=None, max_length=20),
    error_reason: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MistakeListResponse:
    """返回未移出的错题与错因分组统计。"""
    views, summary = await mistake_book_service.list_mistakes(
        session, user=user, state=state, error_reason=error_reason, limit=limit
    )
    counts = await mistake_book_service.mistake_summary(session, user=user)
    entries: list[MistakeEntryOut] = []
    for view in views:
        names = await diagnosis_service.question_knowledge_point_names(session, view.question.id)
        entries.append(
            MistakeEntryOut(
                id=view.entry.id,
                question=QuestionBriefOut(
                    id=view.question.id,
                    stem=view.question.stem,
                    qtype=view.question.qtype.value,
                    options=view.question.options,
                    difficulty=view.question.difficulty,
                    knowledge_points=names,
                ),
                wrong_answer=view.entry.wrong_answer,
                error_reason=view.entry.error_reason,
                error_reason_label=mistake_book_service.reason_label(view.entry.error_reason),
                state=view.entry.state.value,
                review_count=view.entry.review_count,
                created_at=view.entry.created_at,
            )
        )
    response = MistakeListResponse(
        active_count=counts["active"],
        mastered_count=counts["mastered"],
        summary=[
            MistakeSummaryItem(
                reason=reason,
                reason_label=mistake_book_service.reason_label(reason) or "未归因",
                count=count,
            )
            for reason, count in summary
        ],
        entries=entries,
    )
    await session.commit()
    return response


@router.post(
    "/repractice",
    response_model=MistakeRepracticeResponse,
    summary="一键重练（F-18）",
)
async def repractice(
    payload: MistakeRepracticeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MistakeRepracticeResponse:
    """拉取错题用于重练；作答 source=repractice 且答对后自动移出。"""
    questions = await mistake_book_service.repractice_questions(
        session, user=user, count=payload.count, error_reason=payload.error_reason
    )
    payload_out: list[QuestionBriefOut] = []
    for question in questions:
        names = await diagnosis_service.question_knowledge_point_names(session, question.id)
        payload_out.append(
            QuestionBriefOut(
                id=question.id,
                stem=question.stem,
                qtype=question.qtype.value,
                options=question.options,
                difficulty=question.difficulty,
                knowledge_points=names,
            )
        )
    response = MistakeRepracticeResponse(count=len(payload_out), questions=payload_out)
    await session.commit()
    return response


@router.get("/export.pdf", summary="导出错题本 PDF（含题目与解析，F-18）")
async def export_pdf(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """生成并返回错题本 PDF。"""
    content = await mistake_book_service.build_export_pdf(session, user=user)
    await session.commit()
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="xueban-mistakes.pdf"'},
    )


@router.post(
    "/{entry_id}/attribute",
    response_model=AttributionResponse,
    summary="错因自动归因（F-02）",
)
async def attribute(
    entry_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AttributionResponse:
    """调用 LLM 归因（限定五类枚举）并写回错题本。"""
    result = await attribute_mistake(
        session,
        user=user,
        entry_id=entry_id,
        llm=request.app.state.llm,
        trace_id=getattr(request.state, "trace_id", None),
    )
    response = AttributionResponse(
        entry_id=result.entry_id,
        reason=result.reason,
        reason_label=result.reason_label,
        confidence=result.confidence,
        explanation=result.explanation,
    )
    await session.commit()
    return response
