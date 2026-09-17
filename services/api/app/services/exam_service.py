"""模考与无辅助测评（F-20/F-28）：限时考试、即时出分、百分位、逐题诊断、服务端强制禁提示。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.errors import AppError, NotFoundError, PermissionDeniedError
from app.models import (
    Exam,
    ExamAnswer,
    ExamKind,
    ExamStatus,
    LearningProfile,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    User,
)
from app.services import mastery_service
from app.services.diagnosis_service import check_answer

DEFAULT_MOCK_MINUTES = 60
DEFAULT_SOLO_MINUTES = 30
KIND_LABELS = {ExamKind.MOCK: "限时模考", ExamKind.SOLO: "独立能力测评"}


@dataclass(slots=True)
class ExamBundle:
    """考试实例 + 题目。"""

    exam: Exam
    questions: list[Question]


@dataclass(slots=True)
class ExamReport:
    """考试报告。"""

    exam: Exam
    summary: dict[str, Any]
    diagnoses: list[dict[str, Any]]


async def _load_questions(
    session: AsyncSession, *, subject: str, stage: str | None, count: int
) -> list[Question]:
    stmt = select(Question).where(
        Question.subject == subject, Question.status == QuestionStatus.PUBLISHED
    )
    if stage:
        stmt = stmt.where(Question.stage == stage)
    rows = (
        await session.execute(stmt.order_by(Question.difficulty, Question.created_at).limit(count))
    ).scalars()
    return list(rows)


async def create_exam(
    session: AsyncSession,
    *,
    user: User,
    kind: ExamKind,
    subject: str = "math",
    stage: str | None = None,
    count: int = 10,
    time_limit_minutes: int | None = None,
    title: str | None = None,
) -> ExamBundle:
    """创建限时测评（模考或独立测评）。"""
    questions = await _load_questions(session, subject=subject, stage=stage, count=count)
    if not questions:
        raise AppError("题库中暂无可用题目", code="EXAM_NO_QUESTIONS", status_code=409)
    minutes = time_limit_minutes or (
        DEFAULT_SOLO_MINUTES if kind == ExamKind.SOLO else DEFAULT_MOCK_MINUTES
    )
    deadline = utcnow() + timedelta(minutes=minutes)
    exam = Exam(
        user_id=user.id,
        kind=kind,
        title=title or f"{KIND_LABELS.get(kind, '测评')}·{subject}",
        time_limit_minutes=minutes,
        total_score=100.0,
        status=ExamStatus.IN_PROGRESS,
        started_at=utcnow(),
        meta={
            "subject": subject,
            "stage": stage,
            "question_ids": [question.id.hex for question in questions],
            "deadline": deadline.isoformat(),
            "kind_label": KIND_LABELS.get(kind, "测评"),
        },
    )
    session.add(exam)
    await session.flush()
    return ExamBundle(exam=exam, questions=questions)


def _deadline_of(exam: Exam) -> datetime | None:
    value = exam.meta.get("deadline")
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def _finalize(
    session: AsyncSession, *, exam: Exam, answers: dict[uuid.UUID, str], auto_submitted: bool
) -> None:
    """收卷：判分、画像、百分位、逐题诊断。"""
    question_ids = [uuid.UUID(hex=str(item)) for item in exam.meta.get("question_ids", [])]
    diagnoses: list[dict[str, Any]] = []
    correct_count = 0

    existing = {
        row[0]
        for row in (
            await session.execute(
                select(ExamAnswer.question_id).where(ExamAnswer.exam_id == exam.id)
            )
        ).all()
    }

    for question_id in question_ids:
        question = await session.get(Question, question_id)
        if question is None:
            continue
        user_answer = answers.get(question_id)
        is_correct = False if user_answer is None else check_answer(question, user_answer)
        correct_count += 1 if is_correct else 0
        if question_id not in existing and user_answer is not None:
            session.add(
                ExamAnswer(
                    exam_id=exam.id,
                    question_id=question.id,
                    user_answer={"answer": user_answer},
                    is_correct=is_correct,
                    score=1.0 if is_correct else 0.0,
                )
            )
        kp_ids = (
            await session.execute(
                select(QuestionKnowledgePoint.knowledge_point_id).where(
                    QuestionKnowledgePoint.question_id == question.id
                )
            )
        ).scalars()
        for kp_id in kp_ids:
            await mastery_service.record_practice(
                session, user_id=exam.user_id, knowledge_point_id=kp_id, correct=is_correct
            )
        diagnoses.append(
            {
                "question_id": str(question.id),
                "stem": question.stem,
                "is_correct": is_correct,
                "correct_answer": question.answer,
                "analysis": question.analysis,
            }
        )

    total = len(question_ids) or 1
    score = round(correct_count / total * 100, 1)
    exam.score = score
    exam.status = ExamStatus.SUBMITTED
    exam.submitted_at = utcnow()

    percentile_rows = (
        await session.execute(
            select(Exam.score).where(
                Exam.kind == exam.kind,
                Exam.status == ExamStatus.SUBMITTED,
                Exam.id != exam.id,
                Exam.score.is_not(None),
            )
        )
    ).scalars()
    others = [float(value) for value in percentile_rows if value is not None]
    percentile = (
        round(100 * sum(1 for value in others if value <= score) / len(others), 1)
        if others
        else 100.0
    )

    exam.meta = {
        **exam.meta,
        "auto_submitted": auto_submitted,
        "report": {
            "answered": len(answers),
            "correct": correct_count,
            "total": total,
            "score": score,
            "percentile": percentile,
            "kind_label": exam.meta.get("kind_label"),
            "independent": exam.kind == ExamKind.SOLO,
        },
    }

    if exam.kind == ExamKind.SOLO:
        profile = (
            await session.execute(
                select(LearningProfile).where(LearningProfile.user_id == exam.user_id)
            )
        ).scalar_one_or_none()
        if profile is None:
            profile = LearningProfile(user_id=exam.user_id)
            session.add(profile)
            await session.flush()
        profile.independent_score = score

    await session.flush()
    # diagnoses 直接随报告返回（不落库，避免大 JSON 冗余）
    exam.meta = {**exam.meta, "diagnoses": diagnoses}
    await session.flush()


async def submit_exam(
    session: AsyncSession,
    *,
    user: User,
    exam_id: uuid.UUID,
    answers: list[tuple[uuid.UUID, str]],
) -> ExamReport:
    """交卷（幂等）：即时出分 + 百分位 + 逐题诊断。"""
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise NotFoundError("测评不存在", code="EXAM_NOT_FOUND")
    if exam.user_id != user.id:
        raise PermissionDeniedError("无权访问该测评")
    if exam.status != ExamStatus.SUBMITTED:
        mapping = {question_id: answer for question_id, answer in answers}
        await _finalize(session, exam=exam, answers=mapping, auto_submitted=False)
    diagnoses = exam.meta.get("diagnoses") or []
    return ExamReport(
        exam=exam,
        summary=dict(exam.meta.get("report") or {}),
        diagnoses=list(diagnoses),
    )


async def get_exam_report(
    session: AsyncSession, *, user: User, exam_id: uuid.UUID
) -> ExamReport:
    """查询报告；超时未交卷自动收卷（F-20 倒计时结束自动交卷）。"""
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise NotFoundError("测评不存在", code="EXAM_NOT_FOUND")
    if exam.user_id != user.id:
        raise PermissionDeniedError("无权访问该测评")
    if exam.status == ExamStatus.IN_PROGRESS:
        deadline = _deadline_of(exam)
        if deadline is not None and utcnow() >= deadline:
            await _finalize(session, exam=exam, answers={}, auto_submitted=True)
    diagnoses = exam.meta.get("diagnoses") or []
    return ExamReport(
        exam=exam, summary=dict(exam.meta.get("report") or {}), diagnoses=list(diagnoses)
    )


async def has_active_solo(session: AsyncSession, *, user_id: uuid.UUID) -> bool:
    """是否存在进行中的独立测评（用于服务端强制禁提示）。超时则自动收卷解锁。"""
    exam = (
        await session.execute(
            select(Exam)
            .where(
                Exam.user_id == user_id,
                Exam.kind == ExamKind.SOLO,
                Exam.status == ExamStatus.IN_PROGRESS,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if exam is None:
        return False
    deadline = _deadline_of(exam)
    if deadline is not None and utcnow() >= deadline:
        await _finalize(session, exam=exam, answers={}, auto_submitted=True)
        return False
    return True


async def ensure_no_active_solo(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    """无辅助测评期间禁止一切提示/讲解（F-28 红线）。"""
    if await has_active_solo(session, user_id=user_id):
        raise AppError(
            "无辅助限时测评进行中，提示与讲解已禁用",
            code="TUTOR_SOLO_LOCKED",
            status_code=403,
        )


async def exam_count_for_user(session: AsyncSession, *, user_id: uuid.UUID) -> int:
    """用户已完成的测评数量（统计用）。"""
    count = await session.scalar(
        select(func.count())
        .select_from(Exam)
        .where(Exam.user_id == user_id, Exam.status == ExamStatus.SUBMITTED)
    )
    return int(count or 0)
