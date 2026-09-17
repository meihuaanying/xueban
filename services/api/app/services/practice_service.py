"""练习服务（F-10/F-17/F-18 作答闭环；FSRS 见 fsrs_service）。

- F-10 动态难度：accuracy_of + choose_next_difficulty（阈值升降档）
- F-17 智能出题：薄弱知识点占比 ≥60%，近 7 天去重
- F-18 错题自动归集与重练移出
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.errors import NotFoundError
from app.models import (
    KnowledgePoint,
    MistakeBookEntry,
    MistakeState,
    PracticeRecord,
    PracticeSource,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
    User,
)
from app.services import fsrs_service, mastery_service
from app.services.diagnosis_service import check_answer

UP_THRESHOLD = 0.85
DOWN_THRESHOLD = 0.5
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5

WEAK_THRESHOLD = 0.6
WEAK_RATIO = 0.6
DEDUP_DAYS = 7
RECENT_WINDOW = 5


def accuracy_of(results: list[bool]) -> float:
    """近期正确率（空列表按 1.0 处理，避免误降档）。"""
    if not results:
        return 1.0
    return sum(1 for item in results if item) / len(results)


def choose_next_difficulty(
    current: int,
    recent_accuracy: float,
    *,
    up_threshold: float = UP_THRESHOLD,
    down_threshold: float = DOWN_THRESHOLD,
) -> int:
    """动态难度：正确率达阈值升档、低于阈值降档，其余保持（F-10）。"""
    if recent_accuracy >= up_threshold:
        return min(MAX_DIFFICULTY, current + 1)
    if recent_accuracy <= down_threshold:
        return max(MIN_DIFFICULTY, current - 1)
    return current


@dataclass(slots=True)
class PracticeQuestionItem:
    """出题结果条目。"""

    question: Question
    knowledge_point_ids: list[uuid.UUID]
    reason: str  # weak / explore


@dataclass(slots=True)
class PracticeSet:
    """一次生成的练习集。"""

    items: list[PracticeQuestionItem]
    weak_count: int

    @property
    def weak_ratio(self) -> float:
        """薄弱知识点占比。"""
        if not self.items:
            return 0.0
        return round(self.weak_count / len(self.items), 4)


@dataclass(slots=True)
class PracticeAnswerResult:
    """一次练习作答的结果。"""

    is_correct: bool
    correct_answer: str
    next_difficulty: int
    mistake_collected: bool
    mistake_removed: bool
    card_due_at: datetime | None
    explanation: str | None
    duplicate: bool = False


async def _recent_question_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    """近 7 天做过的题（去重分界）。"""
    cutoff = utcnow() - timedelta(days=DEDUP_DAYS)
    rows = await session.execute(
        select(PracticeRecord.question_id).where(
            PracticeRecord.user_id == user_id, PracticeRecord.created_at >= cutoff
        )
    )
    return set(rows.scalars())


async def _subject_knowledge_points(
    session: AsyncSession, *, subject: str, stage: str | None
) -> dict[uuid.UUID, str]:
    stmt = (
        select(KnowledgePoint.id, KnowledgePoint.name)
        .join(
            QuestionKnowledgePoint,
            QuestionKnowledgePoint.knowledge_point_id == KnowledgePoint.id,
        )
        .join(Question, Question.id == QuestionKnowledgePoint.question_id)
        .where(Question.subject == subject, Question.status == QuestionStatus.PUBLISHED)
        .distinct()
    )
    if stage:
        stmt = stmt.where(Question.stage == stage)
    rows = (await session.execute(stmt)).all()
    return {row[0]: row[1] for row in rows}


async def _pick_questions(
    session: AsyncSession,
    *,
    subject: str,
    stage: str | None,
    kp_ids: list[uuid.UUID],
    difficulty: int | None,
    exclude_ids: set[uuid.UUID],
    limit: int,
    reason: str,
) -> list[PracticeQuestionItem]:
    """按「难度贴近 + 教学顺序」选题。"""
    if not kp_ids or limit <= 0:
        return []
    target_difficulty = difficulty if difficulty is not None else 1
    distance = func.abs(Question.difficulty - target_difficulty)
    stmt = (
        select(Question, QuestionKnowledgePoint.knowledge_point_id)
        .join(QuestionKnowledgePoint, QuestionKnowledgePoint.question_id == Question.id)
        .where(
            Question.subject == subject,
            Question.status == QuestionStatus.PUBLISHED,
            QuestionKnowledgePoint.knowledge_point_id.in_(kp_ids),
        )
        .order_by(distance, Question.created_at)
    )
    if stage:
        stmt = stmt.where(Question.stage == stage)
    rows = (await session.execute(stmt)).all()

    grouped: dict[uuid.UUID, PracticeQuestionItem] = {}
    for question, kp_id in rows:
        if question.id in exclude_ids:
            continue
        item = grouped.get(question.id)
        if item is None:
            item = PracticeQuestionItem(
                question=question, knowledge_point_ids=[], reason=reason
            )
            grouped[question.id] = item
        item.knowledge_point_ids.append(kp_id)
    return list(grouped.values())[:limit]


async def generate_practice(
    session: AsyncSession,
    *,
    user: User,
    subject: str = "math",
    stage: str | None = None,
    count: int = 5,
    knowledge_point_ids: list[uuid.UUID] | None = None,
) -> PracticeSet:
    """智能出题（F-17）：薄弱知识点 ≥60% + 近 7 天去重。"""
    recent = await _recent_question_ids(session, user.id)
    overview = await mastery_service.get_mastery_overview(session, user_id=user.id, subject=subject)
    scope = await _subject_knowledge_points(session, subject=subject, stage=stage)

    weak_ids = [point.knowledge_point_id for point in overview if point.mastery < WEAK_THRESHOLD]
    if knowledge_point_ids:
        requested = [item for item in knowledge_point_ids if item in scope]
        weak_ids = [item for item in weak_ids if item in requested] or requested
    if not weak_ids:
        weakest = [
            point.knowledge_point_id
            for point in overview[:3]
            if point.knowledge_point_id in scope
        ]
        weak_ids = weakest or list(scope)[: min(len(scope), 5)]
    weak_ids = [item for item in weak_ids if item in scope]
    explore_ids = [item for item in scope if item not in set(weak_ids)]

    weak_target = min(count, max(1, -(-count * 3 // 5)))  # ceil(count * 0.6)
    chosen: list[PracticeQuestionItem] = []
    chosen += await _pick_questions(
        session,
        subject=subject,
        stage=stage,
        kp_ids=weak_ids,
        difficulty=None,
        exclude_ids=recent | {item.question.id for item in chosen},
        limit=weak_target,
        reason="weak",
    )
    chosen += await _pick_questions(
        session,
        subject=subject,
        stage=stage,
        kp_ids=explore_ids,
        difficulty=3,
        exclude_ids=recent | {item.question.id for item in chosen},
        limit=count - len(chosen),
        reason="explore",
    )
    if len(chosen) < count:
        chosen += await _pick_questions(
            session,
            subject=subject,
            stage=stage,
            kp_ids=[*weak_ids, *explore_ids],
            difficulty=None,
            exclude_ids=recent | {item.question.id for item in chosen},
            limit=count - len(chosen),
            reason="explore",
        )
    return PracticeSet(
        items=chosen, weak_count=sum(1 for item in chosen if item.reason == "weak")
    )


async def _recent_accuracy(session: AsyncSession, user_id: uuid.UUID) -> float:
    rows = (
        await session.execute(
            select(PracticeRecord.is_correct)
            .where(PracticeRecord.user_id == user_id)
            .order_by(PracticeRecord.created_at.desc())
            .limit(RECENT_WINDOW)
        )
    ).scalars()
    return accuracy_of([bool(item) for item in rows])


async def answer_question(
    session: AsyncSession,
    *,
    user: User,
    question_id: uuid.UUID,
    user_answer: str,
    source: PracticeSource = PracticeSource.PRACTICE,
    client_event_id: str | None = None,
) -> PracticeAnswerResult:
    """作答闭环：判定 → 画像/FSRS → 错题本归集或重练移出 → 动态难度。

    `client_event_id` 用于离线补齐的幂等重放：同一事件重复提交只计数一次。
    """
    question = await session.get(Question, question_id)
    if question is None or question.status != QuestionStatus.PUBLISHED:
        raise NotFoundError("题目不存在", code="QUESTION_NOT_FOUND")

    if client_event_id:
        existing = (
            await session.execute(
                select(PracticeRecord).where(
                    PracticeRecord.user_id == user.id,
                    PracticeRecord.client_event_id == client_event_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return PracticeAnswerResult(
                is_correct=existing.is_correct,
                correct_answer=question.answer,
                next_difficulty=question.difficulty,
                mistake_collected=False,
                mistake_removed=False,
                card_due_at=None,
                explanation=question.analysis,
                duplicate=True,
            )

    is_correct = check_answer(question, user_answer)
    session.add(
        PracticeRecord(
            user_id=user.id,
            question_id=question.id,
            source=source,
            is_correct=is_correct,
            difficulty=question.difficulty,
            user_answer=user_answer,
            client_event_id=client_event_id,
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

    card = await fsrs_service.update_card_for_answer(
        session, user_id=user.id, question_id=question.id, correct=is_correct
    )

    mistake_collected = False
    mistake_removed = False
    entry = (
        await session.execute(
            select(MistakeBookEntry).where(
                MistakeBookEntry.user_id == user.id,
                MistakeBookEntry.question_id == question.id,
            )
        )
    ).scalar_one_or_none()
    if not is_correct:
        if entry is None:
            session.add(
                MistakeBookEntry(
                    user_id=user.id,
                    question_id=question.id,
                    wrong_answer=user_answer,
                    source=source.value,
                )
            )
        else:
            entry.wrong_answer = user_answer
            entry.removed_at = None
            entry.review_count += 1
        mistake_collected = True
    elif source == PracticeSource.REPRACTICE and entry is not None and entry.removed_at is None:
        entry.removed_at = utcnow()
        entry.state = MistakeState.MASTERED
        mistake_removed = True

    await session.flush()
    recent_accuracy = await _recent_accuracy(session, user.id)
    next_difficulty = choose_next_difficulty(question.difficulty, recent_accuracy)
    return PracticeAnswerResult(
        is_correct=is_correct,
        correct_answer=question.answer,
        next_difficulty=next_difficulty,
        mistake_collected=mistake_collected,
        mistake_removed=mistake_removed,
        card_due_at=card.due_at,
        explanation=question.analysis,
        duplicate=False,
    )
