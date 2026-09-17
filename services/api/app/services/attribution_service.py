"""错因自动归因（F-02）：LLM 归因，结果限定五类枚举。"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import LlmError, NotFoundError, PermissionDeniedError
from app.models import MistakeBookEntry, Question, User
from app.services.llm_client import LlmClient
from app.services.prompts import ATTRIBUTION_SYSTEM_PROMPT, ATTRIBUTION_USER_TEMPLATE

ATTRIBUTION_REASONS: frozenset[str] = frozenset(
    {"concept", "reading", "computation", "method", "transfer"}
)

REASON_LABELS: dict[str, str] = {
    "concept": "概念不清",
    "reading": "审题偏差",
    "computation": "计算失误",
    "method": "方法缺失",
    "transfer": "迁移薄弱",
}


@dataclass(slots=True)
class AttributionResult:
    """归因结果。"""

    entry_id: uuid.UUID
    reason: str
    reason_label: str
    confidence: float
    explanation: str


def parse_attribution(raw: str) -> tuple[str, float, str]:
    """解析 LLM 输出：容忍代码块与多余文字，枚举严格校验。"""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence is not None:
        text = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.S)
        if brace is not None:
            text = brace.group(0)
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise LlmError("归因结果解析失败", code="ATTRIBUTION_BAD_OUTPUT", status_code=502) from exc
    if not isinstance(payload, dict):
        raise LlmError("归因结果结构异常", code="ATTRIBUTION_BAD_OUTPUT", status_code=502)
    reason = str(payload.get("reason", "")).strip().lower()
    if reason not in ATTRIBUTION_REASONS:
        raise LlmError(
            f"归因结果不在五类枚举内：{reason or '空'}",
            code="ATTRIBUTION_BAD_OUTPUT",
            status_code=502,
        )
    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(max(confidence, 0.0), 1.0)
    explanation = str(payload.get("explanation", "")).strip()[:200]
    return reason, confidence, explanation


async def attribute_mistake(
    session: AsyncSession,
    *,
    user: User,
    entry_id: uuid.UUID,
    llm: LlmClient,
    trace_id: str | None = None,
) -> AttributionResult:
    """对一条错题执行归因并写回错题本。"""
    entry = await session.get(MistakeBookEntry, entry_id)
    if entry is None:
        raise NotFoundError("错题记录不存在", code="MISTAKE_NOT_FOUND")
    if entry.user_id != user.id:
        raise PermissionDeniedError("无权访问该错题")
    question = await session.get(Question, entry.question_id)
    if question is None:
        raise NotFoundError("题目不存在", code="QUESTION_NOT_FOUND")

    messages = [
        {"role": "system", "content": ATTRIBUTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": ATTRIBUTION_USER_TEMPLATE.format(
                stem=question.stem,
                qtype=question.qtype.value,
                answer=question.answer,
                analysis=question.analysis or "（无）",
                wrong_answer=entry.wrong_answer or "（未记录）",
            ),
        },
    ]
    completion = await llm.complete(
        messages, name="mistake.attribute", trace_id=trace_id, temperature=0.0
    )
    reason, confidence, explanation = parse_attribution(completion.content)
    entry.error_reason = reason
    await session.flush()
    return AttributionResult(
        entry_id=entry.id,
        reason=reason,
        reason_label=REASON_LABELS[reason],
        confidence=confidence,
        explanation=explanation,
    )
