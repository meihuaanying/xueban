"""诊断路由（F-01）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.config import settings
from app.models import Question, User
from app.schemas import HandwritingDiagnosisRequest, HandwritingDiagnosisResponse, HandwritingStep
from app.schemas.diagnosis import (
    DiagnosisAnswerRequest,
    DiagnosisAnswerResponse,
    DiagnosisProgress,
    DiagnosisQuestionOut,
    DiagnosisReportResponse,
    DiagnosisStartRequest,
    DiagnosisStartResponse,
)
from app.schemas.profile import MasteryPointResponse
from app.services import diagnosis_service, ocr_client

router = APIRouter(prefix="/v1/diagnosis", tags=["diagnosis"])


async def _question_out(session: AsyncSession, question: Question) -> DiagnosisQuestionOut:
    """组装题目 DTO（含知识点名称，不含答案）。"""
    names = await diagnosis_service.question_knowledge_point_names(session, question.id)
    return DiagnosisQuestionOut(
        id=question.id,
        stem=question.stem,
        qtype=question.qtype.value,
        options=question.options,
        difficulty=question.difficulty,
        knowledge_points=names,
    )


@router.post(
    "/start",
    response_model=DiagnosisStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="开启入学水平诊断（F-01）",
)
async def start(
    payload: DiagnosisStartRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DiagnosisStartResponse:
    """创建诊断并按初始难度给出第一题。"""
    exam, question = await diagnosis_service.start_diagnosis(
        session,
        user=user,
        subject=payload.subject,
        stage=payload.stage,
        target_count=payload.target_count,
    )
    response = DiagnosisStartResponse(
        exam_id=exam.id,
        status=exam.status.value,
        progress=DiagnosisProgress(answered=0, total=payload.target_count),
        question=await _question_out(session, question),
    )
    await session.commit()
    return response


@router.post(
    "/{exam_id}/answer",
    response_model=DiagnosisAnswerResponse,
    summary="提交诊断作答（自适应选题）",
)
async def answer(
    exam_id: uuid.UUID,
    payload: DiagnosisAnswerRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DiagnosisAnswerResponse:
    """判定作答、更新画像与难度，并返回下一题或收卷。"""
    result = await diagnosis_service.submit_answer(
        session,
        user=user,
        exam_id=exam_id,
        question_id=payload.question_id,
        user_answer=payload.answer,
    )
    next_question = (
        await _question_out(session, result.next_question)
        if result.next_question is not None
        else None
    )
    response = DiagnosisAnswerResponse(
        exam_id=exam_id,
        is_correct=result.is_correct,
        correct_answer=result.correct_answer,
        progress=DiagnosisProgress(answered=result.answered, total=result.total),
        finished=result.finished,
        next_question=next_question,
    )
    await session.commit()
    return response


@router.get(
    "/{exam_id}/report",
    response_model=DiagnosisReportResponse,
    summary="诊断报告（含知识点掌握度）",
)
async def report(
    exam_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DiagnosisReportResponse:
    """返回诊断报告（未结束时 409）。"""
    result = await diagnosis_service.get_report(session, user=user, exam_id=exam_id)
    response = DiagnosisReportResponse(
        exam_id=exam_id,
        finished=True,
        summary=result.summary,
        points=[MasteryPointResponse.model_validate(point) for point in result.points],
        has_data=bool(result.points),
    )
    await session.commit()
    return response


@router.post(
    "/handwriting",
    response_model=HandwritingDiagnosisResponse,
    summary="手写步骤拍照诊断（F-04：定位第几步出错）",
)
async def handwriting_diagnosis(
    payload: HandwritingDiagnosisRequest,
    user: User = Depends(get_current_user),
) -> HandwritingDiagnosisResponse:
    """OCR 识别手写步骤并与参考解答逐步比对，定位首次出错步骤。"""
    result = await ocr_client.diagnose_handwriting(
        settings=settings,
        image_key=payload.image_key,
        ocr_text=payload.ocr_text,
        reference_solution=payload.reference_solution,
    )
    return HandwritingDiagnosisResponse(
        steps=[
            HandwritingStep(
                index=step.index, content=step.content, is_error=step.is_error, note=step.note
            )
            for step in result.steps
        ],
        first_error_step=result.first_error_step,
        confidence=result.confidence,
        degraded=result.degraded,
        degradation_hint=result.degradation_hint,
        advice=result.advice,
    )
