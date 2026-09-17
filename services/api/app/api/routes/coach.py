"""陪练路由（F-32~F-35）：情景口语、面试模拟、学习陪伴（红线）、文书辅助。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import ChatMessage, ChatRole, ChatScene, ChatSession, User
from app.schemas import (
    CoachCorrection,
    CoachTurnRequest,
    CoachTurnResponse,
    WritingAnnotation,
    WritingAssistRequest,
    WritingAssistResponse,
)
from app.services import coach_service

router = APIRouter(prefix="/v1/coach", tags=["coach"])


async def _load_session(
    session: AsyncSession,
    *,
    user: User,
    session_id: uuid.UUID | None,
    scene: ChatScene,
    title: str,
) -> ChatSession:
    """获取或创建陪练会话（复用 chat_sessions 表，跨端共享历史）。"""
    if session_id is not None:
        existing = await session.get(ChatSession, session_id)
        if existing is not None and existing.user_id == user.id:
            return existing
    chat = ChatSession(user_id=user.id, scene=scene, title=title)
    session.add(chat)
    await session.flush()
    return chat


async def _record(
    session: AsyncSession, *, chat: ChatSession, role: ChatRole, content: str
) -> None:
    """记录消息（对话留痕）。"""
    session.add(ChatMessage(session_id=chat.id, role=role, content=content))
    chat.last_message_at = None  # 由 DB 默认时间戳维护；显式留空避免额外查询
    await session.flush()


def _to_response(
    *, chat_id: uuid.UUID, scene: str, reply: coach_service.CoachReply
) -> CoachTurnResponse:
    """服务结果 → 响应契约。"""
    return CoachTurnResponse(
        session_id=chat_id,
        scene=scene,
        reply=reply.reply,
        corrections=[
            CoachCorrection(original=item.original, suggestion=item.suggestion, note=item.note)
            for item in reply.corrections
        ],
        followups=reply.followups,
        crisis=reply.crisis,
        crisis_resources=reply.crisis_resources,
    )


@router.post(
    "/companion",
    response_model=CoachTurnResponse,
    summary="学习陪伴对话（F-34 红线：危机表述必须引导专业求助）",
)
async def companion_turn(
    payload: CoachTurnRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CoachTurnResponse:
    """陪伴对话：先规则层危机识别（0 漏判），再普通陪伴话术。"""
    if coach_service.detect_crisis(payload.message):
        reply = coach_service.crisis_reply()
    else:
        reply = coach_service.companion_reply(message=payload.message)
    chat = await _load_session(
        session,
        user=user,
        session_id=payload.session_id,
        scene=ChatScene.COMPANION,
        title="学习陪伴",
    )
    await _record(session, chat=chat, role=ChatRole.USER, content=payload.message)
    await _record(session, chat=chat, role=ChatRole.ASSISTANT, content=reply.reply)
    await session.commit()
    return _to_response(chat_id=chat.id, scene="companion", reply=reply)


@router.post(
    "/roleplay",
    response_model=CoachTurnResponse,
    summary="AI 口语情景陪练（F-32：≥5 预置场景）",
)
async def roleplay_turn(
    payload: CoachTurnRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CoachTurnResponse:
    """场景角色扮演：纠错标注 + 同场景追问。"""
    scene_key = payload.scene or "restaurant"
    if scene_key not in coach_service.ROLEPLAY_SCENES:
        scene_key = "restaurant"
    chat = await _load_session(
        session,
        user=user,
        session_id=payload.session_id,
        scene=ChatScene.ROLEPLAY,
        title=str(coach_service.ROLEPLAY_SCENES[scene_key]["title"]),
    )
    turn = await _turn_count(session, chat_id=chat.id) + 1
    reply = coach_service.roleplay_reply(scene=scene_key, message=payload.message, turn=turn)
    await _record(session, chat=chat, role=ChatRole.USER, content=payload.message)
    await _record(session, chat=chat, role=ChatRole.ASSISTANT, content=reply.reply)
    await session.commit()
    return _to_response(chat_id=chat.id, scene=scene_key, reply=reply)


@router.post(
    "/scenes",
    summary="口语陪练场景列表（F-32）",
)
async def list_scenes() -> list[dict[str, object]]:
    """预置场景（≥5）。"""
    return [
        {"key": key, "title": spec["title"], "opening": spec["opening"], "focus": spec["focus"]}
        for key, spec in coach_service.ROLEPLAY_SCENES.items()
    ]


@router.post(
    "/interview",
    response_model=CoachTurnResponse,
    summary="面试/复试模拟（F-33：内容/逻辑/表达三维反馈）",
)
async def interview_turn(
    payload: CoachTurnRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CoachTurnResponse:
    """结构化面试反馈（含追问）。"""
    chat = await _load_session(
        session,
        user=user,
        session_id=payload.session_id,
        scene=ChatScene.INTERVIEW,
        title="面试模拟",
    )
    reply = coach_service.interview_feedback(message=payload.message, question=payload.message[:40])
    await _record(session, chat=chat, role=ChatRole.USER, content=payload.message)
    await _record(session, chat=chat, role=ChatRole.ASSISTANT, content=reply.reply)
    await session.commit()
    return _to_response(chat_id=chat.id, scene="interview", reply=reply)


@router.post(
    "/writing",
    response_model=WritingAssistResponse,
    summary="文书与论文辅助（F-35：只改表达不代写观点）",
)
async def writing_assist(
    payload: WritingAssistRequest,
    user: User = Depends(get_current_user),
) -> WritingAssistResponse:
    """返回修改建议 + 批注 + 学术诚信提示（不输出整篇代写）。"""
    reply = coach_service.writing_assist(text=payload.text, kind=payload.kind, goal=payload.goal)
    return WritingAssistResponse(
        suggestions=[
            line.lstrip("· ").strip() for line in reply.reply.splitlines()[1:] if line.strip()
        ],
        annotations=[
            WritingAnnotation(excerpt=item.original, issue=item.suggestion, suggestion=item.note)
            for item in reply.corrections
        ],
        polished_excerpt="（仅提供表达优化建议，不代写内容；请结合批注自行修改）",
        integrity_notice=(
            "学术诚信提示：本工具只帮助改进表达与结构，观点与内容必须由你本人完成；"
            "请遵守所在学校的学术规范。"
        ),
    )


async def _turn_count(session: AsyncSession, *, chat_id: uuid.UUID) -> int:
    """会话轮数（用于陪练提示）。"""
    from sqlalchemy import func, select

    return int(
        await session.scalar(
            select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == chat_id)
        )
        or 0
    )


__all__ = ["router"]
