"""工具路由（F-36~F-38）：拍照搜题、教材文档问答、知识卡片与 Anki 导出。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.config import settings
from app.models import User
from app.schemas import (
    CardCreateRequest,
    CardListResponse,
    CardOut,
    LibraryAskRequest,
    LibraryAskResponse,
    LibraryCitation,
    LibraryDocOut,
    LibrarySelfTestResponse,
    PhotoSearchRequest,
    PhotoSearchResponse,
)
from app.services import card_service, library_service, ocr_client
from app.services.embeddings import get_embedding_provider
from app.services.ingest_service import IngestService

router = APIRouter(prefix="/v1", tags=["tools"])


# ------------------------------- F-36 拍照搜题 -------------------------------


@router.post(
    "/tools/photo-search",
    response_model=PhotoSearchResponse,
    summary="拍照搜题（F-36 红线：只返回引导入口，答案藏在三层提示之后）",
)
async def photo_search(
    payload: PhotoSearchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PhotoSearchResponse:
    """识别文本 → 题库匹配 → 返回守护型讲解入口（绝不返回答案）。"""
    result = await ocr_client.photo_search(
        session,
        settings=settings,
        text=payload.ocr_text or "",
        subject=payload.subject,
        image_key=payload.image_key,
    )
    return PhotoSearchResponse(
        recognized_text=result.recognized_text,
        confidence=result.confidence,
        degraded=result.degraded,
        degradation_hint=result.degradation_hint,
        match_found=result.match_found,
        question_id=result.question_id,
        tutor_entry=ocr_client.TUTOR_ENTRY,
        knowledge_points=result.knowledge_points,
    )


# ------------------------------- F-37 文档问答 -------------------------------


def _ingest_service() -> IngestService:
    """构造入库服务（使用当前 embedding 供应商）。"""
    return IngestService(get_embedding_provider(settings))


@router.post(
    "/library/docs",
    response_model=LibraryDocOut,
    summary="上传教材/讲义（F-37：PDF 解析入库）",
)
async def upload_document(
    request: Request,
    title: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LibraryDocOut:
    """PDF 上传 → 解析 → 分块 → 向量化入库。"""
    data = await file.read()
    document = await library_service.create_document(
        session,
        user=user,
        ingest=_ingest_service(),
        title=title,
        filename=file.filename or "document.pdf",
        data=data,
    )
    await session.commit()
    return LibraryDocOut.model_validate(document)


@router.get(
    "/library/docs",
    response_model=list[LibraryDocOut],
    summary="我的文档列表（F-37）",
)
async def list_documents(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LibraryDocOut]:
    """仅本人文档。"""
    documents = await library_service.list_documents(session, user=user)
    return [LibraryDocOut.model_validate(item) for item in documents]


@router.post(
    "/library/{document_id}/ask",
    response_model=LibraryAskResponse,
    summary="文档提问（F-37：回答带页码引用）",
)
async def ask_document(
    document_id: uuid.UUID,
    payload: LibraryAskRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LibraryAskResponse:
    """私有知识库问答（LLM 不可用时走抽取式回退，引用不缺失）。"""
    result = await library_service.ask(
        session,
        user=user,
        document_id=document_id,
        question=payload.question,
        top_k=payload.top_k,
    )
    return LibraryAskResponse(
        answer=result.answer,
        citations=[
            LibraryCitation(page=item.page, chunk_id=item.chunk_id, excerpt=item.excerpt)
            for item in result.citations
        ],
    )


@router.get(
    "/library/{document_id}/self-test",
    response_model=LibrarySelfTestResponse,
    summary="文档自测题（F-37）",
)
async def document_self_test(
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LibrarySelfTestResponse:
    """基于文档生成自测题（可作答批改）。"""
    questions = await library_service.self_test(session, user=user, document_id=document_id)
    return LibrarySelfTestResponse(
        questions=[
            {"question": item.question, "answer": item.answer, "page": item.page}
            for item in questions
        ]
    )


# ------------------------------- F-38 知识卡片 -------------------------------


@router.post("/cards", response_model=CardOut, status_code=201, summary="创建知识卡片（F-38）")
async def create_card(
    payload: CardCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CardOut:
    """对话/错题/手动创建卡片。"""
    card = await card_service.create_card(
        session,
        user=user,
        front=payload.front,
        back=payload.back,
        source_type=payload.source_type,
        source_id=payload.source_id,
        tags=payload.tags,
    )
    await session.commit()
    return CardOut.model_validate(card)


@router.get("/cards", response_model=CardListResponse, summary="我的知识卡片（F-38）")
async def list_cards(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CardListResponse:
    """卡片列表。"""
    cards = await card_service.list_cards(session, user=user)
    return CardListResponse(
        cards=[CardOut.model_validate(item) for item in cards], total=len(cards)
    )


@router.delete("/cards/{card_id}", status_code=204, summary="删除知识卡片（F-38）")
async def delete_card(
    card_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """删除本人卡片。"""
    await card_service.delete_card(session, user=user, card_id=card_id)
    await session.commit()
    return Response(status_code=204)


@router.get(
    "/cards/export.apkg",
    summary="导出 Anki 卡片包（F-38：.apkg，可被 Anki 导入）",
    response_class=Response,
)
async def export_cards(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """genanki 生成 .apkg（含固定 deck/model id，便于增量导入）。"""
    data, count = await card_service.export_apkg(session, user=user)
    return Response(
        content=data,
        media_type="application/apkg",
        headers={
            "Content-Disposition": 'attachment; filename="xueban_cards.apkg"',
            "X-Card-Count": str(count),
        },
    )
