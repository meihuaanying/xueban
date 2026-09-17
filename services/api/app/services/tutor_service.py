"""守护型讲解编排（F-11 红线）：提示分层状态机 + 求助层级记录 + SSE 流式。

状态机（不可跳层）：0（未求助）→ 1（思路提示）→ 2（关键步骤）→ 3（完整解答）。
每次请求只能前进一层；跳层返回 TUTOR_LEVEL_SKIPPED（400），超出层级返回 TUTOR_NO_MORE_HINTS（400）。
无辅助测评（F-28）期间会话被 solo_locked 锁定，提示接口直接 403。
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.errors import AppError, NotFoundError, PermissionDeniedError
from app.models import ChatMessage, ChatRole, ChatScene, ChatSession, Question, User
from app.services.exam_service import ensure_no_active_solo
from app.services.llm_client import LlmClient
from app.services.prompts import (
    TUTOR_HISTORY_TEMPLATE,
    TUTOR_LEVEL_INSTRUCTIONS,
    TUTOR_SYSTEM_PROMPT,
    TUTOR_USER_TEMPLATE,
)

MAX_HINT_LEVEL = 3
LEVEL_NAMES: dict[int, str] = {1: "思路提示", 2: "关键步骤", 3: "完整解答"}


def next_hint_level(current: int, requested: int | None = None) -> int:
    """状态机推进：只允许逐层前进（红线，不允许跳层）。"""
    if current >= MAX_HINT_LEVEL:
        raise AppError(
            "已是完整解答；如需重新讲解请开启新的会话",
            code="TUTOR_NO_MORE_HINTS",
            status_code=400,
        )
    target = current + 1
    if requested is not None and requested != target:
        raise AppError(
            f"提示必须按层级递进（当前第 {current} 层，下一层为第 {target} 层）",
            code="TUTOR_LEVEL_SKIPPED",
            status_code=400,
        )
    return target


def build_hint_messages(
    question: Question, level: int, previous_hints: list[str]
) -> list[dict[str, str]]:
    """构造分层讲解提示词（含历史提示，避免重复）。"""
    options_block = ""
    if question.options:
        lines = [f"{key}. {value}" for key, value in question.options.items()]
        options_block = "选项：\n" + "\n".join(lines) + "\n"
    history_block = ""
    if previous_hints:
        numbered = "\n".join(f"{index}. {text}" for index, text in enumerate(previous_hints, 1))
        history_block = TUTOR_HISTORY_TEMPLATE.format(history=numbered)
    instruction = TUTOR_LEVEL_INSTRUCTIONS[level]
    user_content = TUTOR_USER_TEMPLATE.format(
        stem=question.stem,
        qtype=question.qtype.value,
        options_block=options_block,
        level=level,
        history_block=history_block,
        level_instruction=instruction,
    )
    return [
        {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


async def _load_question(session: AsyncSession, question_id: uuid.UUID | None) -> Question:
    if question_id is None:
        raise NotFoundError("讲解会话未关联题目", code="TUTOR_QUESTION_MISSING")
    question = await session.get(Question, question_id)
    if question is None:
        raise NotFoundError("题目不存在", code="QUESTION_NOT_FOUND")
    return question


async def _load_chat_session(
    session: AsyncSession, *, user_id: uuid.UUID, session_id: uuid.UUID
) -> ChatSession:
    chat = await session.get(ChatSession, session_id)
    if chat is None or chat.scene != ChatScene.TUTOR:
        raise NotFoundError("讲解会话不存在", code="TUTOR_SESSION_NOT_FOUND")
    if chat.user_id != user_id:
        raise PermissionDeniedError("无权访问该讲解会话")
    return chat


def ensure_solo_unlocked(chat: ChatSession) -> None:
    """无辅助测评（F-28）期间禁止一切提示。"""
    if chat.solo_locked:
        raise AppError(
            "无辅助测评进行中，暂不可使用提示", code="TUTOR_SOLO_LOCKED", status_code=403
        )


async def start_session(
    session: AsyncSession, *, user: User, question_id: uuid.UUID
) -> tuple[ChatSession, Question]:
    """开启守护型讲解会话（初始层级 0）。"""
    await ensure_no_active_solo(session, user_id=user.id)
    question = await _load_question(session, question_id)
    chat = ChatSession(
        user_id=user.id,
        scene=ChatScene.TUTOR,
        question_id=question.id,
        title=f"讲解：{question.stem[:30]}",
        hint_level=0,
        meta={"prompt_version": "v1"},
    )
    session.add(chat)
    await session.flush()
    return chat, question


async def _previous_hints(session: AsyncSession, chat_id: uuid.UUID) -> list[str]:
    rows = (
        await session.execute(
            select(ChatMessage.content)
            .where(ChatMessage.session_id == chat_id, ChatMessage.role == ChatRole.ASSISTANT)
            .order_by(ChatMessage.created_at)
        )
    ).scalars()
    return list(rows)


@dataclass(slots=True)
class PreparedHint:
    """待执行的提示请求（已通过状态机与权限校验）。"""

    chat_id: uuid.UUID
    question_id: uuid.UUID
    level: int
    level_name: str
    messages: list[dict[str, str]]


async def prepare_hint(
    session: AsyncSession,
    *,
    user: User,
    session_id: uuid.UUID,
    requested_level: int | None = None,
) -> PreparedHint:
    """校验并构造分层提示请求（不产生副作用）。"""
    await ensure_no_active_solo(session, user_id=user.id)
    chat = await _load_chat_session(session, user_id=user.id, session_id=session_id)
    ensure_solo_unlocked(chat)
    target = next_hint_level(chat.hint_level, requested_level)
    question = await _load_question(session, chat.question_id)
    previous = await _previous_hints(session, chat.id)
    return PreparedHint(
        chat_id=chat.id,
        question_id=question.id,
        level=target,
        level_name=LEVEL_NAMES[target],
        messages=build_hint_messages(question, target, previous),
    )


@dataclass(slots=True)
class HintResult:
    """一次提示的结果。"""

    session_id: uuid.UUID
    level: int
    level_name: str
    content: str
    next_level: int | None


async def request_hint(
    session: AsyncSession,
    *,
    user: User,
    session_id: uuid.UUID,
    llm: LlmClient,
    requested_level: int | None = None,
    trace_id: str | None = None,
) -> HintResult:
    """请求一层提示（非流式）。"""
    prepared = await prepare_hint(
        session, user=user, session_id=session_id, requested_level=requested_level
    )
    completion = await llm.complete(
        prepared.messages,
        name=f"tutor.hint.l{prepared.level}",
        trace_id=trace_id,
        temperature=0.6,
    )
    chat = await _load_chat_session(session, user_id=user.id, session_id=session_id)
    session.add(
        ChatMessage(
            session_id=chat.id,
            role=ChatRole.ASSISTANT,
            content=completion.content,
            hint_level=prepared.level,
        )
    )
    chat.hint_level = prepared.level
    chat.last_message_at = utcnow()
    await session.flush()
    return HintResult(
        session_id=chat.id,
        level=prepared.level,
        level_name=prepared.level_name,
        content=completion.content,
        next_level=(
            prepared.level + 1 if prepared.level < MAX_HINT_LEVEL else None
        ),
    )


def sse_event(event: str, data: dict[str, object]) -> str:
    """SSE 事件编码。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_hint(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    prepared: PreparedHint,
    llm: LlmClient,
    trace_id: str | None = None,
) -> AsyncIterator[str]:
    """SSE 事件流：start → delta* → done（自管理会话，适配流式生命周期）。"""
    yield sse_event(
        "start", {"level": prepared.level, "level_name": prepared.level_name}
    )
    collected: list[str] = []
    async for delta in llm.stream_complete(
        prepared.messages,
        name=f"tutor.hint.l{prepared.level}",
        trace_id=trace_id,
        temperature=0.6,
    ):
        collected.append(delta)
        yield sse_event("delta", {"content": delta})

    content = "".join(collected)
    async with sessionmaker() as session:
        chat = await session.get(ChatSession, prepared.chat_id)
        if chat is not None:
            session.add(
                ChatMessage(
                    session_id=chat.id,
                    role=ChatRole.ASSISTANT,
                    content=content,
                    hint_level=prepared.level,
                )
            )
            chat.hint_level = prepared.level
            chat.last_message_at = utcnow()
            await session.commit()
    yield sse_event(
        "done",
        {
            "level": prepared.level,
            "level_name": prepared.level_name,
            "content": content,
        },
    )
