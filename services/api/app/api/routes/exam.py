"""模考与独立测评路由（F-20/F-28）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import ExamKind, Question, User
from app.schemas.exam import (
    ExamCreateRequest,
    ExamCreateResponse,
    ExamDiagnosisOut,
    ExamQuestionOut,
    ExamReportResponse,
    ExamSubmitRequest,
)
from app.services import diagnosis_service, exam_service

router = APIRouter(tags=["exams"])


async def _question_out(session: AsyncSession, question: Question) -> ExamQuestionOut:
    names = await diagnosis_service.question_knowledge_point_names(session, question.id)
    return ExamQuestionOut(
        id=question.id,
        stem=question.stem,
        qtype=question.qtype.value,
        options=question.options,
        difficulty=question.difficulty,
        knowledge_points=names,
    )


def _report_response(report: exam_service.ExamReport) -> ExamReportResponse:
    exam = report.exam
    return ExamReportResponse(
        exam_id=exam.id,
        kind=exam.kind.value,
        status=exam.status.value,
        auto_submitted=bool(exam.meta.get("auto_submitted")),
        summary=report.summary,
        diagnoses=[
            ExamDiagnosisOut(
                question_id=uuid.UUID(str(item["question_id"])),
                stem=str(item["stem"]),
                is_correct=bool(item["is_correct"]),
                correct_answer=str(item["correct_answer"]),
                analysis=item.get("analysis"),
            )
            for item in report.diagnoses
            if isinstance(item, dict)
        ],
        submitted_at=exam.submitted_at,
    )


@router.post(
    "/v1/exams",
    response_model=ExamCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建限时模考（F-20）",
)
async def create_mock_exam(
    payload: ExamCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExamCreateResponse:
    """创建全真限时模考。"""
    bundle = await exam_service.create_exam(
        session,
        user=user,
        kind=ExamKind.MOCK,
        subject=payload.subject,
        stage=payload.stage,
        count=payload.count,
        time_limit_minutes=payload.time_limit_minutes,
        title=payload.title,
    )
    questions = [await _question_out(session, item) for item in bundle.questions]
    deadline = exam_service._deadline_of(bundle.exam)
    response = ExamCreateResponse(
        exam_id=bundle.exam.id,
        kind=bundle.exam.kind.value,
        title=bundle.exam.title,
        time_limit_minutes=bundle.exam.time_limit_minutes,
        deadline=deadline,
        questions=questions,
    )
    await session.commit()
    return response


@router.post(
    "/v1/assessments/solo",
    response_model=ExamCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建无辅助限时测评（F-28，服务端强制禁提示）",
)
async def create_solo_assessment(
    payload: ExamCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExamCreateResponse:
    """创建独立能力测评；测评期间所有提示/讲解接口返回 403。"""
    bundle = await exam_service.create_exam(
        session,
        user=user,
        kind=ExamKind.SOLO,
        subject=payload.subject,
        stage=payload.stage,
        count=payload.count,
        time_limit_minutes=payload.time_limit_minutes,
        title=payload.title or "独立能力测评",
    )
    questions = [await _question_out(session, item) for item in bundle.questions]
    deadline = exam_service._deadline_of(bundle.exam)
    response = ExamCreateResponse(
        exam_id=bundle.exam.id,
        kind=bundle.exam.kind.value,
        title=bundle.exam.title,
        time_limit_minutes=bundle.exam.time_limit_minutes,
        deadline=deadline,
        questions=questions,
    )
    await session.commit()
    return response


@router.post(
    "/v1/exams/{exam_id}/submit",
    response_model=ExamReportResponse,
    summary="交卷（即时出分 + 百分位 + 逐题诊断）",
)
async def submit_exam(
    exam_id: uuid.UUID,
    payload: ExamSubmitRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExamReportResponse:
    """提交作答（幂等：重复提交返回既有报告）。"""
    report = await exam_service.submit_exam(
        session,
        user=user,
        exam_id=exam_id,
        answers=[(item.question_id, item.answer) for item in payload.answers],
    )
    response = _report_response(report)
    await session.commit()
    return response


@router.get(
    "/v1/exams/{exam_id}",
    response_model=ExamReportResponse,
    summary="测评报告（超时自动交卷）",
)
async def get_exam(
    exam_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExamReportResponse:
    """查询报告；倒计时结束未交卷则自动收卷。"""
    report = await exam_service.get_exam_report(session, user=user, exam_id=exam_id)
    response = _report_response(report)
    await session.commit()
    return response
