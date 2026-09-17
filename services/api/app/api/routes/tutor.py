"""守护型讲解路由（F-11：分层提示 + SSE 流式）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import Question, User
from app.schemas.tutor import (
    TutorHintRequest,
    TutorHintResponse,
    TutorQuestionOut,
    TutorSessionResponse,
    TutorSessionStartRequest,
)
from app.schemas.tutor_ext import (
    AltSolutionOut,
    AltSolutionsResponse,
    AnalogyResponse,
    BackToTutorOut,
    VariantAnswerRequest,
    VariantAnswerResponse,
    VariantOut,
    VariantsResponse,
)
from app.services import diagnosis_service, tutor_ext_service, tutor_service

router = APIRouter(prefix="/v1/tutor", tags=["tutor"])


async def _question_out(session: AsyncSession, question: Question) -> TutorQuestionOut:
    names = await diagnosis_service.question_knowledge_point_names(session, question.id)
    return TutorQuestionOut(
        id=question.id,
        stem=question.stem,
        qtype=question.qtype.value,
        options=question.options,
        difficulty=question.difficulty,
        knowledge_points=names,
    )


@router.post(
    "/session",
    response_model=TutorSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="开启守护型讲解会话（F-11）",
)
async def create_session(
    payload: TutorSessionStartRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TutorSessionResponse:
    """创建讲解会话（初始层级 0，不直接给答案）。"""
    chat, question = await tutor_service.start_session(
        session, user=user, question_id=payload.question_id
    )
    response = TutorSessionResponse(
        session_id=chat.id,
        question=await _question_out(session, question),
        hint_level=chat.hint_level,
        hint_level_name="未开始",
    )
    await session.commit()
    return response


@router.post(
    "/{session_id}/hint",
    response_model=TutorHintResponse,
    summary="请求下一层提示（不可跳层）",
)
async def request_hint(
    session_id: uuid.UUID,
    payload: TutorHintRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TutorHintResponse:
    """按状态机返回下一层提示（思路 → 关键步骤 → 全解）。"""
    result = await tutor_service.request_hint(
        session,
        user=user,
        session_id=session_id,
        llm=request.app.state.llm,
        requested_level=payload.level,
        trace_id=getattr(request.state, "trace_id", None),
    )
    response = TutorHintResponse(
        session_id=result.session_id,
        level=result.level,
        level_name=result.level_name,
        content=result.content,
        next_level=result.next_level,
    )
    await session.commit()
    return response


@router.post(
    "/{session_id}/hint/stream",
    summary="请求下一层提示（SSE 流式）",
    response_class=StreamingResponse,
)
async def stream_hint(
    session_id: uuid.UUID,
    payload: TutorHintRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """SSE 流式输出：start → delta* → done（校验在流开始前完成）。"""
    prepared = await tutor_service.prepare_hint(
        session, user=user, session_id=session_id, requested_level=payload.level
    )
    sessionmaker = request.app.state.sessionmaker
    llm = request.app.state.llm
    generator = tutor_service.stream_hint(
        sessionmaker,
        prepared=prepared,
        llm=llm,
        trace_id=getattr(request.state, "trace_id", None),
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/{session_id}/alt-solutions",
    response_model=AltSolutionsResponse,
    summary="多解法对比讲解（F-12）",
)
async def alt_solutions(
    session_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AltSolutionsResponse:
    """生成 2~3 种解法并做 SymPy 等价性抽检。"""
    result = await tutor_ext_service.generate_alt_solutions(
        session,
        user=user,
        session_id=session_id,
        llm=request.app.state.llm,
        trace_id=getattr(request.state, "trace_id", None),
    )
    response = AltSolutionsResponse(
        session_id=session_id,
        solutions=[
            AltSolutionOut(
                title=item.title,
                steps=item.steps,
                scenario=item.scenario,
                answer_verified=item.answer_verified,
            )
            for item in result.solutions
        ],
        checked_count=result.checked_count,
        verified_count=result.verified_count,
    )
    await session.commit()
    return response


@router.post(
    "/{session_id}/analogy",
    response_model=AnalogyResponse,
    summary="生活化类比生成（F-13）",
)
async def analogy(
    session_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnalogyResponse:
    """生成贴近学生生活的类比与对应关系说明。"""
    result = await tutor_ext_service.generate_analogy(
        session,
        user=user,
        session_id=session_id,
        llm=request.app.state.llm,
        trace_id=getattr(request.state, "trace_id", None),
    )
    response = AnalogyResponse(
        session_id=session_id,
        analogy=result.analogy,
        mapping=result.mapping,
        caveat=result.caveat,
    )
    await session.commit()
    return response


@router.post(
    "/{session_id}/variants",
    response_model=VariantsResponse,
    summary="举一反三变式题（F-14）",
)
async def variants(
    session_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> VariantsResponse:
    """生成 1~2 道同知识点变式题（入库，可作答）。"""
    result = await tutor_ext_service.generate_variants(
        session,
        user=user,
        session_id=session_id,
        llm=request.app.state.llm,
        trace_id=getattr(request.state, "trace_id", None),
    )
    response = VariantsResponse(
        session_id=session_id,
        variants=[
            VariantOut(
                question_id=item.question_id,
                stem=item.stem,
                options=item.options,
                difficulty=item.difficulty,
            )
            for item in result.variants
        ],
    )
    await session.commit()
    return response


@router.post(
    "/{session_id}/variants/{variant_id}/answer",
    response_model=VariantAnswerResponse,
    summary="变式题作答（答错自动回炉，F-14）",
)
async def answer_variant(
    session_id: uuid.UUID,
    variant_id: uuid.UUID,
    payload: VariantAnswerRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> VariantAnswerResponse:
    """答对计入掌握度；答错进入错题本并开启回炉讲解会话。"""
    result = await tutor_ext_service.answer_variant(
        session,
        user=user,
        session_id=session_id,
        variant_id=variant_id,
        user_answer=payload.answer,
    )
    response = VariantAnswerResponse(
        is_correct=result.is_correct,
        correct_answer=result.correct_answer,
        back_to_tutor=(
            BackToTutorOut(
                session_id=result.back_to_tutor.session_id,
                message=result.back_to_tutor.message,
            )
            if result.back_to_tutor is not None
            else None
        ),
    )
    await session.commit()
    return response
