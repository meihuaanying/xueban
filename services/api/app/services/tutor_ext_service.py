"""讲解扩展服务（F-12~F-14）：多解法、生活化类比、变式题与答错回炉。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.errors import LlmError, NotFoundError
from app.models import (
    ChatMessage,
    ChatRole,
    ChatScene,
    ChatSession,
    MistakeBookEntry,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    User,
)
from app.services import exam_service, mastery_service, math_verify, tutor_service
from app.services.diagnosis_service import check_answer
from app.services.llm_client import LlmClient
from app.services.llm_json import extract_json_object
from app.services.prompts import (
    ALT_SOLUTIONS_SYSTEM_PROMPT,
    ALT_SOLUTIONS_USER_TEMPLATE,
    ANALOGY_SYSTEM_PROMPT,
    ANALOGY_USER_TEMPLATE,
    VARIANTS_SYSTEM_PROMPT,
    VARIANTS_USER_TEMPLATE,
)


@dataclass(slots=True)
class AltSolutionItem:
    """一种解法。"""

    title: str
    steps: list[str]
    scenario: str
    answer_verified: bool


@dataclass(slots=True)
class AltSolutionsResult:
    """多解法对比结果。"""

    solutions: list[AltSolutionItem]
    checked_count: int
    verified_count: int


@dataclass(slots=True)
class AnalogyResult:
    """生活化类比。"""

    analogy: str
    mapping: str
    caveat: str


@dataclass(slots=True)
class VariantItem:
    """生成的变式题（对外不含答案）。"""

    question_id: uuid.UUID
    stem: str
    options: dict[str, str] | None
    difficulty: int


@dataclass(slots=True)
class VariantsResult:
    """变式题结果。"""

    variants: list[VariantItem]


@dataclass(slots=True)
class BackToTutor:
    """答错回炉：开启新的讲解会话。"""

    session_id: uuid.UUID
    message: str


@dataclass(slots=True)
class VariantAnswerResult:
    """变式题作答结果。"""

    is_correct: bool
    correct_answer: str
    back_to_tutor: BackToTutor | None = None


async def _load_context(
    session: AsyncSession, *, user: User, session_id: uuid.UUID
) -> tuple[ChatSession, Question]:
    """加载会话与题目（含 solo 锁校验）。"""
    await exam_service.ensure_no_active_solo(session, user_id=user.id)
    chat = await tutor_service._load_chat_session(session, user_id=user.id, session_id=session_id)
    tutor_service.ensure_solo_unlocked(chat)
    question = await tutor_service._load_question(session, chat.question_id)
    return chat, question


async def _question_knowledge_points(
    session: AsyncSession, question_id: uuid.UUID
) -> list[uuid.UUID]:
    rows = (
        await session.execute(
            select(QuestionKnowledgePoint.knowledge_point_id).where(
                QuestionKnowledgePoint.question_id == question_id
            )
        )
    ).scalars()
    return list(rows)


async def generate_alt_solutions(
    session: AsyncSession,
    *,
    user: User,
    session_id: uuid.UUID,
    llm: LlmClient,
    trace_id: str | None = None,
) -> AltSolutionsResult:
    """生成 2~3 种解法并做 SymPy 等价性抽检（F-12）。"""
    chat, question = await _load_context(session, user=user, session_id=session_id)
    completion = await llm.complete(
        [
            {"role": "system", "content": ALT_SOLUTIONS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": ALT_SOLUTIONS_USER_TEMPLATE.format(
                    stem=question.stem, qtype=question.qtype.value, answer=question.answer
                ),
            },
        ],
        name="tutor.alt_solutions",
        trace_id=trace_id,
        temperature=0.3,
    )
    payload = extract_json_object(completion.content, code="ALT_SOLUTIONS_BAD_OUTPUT")
    raw_solutions = payload.get("solutions")
    if not isinstance(raw_solutions, list):
        raise LlmError("解法列表缺失", code="ALT_SOLUTIONS_BAD_OUTPUT", status_code=502)

    items: list[AltSolutionItem] = []
    for raw in raw_solutions[:3]:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", "")).strip()
        steps_raw = raw.get("steps")
        steps = (
            [str(item).strip() for item in steps_raw if str(item).strip()]
            if isinstance(steps_raw, list)
            else []
        )
        scenario = str(raw.get("scenario", "")).strip()
        if not title or not steps:
            continue
        verified = question.subject == "math" and math_verify.verify_contains_answer(
            " ".join(steps), question.answer
        )
        items.append(
            AltSolutionItem(title=title, steps=steps, scenario=scenario, answer_verified=verified)
        )
    if len(items) < 2:
        raise LlmError("至少需要两种有效解法", code="ALT_SOLUTIONS_BAD_OUTPUT", status_code=502)

    session.add(
        ChatMessage(
            session_id=chat.id,
            role=ChatRole.ASSISTANT,
            content=json.dumps(
                {
                    "type": "alt_solutions",
                    "solutions": [
                        {
                            "title": item.title,
                            "steps": item.steps,
                            "scenario": item.scenario,
                            "answer_verified": item.answer_verified,
                        }
                        for item in items
                    ],
                },
                ensure_ascii=False,
            ),
            hint_level=chat.hint_level,
        )
    )
    chat.last_message_at = utcnow()
    await session.flush()
    is_math = question.subject == "math"
    return AltSolutionsResult(
        solutions=items,
        checked_count=len(items) if is_math else 0,
        verified_count=sum(1 for item in items if item.answer_verified),
    )


async def generate_analogy(
    session: AsyncSession,
    *,
    user: User,
    session_id: uuid.UUID,
    llm: LlmClient,
    trace_id: str | None = None,
) -> AnalogyResult:
    """生成生活化类比（F-13）。"""
    chat, question = await _load_context(session, user=user, session_id=session_id)
    from app.models import KnowledgePoint

    kp_names = list(
        (
            await session.execute(
                select(KnowledgePoint.name)
                .join(
                    QuestionKnowledgePoint,
                    QuestionKnowledgePoint.knowledge_point_id == KnowledgePoint.id,
                )
                .where(QuestionKnowledgePoint.question_id == question.id)
            )
        ).scalars()
    )
    knowledge_points_block = (
        f"相关知识点：{'、'.join(kp_names)}\n" if kp_names else ""
    )
    completion = await llm.complete(
        [
            {"role": "system", "content": ANALOGY_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": ANALOGY_USER_TEMPLATE.format(
                    stem=question.stem,
                    knowledge_points_block=knowledge_points_block,
                ),
            },
        ],
        name="tutor.analogy",
        trace_id=trace_id,
        temperature=0.8,
    )
    payload = extract_json_object(completion.content, code="ANALOGY_BAD_OUTPUT")
    analogy = str(payload.get("analogy", "")).strip()
    if not analogy:
        raise LlmError("类比内容缺失", code="ANALOGY_BAD_OUTPUT", status_code=502)
    result = AnalogyResult(
        analogy=analogy,
        mapping=str(payload.get("mapping", "")).strip(),
        caveat=str(payload.get("caveat", "")).strip(),
    )
    session.add(
        ChatMessage(
            session_id=chat.id,
            role=ChatRole.ASSISTANT,
            content=json.dumps(
                {
                    "type": "analogy",
                    "analogy": result.analogy,
                    "mapping": result.mapping,
                    "caveat": result.caveat,
                },
                ensure_ascii=False,
            ),
            hint_level=chat.hint_level,
        )
    )
    chat.last_message_at = utcnow()
    await session.flush()
    return result


async def generate_variants(
    session: AsyncSession,
    *,
    user: User,
    session_id: uuid.UUID,
    llm: LlmClient,
    trace_id: str | None = None,
) -> VariantsResult:
    """生成 1~2 道变式题（同知识点不同情境，F-14）。"""
    chat, question = await _load_context(session, user=user, session_id=session_id)
    kp_ids = await _question_knowledge_points(session, question.id)
    from app.models import KnowledgePoint

    kp_names = list(
        (
            await session.execute(
                select(KnowledgePoint.name).where(KnowledgePoint.id.in_(kp_ids))
            )
        ).scalars()
    )
    completion = await llm.complete(
        [
            {"role": "system", "content": VARIANTS_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": VARIANTS_USER_TEMPLATE.format(
                    stem=question.stem,
                    qtype=question.qtype.value,
                    answer=question.answer,
                    knowledge_points="、".join(kp_names) or "未标注",
                ),
            },
        ],
        name="tutor.variants",
        trace_id=trace_id,
        temperature=0.7,
    )
    payload = extract_json_object(completion.content, code="VARIANTS_BAD_OUTPUT")
    raw_variants = payload.get("variants")
    if not isinstance(raw_variants, list):
        raise LlmError("变式题列表缺失", code="VARIANTS_BAD_OUTPUT", status_code=502)

    created: list[VariantItem] = []
    for raw in raw_variants[:2]:
        if not isinstance(raw, dict):
            continue
        stem = str(raw.get("stem", "")).strip()
        answer = str(raw.get("answer", "")).strip()
        if not stem or not answer:
            continue
        raw_options = raw.get("options")
        options = (
            {str(key): str(value) for key, value in raw_options.items()}
            if isinstance(raw_options, dict) and raw_options
            else None
        )
        if question.qtype.value == "choice" and not options:
            continue
        analysis = str(raw.get("analysis", "")).strip() or f"参考答案：{answer}。"
        variant = Question(
            subject=question.subject,
            stage=question.stage,
            qtype=question.qtype,
            stem=stem,
            options=options,
            answer=answer,
            analysis=analysis,
            difficulty=question.difficulty,
            source="tutor-variant",
            status=QuestionStatus.PUBLISHED,
            created_by=user.id,
        )
        session.add(variant)
        await session.flush()
        for kp_id in kp_ids:
            session.add(
                QuestionKnowledgePoint(question_id=variant.id, knowledge_point_id=kp_id)
            )
        created.append(
            VariantItem(
                question_id=variant.id,
                stem=stem,
                options=options,
                difficulty=variant.difficulty,
            )
        )
    if not created:
        raise LlmError("未能生成有效变式题", code="VARIANTS_BAD_OUTPUT", status_code=502)

    session.add(
        ChatMessage(
            session_id=chat.id,
            role=ChatRole.ASSISTANT,
            content=json.dumps(
                {
                    "type": "variants",
                    "variants": [
                        {"question_id": str(item.question_id), "stem": item.stem}
                        for item in created
                    ],
                },
                ensure_ascii=False,
            ),
            hint_level=chat.hint_level,
        )
    )
    chat.last_message_at = utcnow()
    await session.flush()
    return VariantsResult(variants=created)


async def answer_variant(
    session: AsyncSession,
    *,
    user: User,
    session_id: uuid.UUID,
    variant_id: uuid.UUID,
    user_answer: str,
) -> VariantAnswerResult:
    """变式题作答：答对计入掌握度；答错入错题本并开启回炉讲解（F-14）。"""
    await _load_context(session, user=user, session_id=session_id)
    variant = await session.get(Question, variant_id)
    if (
        variant is None
        or variant.source != "tutor-variant"
        or variant.created_by != user.id
    ):
        raise NotFoundError("变式题不存在", code="VARIANT_NOT_FOUND")

    is_correct = check_answer(variant, user_answer)
    kp_ids = await _question_knowledge_points(session, variant.id)
    for kp_id in kp_ids:
        await mastery_service.record_practice(
            session, user_id=user.id, knowledge_point_id=kp_id, correct=is_correct
        )

    if is_correct:
        await session.flush()
        return VariantAnswerResult(is_correct=True, correct_answer=variant.answer)

    entry = (
        await session.execute(
            select(MistakeBookEntry).where(
                MistakeBookEntry.user_id == user.id,
                MistakeBookEntry.question_id == variant.id,
            )
        )
    ).scalar_one_or_none()
    if entry is None:
        session.add(
            MistakeBookEntry(
                user_id=user.id,
                question_id=variant.id,
                wrong_answer=user_answer,
                source="variant",
            )
        )
    else:
        entry.wrong_answer = user_answer
        entry.removed_at = None

    back_session = ChatSession(
        user_id=user.id,
        scene=ChatScene.TUTOR,
        question_id=variant.id,
        title=f"回炉：{variant.stem[:20]}",
        hint_level=0,
        meta={"from": "variant", "source_session": str(session_id)},
    )
    session.add(back_session)
    await session.flush()
    return VariantAnswerResult(
        is_correct=False,
        correct_answer=variant.answer,
        back_to_tutor=BackToTutor(
            session_id=back_session.id,
            message=(
                "这道变式题答错了。已为你开启回炉讲解：从思路提示开始重新理解，"
                "弄懂后再做一遍同类题。"
            ),
        ),
    )
