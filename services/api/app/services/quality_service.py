"""AI 质量巡检（F-45）：抽样题目做 SymPy + 判定双通道校验，超阈值触发告警。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import utcnow
from app.models import InspectionReport, Question, QuestionStatus, SafetyEvent
from app.services import alert_service
from app.services.math_verify import verify_contains_answer

WRONG_RATE_THRESHOLD = 0.03
DEFAULT_SAMPLE_SIZE = 50


@dataclass(slots=True)
class SampleCheck:
    """单题校验结果。"""

    question_id: uuid.UUID
    flagged: bool
    reason: str | None = None
    sympy_checked: bool = False
    sympy_passed: bool = False


def check_question(question: Question) -> SampleCheck:
    """单题双通道校验：SymPy（数学等价）+ 规则判定（解析覆盖答案）。"""
    analysis = question.analysis or ""
    answer = question.answer or ""
    if not analysis.strip():
        return SampleCheck(question.id, flagged=True, reason="missing_analysis")

    sympy_checked = False
    sympy_passed = False
    # SymPy 通道仅适用于非选择题（答案为可解析的数学表达式）；
    # 选择题答案通常为选项字母，走下方「解析必须引用正确选项」规则通道。
    if question.subject == "math" and not question.options:
        sympy_checked = True
        sympy_passed = verify_contains_answer(analysis, answer)
        if not sympy_passed and len(answer) <= 12:
            # 数学题答案为短表达式时，解析必须包含该答案，否则视为疑似错解
            return SampleCheck(
                question.id,
                flagged=True,
                reason="sympy_answer_mismatch",
                sympy_checked=True,
                sympy_passed=False,
            )

    # 规则判定：选择题解析需指出正确选项；非选择题解析需出现答案文本
    if question.options:
        marker_ok = f"正确选项为 {answer}" in analysis or f"选项 {answer}" in analysis
    else:
        marker_ok = answer in analysis
    if not marker_ok:
        return SampleCheck(
            question.id,
            flagged=True,
            reason="answer_not_referenced",
            sympy_checked=sympy_checked,
            sympy_passed=sympy_passed,
        )
    return SampleCheck(
        question.id, flagged=False, sympy_checked=sympy_checked, sympy_passed=sympy_passed
    )


async def _redline_hits(session: AsyncSession, *, since: date) -> int:
    """近 24h/当日的安全拦截次数（红线命中口径之一）。"""
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=0)
    total = await session.scalar(
        select(func.count())
        .select_from(SafetyEvent)
        .where(SafetyEvent.action == "blocked", SafetyEvent.created_at >= start)
    )
    return int(total or 0)


async def run_inspection(
    session: AsyncSession,
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    threshold: float = WRONG_RATE_THRESHOLD,
    webhook_url: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> InspectionReport:
    """执行一次巡检：抽样 → 双通道校验 → 入库 → 超阈值告警。"""
    questions = (
        (
            await session.execute(
                select(Question)
                .where(Question.status == QuestionStatus.PUBLISHED)
                .order_by(func.random())
                .limit(sample_size)
            )
        )
        .scalars()
        .all()
    )

    checks = [check_question(question) for question in questions]
    flagged = [check for check in checks if check.flagged]
    total = len(checks)
    wrong_rate = round(len(flagged) / total, 4) if total else 0.0
    sympy_checked = sum(1 for check in checks if check.sympy_checked)
    sympy_passed = sum(1 for check in checks if check.sympy_passed)
    redline_hits = await _redline_hits(session, since=utcnow().date())

    report = InspectionReport(
        run_date=utcnow().date(),
        sample_size=total,
        flagged_count=len(flagged),
        wrong_rate=wrong_rate,
        sympy_checked=sympy_checked,
        sympy_passed=sympy_passed,
        redline_hits=redline_hits,
        detail={
            "flagged": [
                {"question_id": str(check.question_id), "reason": check.reason}
                for check in flagged[:20]
            ],
            "threshold": threshold,
        },
    )
    session.add(report)
    await session.flush()

    if total > 0 and wrong_rate > threshold:
        record = await alert_service.send_alert(
            session,
            kind="quality.wrong_rate",
            payload={
                "run_date": str(report.run_date),
                "sample_size": total,
                "wrong_rate": wrong_rate,
                "threshold": threshold,
                "report_id": str(report.id),
            },
            webhook_url=webhook_url,
            transport=transport,
        )
        report.alerted = record.status in ("sent", "skipped")
    await session.flush()
    return report


async def list_reports(session: AsyncSession, *, limit: int = 20) -> list[InspectionReport]:
    """最近巡检报告。"""
    result = await session.execute(
        select(InspectionReport).order_by(InspectionReport.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


@dataclass(slots=True)
class DailyInspectionResult:
    """定时巡检结果。"""

    reports: list[str] = field(default_factory=list)


async def run_daily_inspection(sessionmaker: Any) -> int:
    """arq 每日任务：按 50 条抽样巡检并告警。"""
    async with sessionmaker() as session:
        report = await run_inspection(
            session,
            sample_size=settings.inspection_sample_size,
            threshold=settings.inspection_threshold,
        )
        await session.commit()
        return report.sample_size
