"""错题本服务（F-18）：按错因分组列表、一键重练、PDF 导出（含解析）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.models import MistakeBookEntry, Question, User
from app.services.attribution_service import REASON_LABELS

FONT_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "ZCOOLXiaoWei-Regular.ttf"
)


@dataclass(slots=True)
class MistakeEntryView:
    """错题条目视图。"""

    entry: MistakeBookEntry
    question: Question


async def list_mistakes(
    session: AsyncSession,
    *,
    user: User,
    state: str | None = None,
    error_reason: str | None = None,
    limit: int = 50,
) -> tuple[list[MistakeEntryView], list[tuple[str, int]]]:
    """错题列表（未移出）+ 按错因分组的计数。"""
    stmt = (
        select(MistakeBookEntry, Question)
        .join(Question, Question.id == MistakeBookEntry.question_id)
        .where(MistakeBookEntry.user_id == user.id, MistakeBookEntry.removed_at.is_(None))
    )
    if state:
        stmt = stmt.where(MistakeBookEntry.state == state)
    if error_reason:
        stmt = stmt.where(MistakeBookEntry.error_reason == error_reason)
    rows = (
        await session.execute(
            stmt.order_by(MistakeBookEntry.created_at.desc()).limit(limit)
        )
    ).all()
    entries = [MistakeEntryView(entry=row[0], question=row[1]) for row in rows]

    reason_rows = (
        await session.execute(
            select(MistakeBookEntry.error_reason, func.count())
            .where(MistakeBookEntry.user_id == user.id, MistakeBookEntry.removed_at.is_(None))
            .group_by(MistakeBookEntry.error_reason)
        )
    ).all()
    summary = [
        (str(row[0]) if row[0] else "unattributed", int(row[1])) for row in reason_rows
    ]
    return entries, summary


async def repractice_questions(
    session: AsyncSession,
    *,
    user: User,
    count: int = 5,
    error_reason: str | None = None,
) -> list[Question]:
    """一键重练：优先重练次数少、入本早的错题。"""
    stmt = (
        select(Question)
        .join(MistakeBookEntry, MistakeBookEntry.question_id == Question.id)
        .where(MistakeBookEntry.user_id == user.id, MistakeBookEntry.removed_at.is_(None))
    )
    if error_reason:
        stmt = stmt.where(MistakeBookEntry.error_reason == error_reason)
    rows = (
        await session.execute(
            stmt.order_by(
                MistakeBookEntry.review_count.asc(), MistakeBookEntry.created_at.asc()
            ).limit(count)
        )
    ).scalars()
    return list(rows)


def export_mistakes_pdf(entries: list[MistakeEntryView], *, title: str = "学伴错题本") -> bytes:
    """生成错题本 PDF（含题目、作答、正确答案、错因与解析）。"""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_font("CJK", "", str(FONT_PATH))
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("CJK", size=16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("CJK", size=11)
    exported_at = utcnow().strftime("%Y-%m-%d %H:%M")
    pdf.cell(0, 8, f"导出时间：{exported_at}（UTC）", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for index, item in enumerate(entries, start=1):
        pdf.multi_cell(0, 7, f"{index}. {item.question.stem}", new_x="LMARGIN", new_y="NEXT")
        wrong = item.entry.wrong_answer or "（未记录）"
        pdf.multi_cell(
            0,
            7,
            f"我的作答：{wrong}    正确答案：{item.question.answer}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        if item.entry.error_reason:
            label = REASON_LABELS.get(item.entry.error_reason, item.entry.error_reason)
            pdf.multi_cell(0, 7, f"错因：{label}", new_x="LMARGIN", new_y="NEXT")
        if item.question.analysis:
            pdf.multi_cell(0, 7, f"解析：{item.question.analysis}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
    return bytes(pdf.output())


async def build_export_pdf(session: AsyncSession, *, user: User, limit: int = 100) -> bytes:
    """导出当前用户的错题本 PDF。"""
    entries, _ = await list_mistakes(session, user=user, limit=limit)
    return export_mistakes_pdf(entries)


async def mistake_summary(session: AsyncSession, *, user: User) -> dict[str, int]:
    """错题统计（总数 + 已掌握）。"""
    total = await session.scalar(
        select(func.count())
        .select_from(MistakeBookEntry)
        .where(MistakeBookEntry.user_id == user.id, MistakeBookEntry.removed_at.is_(None))
    )
    mastered = await session.scalar(
        select(func.count())
        .select_from(MistakeBookEntry)
        .where(
            MistakeBookEntry.user_id == user.id,
            MistakeBookEntry.removed_at.is_not(None),
        )
    )
    return {"active": int(total or 0), "mastered": int(mastered or 0)}


def reason_label(reason: str | None) -> str | None:
    """错因英文码 → 中文标签。"""
    if reason is None:
        return None
    if reason == "unattributed":
        return "未归因"
    return REASON_LABELS.get(reason, reason)


__all__ = [
    "MistakeEntryView",
    "build_export_pdf",
    "export_mistakes_pdf",
    "list_mistakes",
    "mistake_summary",
    "reason_label",
    "repractice_questions",
]
