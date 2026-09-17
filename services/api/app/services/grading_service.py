"""批改服务（F-22/F-23/F-24）：客观题秒批、主观题评分细则引擎、作文三口径。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import LlmError, NotFoundError
from app.models import (
    ChatScene,
    ChatSession,
    GradingKind,
    GradingRecord,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    User,
)
from app.services import mastery_service, math_verify
from app.services.diagnosis_service import check_answer
from app.services.llm_client import LlmClient
from app.services.llm_json import extract_json_object
from app.services.prompts import (
    ESSAY_GRADING_SYSTEM_PROMPT,
    ESSAY_GRADING_USER_TEMPLATE,
    ESSAY_RUBRIC_LABELS,
    SUBJECTIVE_GRADING_SYSTEM_PROMPT,
    SUBJECTIVE_GRADING_USER_TEMPLATE,
)

# 主观/作文批改不做 LLM 重试之外的限制；JSON 解析失败给出明确错误码
SUBJECTIVE_BAD_OUTPUT = "GRADING_BAD_OUTPUT"
ESSAY_BAD_OUTPUT = "GRADING_BAD_OUTPUT"


@dataclass(slots=True)
class ObjectiveGradingResult:
    """客观题批改结果（秒批）。"""

    is_correct: bool
    correct_answer: str
    analysis: str | None
    tutor_session_id: uuid.UUID | None = None


@dataclass(slots=True)
class StepScore:
    """逐步得分点。"""

    step: str
    score: float
    comment: str
    lost_points: str


@dataclass(slots=True)
class SubjectiveGradingResult:
    """主观题批改结果。"""

    total_score: float
    max_score: float
    steps: list[StepScore] = field(default_factory=list)
    rewrite: str = ""
    summary: str = ""
    machine_check: dict[str, Any] | None = None


@dataclass(slots=True)
class DimensionScore:
    """作文维度分。"""

    score: float
    max_score: float
    comment: str


@dataclass(slots=True)
class ParagraphComment:
    """逐段评语。"""

    index: int
    comment: str
    suggestion: str


@dataclass(slots=True)
class EssayGradingResult:
    """作文批改结果。"""

    total_score: float
    max_score: float
    rubric: str
    structure: DimensionScore
    ideas: DimensionScore
    language: DimensionScore
    paragraphs: list[ParagraphComment] = field(default_factory=list)
    upgrade_sample: str = ""
    summary: str = ""


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_dimension(raw: Any, default_max: float) -> DimensionScore:
    if not isinstance(raw, dict):
        return DimensionScore(score=0.0, max_score=default_max, comment="")
    return DimensionScore(
        score=_as_float(raw.get("score")),
        max_score=_as_float(raw.get("max_score"), default_max),
        comment=str(raw.get("comment", "")).strip(),
    )


async def grade_objective(
    session: AsyncSession,
    *,
    user: User,
    question_id: uuid.UUID,
    user_answer: str,
) -> ObjectiveGradingResult:
    """客观题即时批改；答错时创建讲解会话直达守护型讲解（F-22）。"""
    question = await session.get(Question, question_id)
    if question is None or question.status != QuestionStatus.PUBLISHED:
        raise NotFoundError("题目不存在", code="QUESTION_NOT_FOUND")

    is_correct = check_answer(question, user_answer)
    session.add(
        GradingRecord(
            user_id=user.id,
            question_id=question.id,
            kind=GradingKind.OBJECTIVE,
            input_payload={"answer": user_answer},
            result={"is_correct": is_correct, "correct_answer": question.answer},
            score=1.0 if is_correct else 0.0,
        )
    )

    kp_ids = list(
        (
            await session.execute(
                select(QuestionKnowledgePoint.knowledge_point_id).where(
                    QuestionKnowledgePoint.question_id == question.id
                )
            )
        ).scalars()
    )
    for kp_id in kp_ids:
        await mastery_service.record_practice(
            session, user_id=user.id, knowledge_point_id=kp_id, correct=is_correct
        )

    tutor_session_id: uuid.UUID | None = None
    if not is_correct:
        chat = ChatSession(
            user_id=user.id,
            scene=ChatScene.TUTOR,
            question_id=question.id,
            title=f"讲解：{question.stem[:30]}",
            hint_level=0,
            meta={"from": "grading.objective"},
        )
        session.add(chat)
        await session.flush()
        tutor_session_id = chat.id
    await session.flush()
    return ObjectiveGradingResult(
        is_correct=is_correct,
        correct_answer=question.answer,
        analysis=question.analysis,
        tutor_session_id=tutor_session_id,
    )


async def grade_subjective(
    session: AsyncSession,
    *,
    user: User,
    llm: LlmClient,
    student_answer: str,
    question_id: uuid.UUID | None = None,
    stem: str | None = None,
    answer: str | None = None,
    criteria: str | None = None,
    trace_id: str | None = None,
) -> SubjectiveGradingResult:
    """主观解答题批改：评分细则 + 逐步给分 + 改写示范 + 数学 SymPy 抽检（F-23）。"""
    question: Question | None = None
    if question_id is not None:
        question = await session.get(Question, question_id)
        if question is None:
            raise NotFoundError("题目不存在", code="QUESTION_NOT_FOUND")
    prompt_stem = stem or (question.stem if question else None)
    prompt_answer = answer or (question.answer if question else None)
    if not prompt_stem or not prompt_answer:
        raise LlmError(
            "缺少题目或标准答案（请传 question_id 或 stem+answer）",
            code="GRADING_MISSING_CONTEXT",
            status_code=400,
        )

    default_criteria = "按步骤给分：关键公式/思路各占 40%，计算与结论各占 30%（共 100%）。"
    completion = await llm.complete(
        [
            {"role": "system", "content": SUBJECTIVE_GRADING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": SUBJECTIVE_GRADING_USER_TEMPLATE.format(
                    stem=prompt_stem,
                    answer=prompt_answer,
                    criteria=criteria or default_criteria,
                    student_answer=student_answer,
                ),
            },
        ],
        name="grading.subjective",
        trace_id=trace_id,
        temperature=0.2,
    )
    payload = extract_json_object(completion.content, code=SUBJECTIVE_BAD_OUTPUT)

    steps: list[StepScore] = []
    raw_steps = payload.get("steps")
    if isinstance(raw_steps, list):
        for raw in raw_steps:
            if isinstance(raw, dict):
                steps.append(
                    StepScore(
                        step=str(raw.get("step", "")).strip(),
                        score=_as_float(raw.get("score")),
                        comment=str(raw.get("comment", "")).strip(),
                        lost_points=str(raw.get("lost_points", "")).strip(),
                    )
                )

    machine_check: dict[str, Any] | None = None
    question_subject = question.subject if question else "math"
    if question_subject == "math":
        machine_check = {
            "checked": True,
            "answer_verified": math_verify.verify_contains_answer(
                student_answer, prompt_answer
            ),
        }

    result = SubjectiveGradingResult(
        total_score=_as_float(payload.get("total_score")),
        max_score=_as_float(payload.get("max_score"), 100.0),
        steps=steps,
        rewrite=str(payload.get("rewrite", "")).strip(),
        summary=str(payload.get("summary", "")).strip(),
        machine_check=machine_check,
    )
    session.add(
        GradingRecord(
            user_id=user.id,
            question_id=question.id if question else None,
            kind=GradingKind.SUBJECTIVE,
            input_payload={"student_answer": student_answer, "criteria": criteria},
            result={
                "total_score": result.total_score,
                "max_score": result.max_score,
                "step_count": len(result.steps),
                "machine_check": machine_check,
            },
            score=result.total_score,
            model=completion.model,
            trace_id=trace_id,
            latency_ms=completion.latency_ms,
            excerpt=student_answer[:200],
        )
    )
    await session.flush()
    return result


async def grade_essay(
    session: AsyncSession,
    *,
    user: User,
    llm: LlmClient,
    rubric: str,
    content: str,
    prompt_text: str | None = None,
    trace_id: str | None = None,
) -> EssayGradingResult:
    """作文批改：结构/立意/语言三维 + 逐段评语 + 升格范文（F-24）。"""
    rubric_label = ESSAY_RUBRIC_LABELS.get(rubric, rubric)
    completion = await llm.complete(
        [
            {"role": "system", "content": ESSAY_GRADING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": ESSAY_GRADING_USER_TEMPLATE.format(
                    rubric_label=rubric_label,
                    prompt=prompt_text or "（未提供题目，请按常规审题批改）",
                    content=content,
                ),
            },
        ],
        name="grading.essay",
        trace_id=trace_id,
        temperature=0.3,
    )
    payload = extract_json_object(completion.content, code=ESSAY_BAD_OUTPUT)

    paragraphs: list[ParagraphComment] = []
    raw_paragraphs = payload.get("paragraphs")
    if isinstance(raw_paragraphs, list):
        for raw in raw_paragraphs:
            if isinstance(raw, dict):
                paragraphs.append(
                    ParagraphComment(
                        index=int(_as_float(raw.get("index"))),
                        comment=str(raw.get("comment", "")).strip(),
                        suggestion=str(raw.get("suggestion", "")).strip(),
                    )
                )

    result = EssayGradingResult(
        total_score=_as_float(payload.get("total_score")),
        max_score=_as_float(payload.get("max_score"), 100.0),
        rubric=rubric,
        structure=_as_dimension(payload.get("structure"), 40.0),
        ideas=_as_dimension(payload.get("ideas"), 40.0),
        language=_as_dimension(payload.get("language"), 20.0),
        paragraphs=paragraphs,
        upgrade_sample=str(payload.get("upgrade_sample", "")).strip(),
        summary=str(payload.get("summary", "")).strip(),
    )
    session.add(
        GradingRecord(
            user_id=user.id,
            question_id=None,
            kind=GradingKind.ESSAY,
            input_payload={"rubric": rubric, "prompt": prompt_text},
            result={
                "total_score": result.total_score,
                "dimensions": {
                    "structure": result.structure.score,
                    "ideas": result.ideas.score,
                    "language": result.language.score,
                },
                "paragraph_count": len(result.paragraphs),
            },
            score=result.total_score,
            model=completion.model,
            trace_id=trace_id,
            latency_ms=completion.latency_ms,
            excerpt=content[:200],
        )
    )
    await session.flush()
    return result
