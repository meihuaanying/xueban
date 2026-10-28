"""模考与无辅助测评（F-20/F-28）：限时考试、即时出分、百分位、逐题诊断、服务端强制禁提示。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.exam_blueprints import get_exam as get_blueprint
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
    QuestionType,
    User,
)
from app.services import grading_service, mastery_service
from app.services.diagnosis_service import check_answer
from app.services.grading_service import SubjectiveGradingResult
from app.services.llm_client import LlmClient

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


#: 蓝图题型（中文部分名）→ 题库 qtype。解答题用 short_answer 承载，
#: 交卷时按主观题处理（不自动判分，等主观批改）。
_BLUEPRINT_PART_QTYPE: dict[str, QuestionType] = {
    "单项选择题": QuestionType.CHOICE,
    "多项选择题": QuestionType.MULTI_CHOICE,
    "填空题": QuestionType.FILL,
    "解答题": QuestionType.SHORT_ANSWER,
}


async def _sample_by_qtype(
    session: AsyncSession, *, qtype: QuestionType, count: int, exclude: set[uuid.UUID]
) -> list[Question]:
    """按题型随机抽题（senior 数学、PUBLISHED）。"""
    rows = (
        await session.execute(
            select(Question)
            .where(
                Question.subject == "math",
                Question.stage == "senior",
                Question.status == QuestionStatus.PUBLISHED,
                Question.qtype == qtype,
            )
            .order_by(func.random())
        )
    ).scalars()
    picked: list[Question] = []
    for question in rows:
        if question.id in exclude:
            continue
        picked.append(question)
        if len(picked) >= count:
            break
    return picked


async def create_blueprint_exam(
    session: AsyncSession,
    *,
    user: User,
    blueprint_id: str = "gaokao_2026_gd",
) -> ExamBundle:
    """按地区考卷蓝图组卷（新高考数学 19 题结构）。

    - 各题型按蓝图份数随机抽取（多选题已落地）；
    - 解答题进卷但标记为主观题：交卷时不自动判分，等主观批改；
    - 时长与总分取自蓝图（120 分钟 / 150 分）。
    """
    blueprint = get_blueprint(blueprint_id)
    if blueprint is None:
        raise NotFoundError("考卷结构不存在", code="EXAM_BLUEPRINT_NOT_FOUND")
    math = next(
        (item for item in blueprint.get("subjects", []) if item.get("subject") == "math"),
        None,
    )
    if not isinstance(math, dict):
        raise AppError("蓝图中没有数学科目", code="EXAM_BLUEPRINT_INVALID", status_code=422)
    structure = math.get("structure")
    if not isinstance(structure, list) or not structure:
        raise AppError("蓝图中没有数学题型结构", code="EXAM_BLUEPRINT_INVALID", status_code=422)

    questions: list[Question] = []
    used: set[uuid.UUID] = set()
    structure_meta: list[dict[str, Any]] = []
    subjective_scores: dict[str, float] = {}
    for part in structure:
        if not isinstance(part, dict):
            continue
        qtype = _BLUEPRINT_PART_QTYPE.get(str(part.get("part")))
        count = int(part.get("count") or 0)
        if qtype is None or count <= 0:
            continue
        picked = await _sample_by_qtype(session, qtype=qtype, count=count, exclude=used)
        if len(picked) < count:
            raise AppError(
                f"题库中「{part.get('part')}」题量不足（需要 {count} 道）",
                code="EXAM_NO_QUESTIONS",
                status_code=409,
            )
        part_scores = _part_scores(part, count)
        used.update(question.id for question in picked)
        questions.extend(picked)
        if qtype is QuestionType.SHORT_ANSWER:
            for question, score in zip(picked, part_scores, strict=False):
                subjective_scores[question.id.hex] = score
        structure_meta.append(
            {
                "part": part.get("part"),
                "qtype": qtype.value,
                "count": count,
                "per_score": part.get("per_score"),
                "scores": part.get("scores"),
                "score": part.get("score"),
            }
        )

    subjective_ids = [
        question.id.hex for question in questions if question.qtype is QuestionType.SHORT_ANSWER
    ]
    minutes = int(math.get("duration_minutes") or 120)
    deadline = utcnow() + timedelta(minutes=minutes)
    exam = Exam(
        user_id=user.id,
        kind=ExamKind.MOCK,
        title=f"高考数学新结构模考（{blueprint.get('name', blueprint_id)}）",
        time_limit_minutes=minutes,
        total_score=float(blueprint.get("total_score") or 150),
        status=ExamStatus.IN_PROGRESS,
        started_at=utcnow(),
        meta={
            "subject": "math",
            "stage": "senior",
            "question_ids": [question.id.hex for question in questions],
            "deadline": deadline.isoformat(),
            "kind_label": "高考模考",
            "blueprint_id": blueprint_id,
            "structure": structure_meta,
            "subjective_ids": subjective_ids,
            "subjective_scores": subjective_scores,
        },
    )
    session.add(exam)
    await session.flush()
    return ExamBundle(exam=exam, questions=questions)


def _part_scores(part: dict[str, Any], count: int) -> list[float]:
    """题型分项分值：优先 scores 数组，其次 per_score，最后按总分均分。"""
    raw = part.get("scores")
    if isinstance(raw, list) and len(raw) >= count:
        return [round(float(item), 2) for item in raw[:count]]
    per_score = part.get("per_score")
    if per_score:
        return [round(float(per_score), 2)] * count
    total = part.get("score")
    if total:
        return [round(float(total) / count, 2)] * count
    return [0.0] * count


async def _finalize(
    session: AsyncSession, *, exam: Exam, answers: dict[uuid.UUID, str], auto_submitted: bool
) -> None:
    """收卷：判分、画像、百分位、逐题诊断。

    蓝图模考（meta.subjective_ids 非空）走分值计分：客观题按蓝图 per_score
    累计，解答题标记主观待批（exam.score 保持 None，等主观批改后补总分）。
    """
    question_ids = [uuid.UUID(hex=str(item)) for item in exam.meta.get("question_ids", [])]
    diagnoses: list[dict[str, Any]] = []
    correct_count = 0
    subjective = {str(item) for item in exam.meta.get("subjective_ids", []) or []}
    part_score_by_qtype: dict[str, float] = {
        str(part.get("qtype")): float(part.get("per_score") or 0)
        for part in exam.meta.get("structure", []) or []
        if isinstance(part, dict) and part.get("qtype")
    }
    objective_earned = 0.0
    objective_total = 0.0
    subjective_pending = 0

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
        # meta 里的 id 是无连字符 hex，question_id.hex 同构，避免 uuid 字符串带杠不匹配
        if question_id.hex in subjective:
            # 主观题（解答题）：不自动判分，留待主观批改；不进掌握度更新
            subjective_pending += 1
            if question_id not in existing and user_answer is not None:
                session.add(
                    ExamAnswer(
                        exam_id=exam.id,
                        question_id=question.id,
                        user_answer={"answer": user_answer},
                        is_correct=None,
                        score=None,
                    )
                )
            diagnoses.append(
                {
                    "question_id": str(question.id),
                    "stem": question.stem,
                    "is_correct": None,
                    "correct_answer": question.answer,
                    "analysis": question.analysis,
                    "subjective": True,
                }
            )
            continue
        is_correct = False if user_answer is None else check_answer(question, user_answer)
        correct_count += 1 if is_correct else 0
        per_score = part_score_by_qtype.get(question.qtype.value, 0.0)
        objective_total += per_score
        if is_correct:
            objective_earned += per_score
        if question_id not in existing and user_answer is not None:
            session.add(
                ExamAnswer(
                    exam_id=exam.id,
                    question_id=question.id,
                    user_answer={"answer": user_answer},
                    is_correct=is_correct,
                    score=per_score if is_correct else 0.0,
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

    exam.status = ExamStatus.SUBMITTED
    exam.submitted_at = utcnow()

    if subjective:
        # 蓝图模考：客观题按蓝图分值计分（满分 73），解答题 77 分待主观批改，
        # 总分在批改完成前保持 None——用 73/150 冒充 150 制分数会误导考生。
        exam.score = None
        percentile = None
        score = None
    else:
        total = len(question_ids) or 1
        score = round(correct_count / total * 100, 1)
        exam.score = score
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
            "total": len(question_ids),
            "score": score,
            "percentile": percentile,
            "kind_label": exam.meta.get("kind_label"),
            "independent": exam.kind == ExamKind.SOLO,
            "objective_earned": round(objective_earned, 1),
            "objective_total": round(objective_total, 1),
            "subjective_pending": subjective_pending,
            "subjective_total": round(
                sum(
                    float(value)
                    for value in (exam.meta.get("subjective_scores") or {}).values()
                ),
                1,
            ),
        },
    }

    if exam.kind == ExamKind.SOLO and score is not None:
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


@dataclass(slots=True)
class ExamSubjectiveGrade:
    """解答题批改结果 + 整卷总分状态。"""

    grading: SubjectiveGradingResult
    question_score: float
    max_score: float
    exam_score: float | None
    graded_count: int
    subjective_count: int
    all_graded: bool


def _subjective_part_total(exam: Exam, count: int) -> float:
    """蓝图里解答题分项总分兜底：structure 中 short_answer 的 score / count。"""
    for part in exam.meta.get("structure", []) or []:
        if isinstance(part, dict) and part.get("qtype") == QuestionType.SHORT_ANSWER.value:
            total = part.get("score")
            if total and count:
                return round(float(total) / count, 2)
    return 0.0


async def grade_subjective_answer(
    session: AsyncSession,
    *,
    user: User,
    exam_id: uuid.UUID,
    question_id: uuid.UUID,
    student_answer: str,
    llm: LlmClient,
    trace_id: str | None = None,
) -> ExamSubjectiveGrade:
    """批改蓝图模考的解答题并按题分值折算；全部批完才补整卷总分。"""
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise NotFoundError("测评不存在", code="EXAM_NOT_FOUND")
    if exam.user_id != user.id:
        raise PermissionDeniedError("无权访问该测评")
    if exam.status != ExamStatus.SUBMITTED:
        raise AppError("交卷后才能批改解答题", code="EXAM_NOT_SUBMITTED", status_code=409)
    subjective = {str(item) for item in (exam.meta.get("subjective_ids") or [])}
    if question_id.hex not in subjective:
        raise AppError("该题不是本卷的解答题", code="EXAM_NOT_SUBJECTIVE", status_code=422)
    question = await session.get(Question, question_id)
    if question is None:
        raise NotFoundError("题目不存在", code="QUESTION_NOT_FOUND")
    max_score = float(
        (exam.meta.get("subjective_scores") or {}).get(question_id.hex) or 0.0
    )
    if max_score <= 0:
        max_score = _subjective_part_total(exam, len(subjective))

    grading = await grading_service.grade_subjective(
        session,
        user=user,
        llm=llm,
        question_id=question_id,
        student_answer=student_answer,
        trace_id=trace_id,
    )
    ratio = grading.total_score / grading.max_score if grading.max_score > 0 else 0.0
    question_score = round(min(max(ratio, 0.0), 1.0) * max_score, 1)

    answer = (
        await session.execute(
            select(ExamAnswer).where(
                ExamAnswer.exam_id == exam.id,
                ExamAnswer.question_id == question_id,
            )
        )
    ).scalar_one_or_none()
    if answer is None:
        answer = ExamAnswer(
            exam_id=exam.id,
            question_id=question_id,
            user_answer={"answer": student_answer},
            is_correct=None,
        )
        session.add(answer)
    else:
        answer.user_answer = {"answer": student_answer}
    answer.score = question_score
    await session.flush()

    subjective_ids = [uuid.UUID(hex=item) for item in subjective]
    rows = (
        await session.execute(
            select(ExamAnswer.question_id, ExamAnswer.score).where(
                ExamAnswer.exam_id == exam.id,
                ExamAnswer.question_id.in_(subjective_ids),
            )
        )
    ).all()
    graded_scores = [float(score) for _, score in rows if score is not None]
    graded_count = len(graded_scores)
    all_graded = bool(subjective_ids) and graded_count >= len(subjective_ids)
    report = dict(exam.meta.get("report") or {})
    objective_earned = float(report.get("objective_earned") or 0.0)
    subjective_earned = round(sum(graded_scores), 1)
    exam_score = round(objective_earned + subjective_earned, 1) if all_graded else None
    exam.score = exam_score
    report.update(
        {
            "subjective_graded": graded_count,
            "subjective_earned": subjective_earned,
            "score": exam_score,
        }
    )
    exam.meta = {**exam.meta, "report": report}
    await session.flush()
    return ExamSubjectiveGrade(
        grading=grading,
        question_score=question_score,
        max_score=max_score,
        exam_score=exam_score,
        graded_count=graded_count,
        subjective_count=len(subjective_ids),
        all_graded=all_graded,
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
