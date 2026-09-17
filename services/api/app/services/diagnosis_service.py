"""自适应诊断引擎（F-01/F-02 的 F-01 部分）：CAT 选题、难度调节、报告生成。

选题策略（最近发展区）：优先选择掌握度最低的知识点，其次选择与目标难度最接近的题目。
难度调节：答对升 1 档、答错降 1 档（1~5 档），已由单测覆盖边界。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.errors import AppError, NotFoundError, PermissionDeniedError
from app.models import (
    Exam,
    ExamAnswer,
    ExamKind,
    ExamStatus,
    KnowledgePoint,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    User,
)
from app.services import mastery_service
from app.services.mastery_service import BktParams, MasteryPoint

DEFAULT_TARGET_COUNT = 25
MIN_TARGET_COUNT = 20
MAX_TARGET_COUNT = 30
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
INITIAL_DIFFICULTY = 3


@dataclass(slots=True)
class QuestionCandidate:
    """候选题目（在目标难度与知识点偏好下排序）。"""

    question_id: uuid.UUID
    difficulty: int
    knowledge_point_ids: list[uuid.UUID]
    sort_key: tuple[datetime, str]


@dataclass(slots=True)
class DiagnosisAnswerResult:
    """一次作答的判定结果。"""

    is_correct: bool
    correct_answer: str
    answered: int
    total: int
    finished: bool
    exam: Exam
    next_question: Question | None = None


def adjust_difficulty(current: int, correct: bool) -> int:
    """答对加难、答错降难（1~5 档）。"""
    if correct:
        return min(MAX_DIFFICULTY, current + 1)
    return max(MIN_DIFFICULTY, current - 1)


def select_candidate(
    candidates: list[QuestionCandidate],
    mastery_by_kp: dict[uuid.UUID, float],
    *,
    preferred_difficulty: int,
    params: BktParams = mastery_service.DEFAULT_BKT,
) -> QuestionCandidate | None:
    """按「最弱知识点优先 + 难度最接近」排序取一题。"""

    def score(candidate: QuestionCandidate) -> tuple[float, int, datetime, str]:
        mastery = min(
            (mastery_by_kp.get(kp_id, params.p_init) for kp_id in candidate.knowledge_point_ids),
            default=params.p_init,
        )
        return (
            round(mastery, 4),
            abs(candidate.difficulty - preferred_difficulty),
            candidate.sort_key[0],
            candidate.sort_key[1],
        )

    if not candidates:
        return None
    return min(candidates, key=score)


def normalize_answer(value: str) -> str:
    """作答归一化（去空白、全角转半角、大小写统一）。"""
    translation = str.maketrans("０１２３４５６７８９ＡＢＣＤａｂｃｄ", "0123456789ABCDabcd")
    return value.translate(translation).strip().lower()


def check_answer(question: Question, user_answer: str) -> bool:
    """客观题判定（选择题比较选项字母，填空比较归一化文本）。"""
    return normalize_answer(question.answer) == normalize_answer(user_answer)


async def _build_candidates(
    session: AsyncSession, *, subject: str, stage: str, exclude: set[uuid.UUID]
) -> tuple[list[QuestionCandidate], set[uuid.UUID]]:
    """加载候选题目与知识点范围。"""
    rows = (
        await session.execute(
            select(
                Question.id,
                Question.difficulty,
                Question.created_at,
                QuestionKnowledgePoint.knowledge_point_id,
            )
            .join(QuestionKnowledgePoint, QuestionKnowledgePoint.question_id == Question.id)
            .where(
                Question.subject == subject,
                Question.stage == stage,
                Question.status == QuestionStatus.PUBLISHED,
            )
        )
    ).all()
    grouped: dict[uuid.UUID, QuestionCandidate] = {}
    scope_kp_ids: set[uuid.UUID] = set()
    for question_id, difficulty, created_at, kp_id in rows:
        scope_kp_ids.add(kp_id)
        candidate = grouped.get(question_id)
        if candidate is None:
            candidate = QuestionCandidate(
                question_id=question_id,
                difficulty=int(difficulty),
                knowledge_point_ids=[],
                sort_key=(created_at, str(question_id)),
            )
            grouped[question_id] = candidate
        candidate.knowledge_point_ids.append(kp_id)
    candidates = [item for item in grouped.values() if item.question_id not in exclude]
    return candidates, scope_kp_ids


async def _load_question(session: AsyncSession, question_id: uuid.UUID) -> Question:
    question = await session.get(Question, question_id)
    if question is None:
        raise NotFoundError("题目不存在", code="QUESTION_NOT_FOUND")
    return question


async def start_diagnosis(
    session: AsyncSession,
    *,
    user: User,
    subject: str,
    stage: str,
    target_count: int = DEFAULT_TARGET_COUNT,
) -> tuple[Exam, Question]:
    """开启诊断：创建测评实例并返回第一题。"""
    if not MIN_TARGET_COUNT <= target_count <= MAX_TARGET_COUNT:
        raise AppError(
            f"诊断题量需在 {MIN_TARGET_COUNT}~{MAX_TARGET_COUNT} 之间",
            code="DIAGNOSIS_INVALID_TARGET",
            status_code=400,
        )
    candidates, scope_kp_ids = await _build_candidates(
        session, subject=subject, stage=stage, exclude=set()
    )
    if not candidates or not scope_kp_ids:
        raise AppError("题库中暂无可用题目", code="DIAGNOSIS_NO_QUESTIONS", status_code=409)

    first = select_candidate(candidates, {}, preferred_difficulty=INITIAL_DIFFICULTY)
    assert first is not None  # candidates 非空已在上方保证
    exam = Exam(
        user_id=user.id,
        kind=ExamKind.DIAGNOSIS,
        title=f"{subject}·{stage} 入学诊断",
        time_limit_minutes=0,
        status=ExamStatus.IN_PROGRESS,
        started_at=utcnow(),
        meta={
            "subject": subject,
            "stage": stage,
            "target_count": target_count,
            "answered": 0,
            "correct": 0,
            "difficulty": INITIAL_DIFFICULTY,
            "asked": [first.question_id.hex],
            "current_question": first.question_id.hex,
            "scope_knowledge_points": sorted(str(kp_id) for kp_id in scope_kp_ids),
        },
    )
    session.add(exam)
    await session.flush()
    return exam, await _load_question(session, first.question_id)


async def _get_exam(session: AsyncSession, *, user: User, exam_id: uuid.UUID) -> Exam:
    exam = await session.get(Exam, exam_id)
    if exam is None or exam.kind != ExamKind.DIAGNOSIS:
        raise NotFoundError("诊断记录不存在", code="DIAGNOSIS_NOT_FOUND")
    if exam.user_id != user.id:
        raise PermissionDeniedError("无权访问该诊断记录")
    return exam


async def submit_answer(
    session: AsyncSession,
    *,
    user: User,
    exam_id: uuid.UUID,
    question_id: uuid.UUID,
    user_answer: str,
) -> DiagnosisAnswerResult:
    """提交一道作答：判定、画像更新、难度调节、选题或收卷。"""
    exam = await _get_exam(session, user=user, exam_id=exam_id)
    if exam.status != ExamStatus.IN_PROGRESS:
        raise AppError("本次诊断已结束", code="DIAGNOSIS_FINISHED", status_code=409)

    asked: list[str] = list(exam.meta.get("asked", []))
    if question_id.hex not in asked:
        raise AppError("该题目不属于本次诊断", code="DIAGNOSIS_QUESTION_MISMATCH", status_code=400)

    existing = (
        await session.execute(
            select(ExamAnswer.id).where(
                ExamAnswer.exam_id == exam_id, ExamAnswer.question_id == question_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise AppError("该题目已作答", code="DIAGNOSIS_ALREADY_ANSWERED", status_code=409)

    question = await _load_question(session, question_id)
    is_correct = check_answer(question, user_answer)
    session.add(
        ExamAnswer(
            exam_id=exam_id,
            question_id=question_id,
            user_answer={"answer": user_answer},
            is_correct=is_correct,
            score=1.0 if is_correct else 0.0,
        )
    )

    kp_rows = (
        await session.execute(
            select(QuestionKnowledgePoint.knowledge_point_id).where(
                QuestionKnowledgePoint.question_id == question_id
            )
        )
    ).scalars()
    kp_ids = list(kp_rows)
    for kp_id in kp_ids:
        await mastery_service.record_practice(
            session, user_id=user.id, knowledge_point_id=kp_id, correct=is_correct
        )

    answered = int(exam.meta.get("answered", 0)) + 1
    correct_count = int(exam.meta.get("correct", 0)) + (1 if is_correct else 0)
    current_difficulty = int(exam.meta.get("difficulty", INITIAL_DIFFICULTY))
    next_difficulty = adjust_difficulty(current_difficulty, is_correct)
    target_count = int(exam.meta.get("target_count", DEFAULT_TARGET_COUNT))

    exam.meta = {
        **exam.meta,
        "answered": answered,
        "correct": correct_count,
        "difficulty": next_difficulty,
        "last_answer_correct": is_correct,
    }

    next_question: Question | None = None
    finished = False
    if answered >= target_count:
        await _finalize(session, exam)
        finished = True
    else:
        candidates, _ = await _build_candidates(
            session,
            subject=str(exam.meta.get("subject", "math")),
            stage=str(exam.meta.get("stage", "junior")),
            exclude={uuid.UUID(hex=item) for item in asked},
        )
        mastery_points = await mastery_service.get_mastery_overview(session, user_id=user.id)
        mastery_by_kp = {point.knowledge_point_id: point.mastery for point in mastery_points}
        candidate = select_candidate(
            candidates, mastery_by_kp, preferred_difficulty=next_difficulty
        )
        if candidate is None:
            await _finalize(session, exam)
            finished = True
        else:
            exam.meta = {
                **exam.meta,
                "asked": [*asked, candidate.question_id.hex],
                "current_question": candidate.question_id.hex,
            }
            next_question = await _load_question(session, candidate.question_id)

    await session.flush()
    return DiagnosisAnswerResult(
        is_correct=is_correct,
        correct_answer=question.answer,
        answered=answered,
        total=target_count,
        finished=finished,
        exam=exam,
        next_question=next_question,
    )


async def _finalize(session: AsyncSession, exam: Exam) -> None:
    """收卷并生成报告数据。"""
    exam.status = ExamStatus.SUBMITTED
    exam.submitted_at = utcnow()
    report = await _build_report(session, exam)
    exam.meta = {**exam.meta, "report": report}


async def _build_report(session: AsyncSession, exam: Exam) -> dict[str, Any]:
    """基于掌握度与作答明细生成报告数据。"""
    scope = [uuid.UUID(value) for value in exam.meta.get("scope_knowledge_points", [])]
    points = await mastery_service.get_mastery_overview(
        session, user_id=exam.user_id, knowledge_point_ids=scope
    )
    answered = int(exam.meta.get("answered", 0))
    correct_count = int(exam.meta.get("correct", 0))
    accuracy = round(correct_count / answered, 4) if answered else 0.0
    weakest = [point.name for point in points[:3]]
    return {
        "answered": answered,
        "correct": correct_count,
        "accuracy": accuracy,
        "final_difficulty": int(exam.meta.get("difficulty", INITIAL_DIFFICULTY)),
        "red_count": sum(1 for point in points if point.level == "red"),
        "yellow_count": sum(1 for point in points if point.level == "yellow"),
        "green_count": sum(1 for point in points if point.level == "green"),
        "weakest": weakest,
        "suggestions": [
            f"优先复习：{'、'.join(weakest)}" if weakest else "继续保持每日练习",
            "针对薄弱知识点使用「守护型讲解」逐层理解，再进入专项练习。",
        ],
    }


@dataclass(slots=True)
class DiagnosisReport:
    """诊断报告视图。"""

    exam: Exam
    summary: dict[str, Any]
    points: list[MasteryPoint] = field(default_factory=list)


async def get_report(session: AsyncSession, *, user: User, exam_id: uuid.UUID) -> DiagnosisReport:
    """获取诊断报告（未结束返回 409）。"""
    exam = await _get_exam(session, user=user, exam_id=exam_id)
    if exam.status != ExamStatus.SUBMITTED:
        raise AppError("诊断尚未结束", code="DIAGNOSIS_NOT_FINISHED", status_code=409)
    report = exam.meta.get("report")
    if not isinstance(report, dict):
        report = await _build_report(session, exam)
        exam.meta = {**exam.meta, "report": report}
        await session.flush()
    scope = [uuid.UUID(value) for value in exam.meta.get("scope_knowledge_points", [])]
    points = await mastery_service.get_mastery_overview(
        session, user_id=exam.user_id, knowledge_point_ids=scope
    )
    return DiagnosisReport(exam=exam, summary=report, points=points)


async def list_exam_questions(session: AsyncSession, exam: Exam) -> list[Question]:
    """按作答顺序返回试题（用于测试与复盘）。"""
    asked = exam.meta.get("asked", [])
    questions: list[Question] = []
    for value in asked:
        question = await session.get(Question, uuid.UUID(hex=str(value)))
        if question is not None:
            questions.append(question)
    return questions


async def question_knowledge_point_names(
    session: AsyncSession, question_id: uuid.UUID
) -> list[str]:
    """题目的知识点名称列表（响应组装用）。"""
    rows = (
        await session.execute(
            select(KnowledgePoint.name)
            .join(
                QuestionKnowledgePoint,
                QuestionKnowledgePoint.knowledge_point_id == KnowledgePoint.id,
            )
            .where(QuestionKnowledgePoint.question_id == question_id)
        )
    ).scalars()
    return list(rows)
