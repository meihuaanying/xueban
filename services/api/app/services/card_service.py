"""知识卡片（F-38）：对话/错题一键转卡片 + Anki .apkg 导出（genanki）。"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models import KnowledgeCard, User

ANKI_DECK_NAME = "学伴知识卡片"
ANKI_MODEL_ID = 1899273421  # 固定 ID：保证 Anki 复用同一模板
ANKI_DECK_ID = 1899273422


def anki_model() -> object:
    """Anki 卡片模板（正面/背面 + 标签）。"""
    import genanki

    return genanki.Model(
        ANKI_MODEL_ID,
        "学伴问答卡",
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[
            {
                "name": "卡片 1",
                "qfmt": '<div class="front">{{Front}}</div>',
                "afmt": '{{FrontSide}}<hr id="answer"><div class="back">{{Back}}</div>',
            }
        ],
        css=".front,.back{font-family:sans-serif;font-size:18px;line-height:1.6;}",
    )


def build_apkg(cards: list[KnowledgeCard]) -> bytes:
    """用 genanki 生成 .apkg 字节（可由 Anki 导入）。"""
    import genanki

    deck = genanki.Deck(ANKI_DECK_ID, ANKI_DECK_NAME)
    model = anki_model()
    for card in cards:
        note = genanki.Note(
            model=model,
            fields=[card.front, card.back],
            tags=list(card.tags or []) or ["学伴"],
        )
        deck.add_note(note)

    with tempfile.TemporaryDirectory(prefix="anki-") as temp_dir:
        path = Path(temp_dir) / "xueban_cards.apkg"
        genanki.Package(deck).write_to_file(str(path))
        return path.read_bytes()


async def create_card(
    session: AsyncSession,
    *,
    user: User,
    front: str,
    back: str,
    source_type: str,
    source_id: uuid.UUID | None,
    tags: list[str],
) -> KnowledgeCard:
    """创建卡片。"""
    card = KnowledgeCard(
        user_id=user.id,
        front=front,
        back=back,
        source_type=source_type,
        source_id=source_id,
        tags=tags,
    )
    session.add(card)
    await session.flush()
    return card


async def list_cards(session: AsyncSession, *, user: User) -> list[KnowledgeCard]:
    """我的卡片（倒序）。"""
    result = await session.execute(
        select(KnowledgeCard)
        .where(KnowledgeCard.user_id == user.id)
        .order_by(KnowledgeCard.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_card(session: AsyncSession, *, user: User, card_id: uuid.UUID) -> None:
    """删除卡片。"""
    card = await session.get(KnowledgeCard, card_id)
    if card is None or card.user_id != user.id:
        raise NotFoundError("卡片不存在", code="CARD_NOT_FOUND")
    await session.delete(card)
    await session.flush()


async def export_apkg(session: AsyncSession, *, user: User) -> tuple[bytes, int]:
    """导出全部卡片为 .apkg。"""
    cards = await list_cards(session, user=user)
    if not cards:
        raise NotFoundError("还没有卡片可以导出", code="CARD_EMPTY")
    return build_apkg(cards), len(cards)


async def count_cards(session: AsyncSession, *, user: User) -> int:
    """卡片数量。"""
    return int(
        await session.scalar(
            select(func.count()).select_from(KnowledgeCard).where(KnowledgeCard.user_id == user.id)
        )
        or 0
    )


__all__ = [
    "build_apkg",
    "count_cards",
    "create_card",
    "delete_card",
    "export_apkg",
    "list_cards",
]
