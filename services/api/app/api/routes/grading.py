"""批改路由（F-22~F-26）：客观/主观/作文 + 口语评测 + 编程判题 + 背诵校验。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas import (
    CodeJudgeRequest,
    CodeJudgeResponse,
    DimensionScore,
    JudgeCaseOut,
    RecitationCheckRequest,
    RecitationCheckResponse,
    RecitationErrorMark,
    SpeakingError,
    SpeakingGradeRequest,
    SpeakingGradeResponse,
)
from app.schemas.grading import (
    DimensionScoreOut,
    EssayGradingRequest,
    EssayGradingResponse,
    ObjectiveGradingRequest,
    ObjectiveGradingResponse,
    ParagraphCommentOut,
    SubjectiveGradingRequest,
    SubjectiveGradingResponse,
    SubjectiveStepOut,
)
from app.services import grading_service, judge_service, recitation_service, speaking_service

router = APIRouter(prefix="/v1/grading", tags=["grading"])


@router.post(
    "/objective",
    response_model=ObjectiveGradingResponse,
    summary="客观题即时批改（F-22，答案错题直达讲解流）",
)
async def grade_objective(
    payload: ObjectiveGradingRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ObjectiveGradingResponse:
    """选择/填空秒批；答错时返回守护型讲解会话入口。"""
    result = await grading_service.grade_objective(
        session, user=user, question_id=payload.question_id, user_answer=payload.answer
    )
    response = ObjectiveGradingResponse(
        is_correct=result.is_correct,
        correct_answer=result.correct_answer,
        analysis=result.analysis,
        tutor_session_id=result.tutor_session_id,
    )
    await session.commit()
    return response


@router.post(
    "/subjective",
    response_model=SubjectiveGradingResponse,
    summary="主观解答题批改（F-23，逐步给分 + 改写示范 + SymPy 抽检）",
)
async def grade_subjective(
    payload: SubjectiveGradingRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubjectiveGradingResponse:
    """按评分细则逐步给分，数学解答做机器校验。"""
    result = await grading_service.grade_subjective(
        session,
        user=user,
        llm=request.app.state.llm,
        question_id=payload.question_id,
        stem=payload.stem,
        answer=payload.answer,
        criteria=payload.criteria,
        student_answer=payload.student_answer,
        trace_id=getattr(request.state, "trace_id", None),
    )
    response = SubjectiveGradingResponse(
        total_score=result.total_score,
        max_score=result.max_score,
        steps=[
            SubjectiveStepOut(
                step=item.step,
                score=item.score,
                comment=item.comment,
                lost_points=item.lost_points,
            )
            for item in result.steps
        ],
        rewrite=result.rewrite,
        summary=result.summary,
        machine_check=result.machine_check,
    )
    await session.commit()
    return response


def _dimension_out(item: object) -> DimensionScoreOut:
    """维度分 → 响应模型。"""
    return DimensionScoreOut(
        score=item.score,  # type: ignore[attr-defined]
        max_score=item.max_score,  # type: ignore[attr-defined]
        comment=item.comment,  # type: ignore[attr-defined]
    )


@router.post(
    "/essay",
    response_model=EssayGradingResponse,
    summary="作文批改（F-24，中高考/四六级/考研口径）",
)
async def grade_essay(
    payload: EssayGradingRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EssayGradingResponse:
    """结构/立意/语言三维评分 + 逐段评语 + 升格范文。"""
    result = await grading_service.grade_essay(
        session,
        user=user,
        llm=request.app.state.llm,
        rubric=payload.rubric,
        content=payload.content,
        prompt_text=payload.prompt,
        trace_id=getattr(request.state, "trace_id", None),
    )
    response = EssayGradingResponse(
        total_score=result.total_score,
        max_score=result.max_score,
        rubric=result.rubric,
        structure=_dimension_out(result.structure),
        ideas=_dimension_out(result.ideas),
        language=_dimension_out(result.language),
        paragraphs=[
            ParagraphCommentOut(index=item.index, comment=item.comment, suggestion=item.suggestion)
            for item in result.paragraphs
        ],
        upgrade_sample=result.upgrade_sample,
        summary=result.summary,
    )
    await session.commit()
    return response


# ------------------------------- F-25 口语评测 -------------------------------


@router.post(
    "/speaking",
    response_model=SpeakingGradeResponse,
    summary="英语口语评测（F-25，发音/流利度/完整度 + 音素级纠错）",
)
async def grade_speaking(
    payload: SpeakingGradeRequest,
    user: User = Depends(get_current_user),
) -> SpeakingGradeResponse:
    """口语评测（mock 供应商先行；返回三维分数与纠错词列表）。"""
    result = speaking_service.grade_speaking(
        reference=payload.reference,
        transcript=payload.transcript,
        duration_seconds=payload.duration_seconds,
    )
    return SpeakingGradeResponse(
        provider=result.provider,
        pronunciation=DimensionScore(score=result.pronunciation, comment="发音准确度"),
        fluency=DimensionScore(score=result.fluency, comment=result.notes.get("fluency", "")),
        completeness=DimensionScore(score=result.completeness, comment="内容完整度"),
        errors=[
            SpeakingError(
                word=error.word, expected=error.expected, pronunciation=error.pronunciation
            )
            for error in result.errors
        ],
    )


# ------------------------------- F-26 编程判题 -------------------------------


@router.post(
    "/code",
    response_model=CodeJudgeResponse,
    summary="编程题判题（F-26：沙箱执行 + 评审式反馈）",
)
async def judge_code(
    payload: CodeJudgeRequest,
    user: User = Depends(get_current_user),
) -> CodeJudgeResponse:
    """受限子进程执行代码：资源/超时限制，恶意代码一律拦截。"""
    outcome = judge_service.run_python(
        payload.code,
        tests=[
            judge_service.TestCase(input=case.input, expected=case.expected)
            for case in payload.tests
        ],
        timeout_seconds=payload.timeout_seconds,
    )
    return CodeJudgeResponse(
        verdict=outcome.verdict,
        passed=outcome.passed,
        total=outcome.total,
        results=[
            JudgeCaseOut(
                index=item.index,
                passed=item.passed,
                status=item.status,
                stdout=item.stdout,
                expected=item.expected,
                stderr=item.stderr,
                runtime_ms=item.runtime_ms,
            )
            for item in outcome.results
        ],
        feedback=outcome.feedback,
        blocked_reason=outcome.blocked_reason,
    )


# ------------------------------- F-21 背诵助手 -------------------------------


@router.post(
    "/recitation/check",
    response_model=RecitationCheckResponse,
    summary="背诵校验（F-21：错字标记 + 易错点抽考）",
)
async def check_recitation(
    payload: RecitationCheckRequest,
    user: User = Depends(get_current_user),
) -> RecitationCheckResponse:
    """ASR 转写与原文比对，返回错字标记与抽考点。"""
    result = recitation_service.check_recitation(payload.reference, payload.transcript)
    return RecitationCheckResponse(
        accuracy=result.accuracy,
        total_chars=result.total_chars,
        error_count=len(result.errors),
        errors=[
            RecitationErrorMark(
                position=error.position,
                expected=error.expected,
                got=error.got,
                kind=error.kind,
            )
            for error in result.errors
        ],
        masked_preview=result.masked_preview,
        quiz_points=result.quiz_points,
    )
