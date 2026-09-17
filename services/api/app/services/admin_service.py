"""题库与解析管理（F-44）：三态审核流、版本历史、覆盖率看板。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, NotFoundError
from app.models import Question, QuestionKnowledgePoint, QuestionStatus, QuestionVersion, User

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    QuestionStatus.DRAFT.value: {QuestionStatus.REVIEW.value},
    QuestionStatus.REVIEW.value: {QuestionStatus.PUBLISHED.value, QuestionStatus.DRAFT.value},
    QuestionStatus.PUBLISHED.value: {QuestionStatus.DRAFT.value},
}


def _snapshot(question: Question) -> dict[str, Any]:
    """题目快照（用于版本历史）。"""
    return {
        "stem": question.stem,
        "options": question.options,
        "answer": question.answer,
        "analysis": question.analysis,
        "difficulty": question.difficulty,
        "status": question.status.value
        if hasattr(question.status, "value")
        else str(question.status),
        "source": question.source,
    }


async def list_questions(
    session: AsyncSession,
    *,
    status: str | None = None,
    subject: str | None = None,
    stage: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Question]]:
    """分页检索题库。"""
    query = select(Question)
    if status:
        query = query.where(Question.status == QuestionStatus(status))
    if subject:
        query = query.where(Question.subject == subject)
    if stage:
        query = query.where(Question.stage == stage)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.where(or_(Question.stem.ilike(pattern), Question.analysis.ilike(pattern)))
    total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    items = (
        (
            await session.execute(
                query.order_by(Question.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return total, list(items)


async def _next_version(session: AsyncSession, *, question_id: uuid.UUID) -> int:
    """下一个版本号。"""
    current = await session.scalar(
        select(func.max(QuestionVersion.version)).where(QuestionVersion.question_id == question_id)
    )
    return int(current or 0) + 1


async def _add_version(
    session: AsyncSession, *, question: Question, editor: User, note: str | None
) -> QuestionVersion:
    """写入版本快照。"""
    next_version = await _next_version(session, question_id=question.id)
    version = QuestionVersion(
        question_id=question.id,
        version=next_version,
        editor_id=editor.id,
        change_note=note,
        snapshot=_snapshot(question),
    )
    question.version = next_version
    session.add(version)
    await session.flush()
    return version


async def create_question(
    session: AsyncSession,
    *,
    editor: User,
    subject: str,
    stage: str,
    qtype: str,
    stem: str,
    options: dict[str, str] | None,
    answer: str,
    analysis: str | None,
    difficulty: int,
    source: str,
) -> Question:
    """新建题目（草稿），并落一条初始版本。"""
    question = Question(
        subject=subject,
        stage=stage,
        qtype=qtype,
        stem=stem,
        options=options,
        answer=answer,
        analysis=analysis,
        difficulty=difficulty,
        source=source,
        status=QuestionStatus.DRAFT,
    )
    session.add(question)
    await session.flush()
    await _add_version(session, question=question, editor=editor, note="创建题目")
    return question


async def get_question(session: AsyncSession, *, question_id: uuid.UUID) -> Question:
    """读取题目（含不存在校验）。"""
    question = await session.get(Question, question_id)
    if question is None:
        raise NotFoundError("题目不存在", code="QUESTION_NOT_FOUND")
    return question


async def update_question(
    session: AsyncSession,
    *,
    editor: User,
    question_id: uuid.UUID,
    changes: dict[str, Any],
    change_note: str | None,
) -> Question:
    """编辑题目；内容变化时写入新版本历史。"""
    question = await get_question(session, question_id=question_id)
    meaningful = {
        key: value
        for key, value in changes.items()
        if value is not None and getattr(question, key) != value
    }
    if not meaningful:
        return question
    for key, value in meaningful.items():
        setattr(question, key, value)
    await session.flush()
    await _add_version(session, question=question, editor=editor, note=change_note or "编辑题目")
    return question


async def transition(
    session: AsyncSession, *, editor: User, question_id: uuid.UUID, target: str, note: str | None
) -> Question:
    """审核流流转：draft → review → published（published 可退回 draft 下架重审）。"""
    question = await get_question(session, question_id=question_id)
    current = question.status.value if hasattr(question.status, "value") else str(question.status)
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ConflictError(
            f"不允许从 {current} 流转到 {target}", code="QUESTION_TRANSITION_INVALID"
        )
    question.status = QuestionStatus(target)
    await session.flush()
    await _add_version(
        session, question=question, editor=editor, note=note or f"{current} → {target}"
    )
    return question


async def list_versions(session: AsyncSession, *, question_id: uuid.UUID) -> list[QuestionVersion]:
    """版本历史（倒序）。"""
    result = await session.execute(
        select(QuestionVersion)
        .where(QuestionVersion.question_id == question_id)
        .order_by(QuestionVersion.version.desc())
    )
    return list(result.scalars().all())


async def coverage(session: AsyncSession) -> dict[str, Any]:
    """覆盖率看板：解析覆盖率与状态/学科分布（F-44 验收：≥95%）。"""
    total = int(await session.scalar(select(func.count()).select_from(Question)) or 0)
    with_analysis = int(
        await session.scalar(
            select(func.count())
            .select_from(Question)
            .where(Question.analysis.is_not(None), Question.analysis != "")
        )
        or 0
    )
    status_rows = (
        await session.execute(select(Question.status, func.count()).group_by(Question.status))
    ).all()
    subject_rows = (
        await session.execute(
            select(
                Question.subject,
                func.count().label("total"),
                func.count()
                .filter(Question.analysis.is_not(None), Question.analysis != "")
                .label("with_analysis"),
            ).group_by(Question.subject)
        )
    ).all()
    by_status = {
        (row[0].value if hasattr(row[0], "value") else str(row[0])): int(row[1])
        for row in status_rows
    }
    return {
        "total": total,
        "with_analysis": with_analysis,
        "coverage_rate": round(with_analysis / total, 4) if total else 0.0,
        "published": by_status.get(QuestionStatus.PUBLISHED.value, 0),
        "draft": by_status.get(QuestionStatus.DRAFT.value, 0),
        "review": by_status.get(QuestionStatus.REVIEW.value, 0),
        "by_subject": [
            {
                "subject": row[0],
                "total": int(row[1]),
                "with_analysis": int(row[2]),
                "coverage_rate": round(int(row[2]) / int(row[1]), 4) if int(row[1]) else 0.0,
            }
            for row in subject_rows
        ],
    }


async def knowledge_point_links(
    session: AsyncSession, *, question_id: uuid.UUID
) -> list[QuestionKnowledgePoint]:
    """题目的知识点关联（后台展示用）。"""
    result = await session.execute(
        select(QuestionKnowledgePoint).where(QuestionKnowledgePoint.question_id == question_id)
    )
    return list(result.scalars().all())


__all__ = [
    "coverage",
    "create_question",
    "get_question",
    "knowledge_point_links",
    "list_questions",
    "list_versions",
    "transition",
    "update_question",
]
