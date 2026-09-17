"""OCR 流程服务（F-36 拍照搜题 / F-04 手写步骤诊断）：识别 → 匹配/定位 → 引导。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import KnowledgePoint, Question, QuestionKnowledgePoint, QuestionStatus
from app.services.library_service import _tokens

STEP_SPLIT = re.compile(r"[\n；;。]+")
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

DEGRADATION_HINT = "识别置信度不足或 OCR 服务不可用：请手动确认/输入题目文本后继续（降级路径）。"

TUTOR_ENTRY = "/v1/tutor/session"


@dataclass(slots=True)
class RecognizeResult:
    """OCR 识别结果。"""

    text: str
    confidence: float
    degraded: bool
    hint: str | None = None


async def recognize(
    *,
    settings: Settings,
    image_key: str | None,
    ocr_text: str | None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> RecognizeResult:
    """识别图片文本：优先使用人工确认文本；否则调用 OCR 服务；失败走降级路径。"""
    if ocr_text and ocr_text.strip():
        return RecognizeResult(text=ocr_text.strip(), confidence=1.0, degraded=False)

    if settings.ocr_provider != "service" or not image_key:
        return RecognizeResult(text="", confidence=0.0, degraded=True, hint=DEGRADATION_HINT)

    try:
        async with httpx.AsyncClient(
            base_url=settings.ocr_base_url.rstrip("/"),
            timeout=settings.ocr_timeout_seconds,
            transport=transport,
        ) as client:
            response = await client.post("/v1/ocr", json={"image_key": image_key})
        if response.status_code >= 400:
            return RecognizeResult(text="", confidence=0.0, degraded=True, hint=DEGRADATION_HINT)
        payload = response.json()
        text = str(payload.get("text", "")).strip()
        confidence = float(payload.get("confidence", 0.0))
        if not text:
            return RecognizeResult(
                text="", confidence=confidence, degraded=True, hint=DEGRADATION_HINT
            )
        return RecognizeResult(text=text, confidence=confidence, degraded=False)
    except (httpx.HTTPError, ValueError):
        return RecognizeResult(text="", confidence=0.0, degraded=True, hint=DEGRADATION_HINT)


@dataclass(slots=True)
class PhotoSearchResult:
    """拍照搜题结果（不含答案）。"""

    recognized_text: str
    confidence: float
    degraded: bool
    degradation_hint: str | None
    match_found: bool
    question_id: uuid.UUID | None
    knowledge_points: list[str]


async def photo_search(
    session: AsyncSession,
    *,
    settings: Settings,
    text: str,
    subject: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    image_key: str | None = None,
) -> PhotoSearchResult:
    """识别文本并在题库中匹配原题；只返回引导入口，不返回答案。"""
    recognized = await recognize(
        settings=settings, image_key=image_key, ocr_text=text or None, transport=transport
    )
    if recognized.degraded:
        return PhotoSearchResult(
            recognized_text=recognized.text,
            confidence=recognized.confidence,
            degraded=True,
            degradation_hint=recognized.hint,
            match_found=False,
            question_id=None,
            knowledge_points=[],
        )

    query = select(Question).where(Question.status == QuestionStatus.PUBLISHED)
    if subject:
        query = query.where(Question.subject == subject)
    candidates = (await session.execute(query.limit(200))).scalars().all()

    tokens = _tokens(recognized.text)
    best: tuple[float, Question] | None = None
    for question in candidates:
        overlap = len(tokens & _tokens(question.stem)) / max(len(tokens), 1)
        if best is None or overlap > best[0]:
            best = (overlap, question)
    if best is None or best[0] < 0.5:
        return PhotoSearchResult(
            recognized_text=recognized.text,
            confidence=recognized.confidence,
            degraded=False,
            degradation_hint=None,
            match_found=False,
            question_id=None,
            knowledge_points=[],
        )

    question = best[1]
    point_rows = (
        (
            await session.execute(
                select(KnowledgePoint.name)
                .join(
                    QuestionKnowledgePoint,
                    QuestionKnowledgePoint.knowledge_point_id == KnowledgePoint.id,
                )
                .where(QuestionKnowledgePoint.question_id == question.id)
            )
        )
        .scalars()
        .all()
    )
    return PhotoSearchResult(
        recognized_text=recognized.text,
        confidence=recognized.confidence,
        degraded=False,
        degradation_hint=None,
        match_found=True,
        question_id=question.id,
        knowledge_points=list(point_rows),
    )


@dataclass(slots=True)
class HandwritingStep:
    """手写步骤。"""

    index: int
    content: str
    is_error: bool
    note: str


@dataclass(slots=True)
class HandwritingResult:
    """手写诊断结果。"""

    steps: list[HandwritingStep]
    first_error_step: int | None
    confidence: float
    degraded: bool
    degradation_hint: str | None
    advice: str


def _step_similarity(step: str, reference: str) -> float:
    """步骤相似度：数值一致优先（数学步骤对数字敏感），叠加文字 token 重合。"""
    step_norm = re.sub(r"\s+", "", step)
    ref_norm = re.sub(r"\s+", "", reference)
    if not step_norm or not ref_norm:
        return 0.0
    step_tokens = _tokens(step)
    reference_tokens = _tokens(reference)
    token_score = (
        len(step_tokens & reference_tokens) / len(reference_tokens) if reference_tokens else 0.0
    )
    step_numbers = set(NUMBER.findall(step))
    ref_numbers = set(NUMBER.findall(reference))
    if not reference_tokens:
        # 纯数值/符号步骤：要求归一化后完全一致（数学步骤对数字零容忍）
        return 1.0 if step_norm == ref_norm else 0.0
    if ref_numbers:
        number_factor = len(step_numbers & ref_numbers) / len(ref_numbers)
    else:
        number_factor = 1.0 if step_norm == ref_norm else 0.0
    return round(0.4 * token_score + 0.6 * number_factor, 4)


async def diagnose_handwriting(
    *,
    settings: Settings,
    image_key: str | None,
    ocr_text: str | None,
    reference_solution: str | None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> HandwritingResult:
    """定位手写解答中第一次出错的步骤（F-04）。"""
    recognized = await recognize(
        settings=settings, image_key=image_key, ocr_text=ocr_text, transport=transport
    )
    if recognized.degraded or not reference_solution:
        return HandwritingResult(
            steps=[],
            first_error_step=None,
            confidence=recognized.confidence,
            degraded=True,
            degradation_hint=recognized.hint or "缺少参考解答：请先选择题目或确认文本。",
            advice="已切换为人工确认模式：请核对识别文本或手动输入你的解答步骤。",
        )

    raw_steps = [step.strip() for step in STEP_SPLIT.split(recognized.text) if step.strip()]
    reference_steps = [
        step.strip() for step in STEP_SPLIT.split(reference_solution) if step.strip()
    ]
    steps: list[HandwritingStep] = []
    first_error: int | None = None
    for index, content in enumerate(raw_steps):
        reference = reference_steps[index] if index < len(reference_steps) else ""
        score = _step_similarity(content, reference) if reference else 0.0
        is_error = bool(reference) and score < 0.5
        if is_error and first_error is None:
            first_error = index
        note = "与参考步骤一致" if not is_error else "数值/结论与参考步骤不一致，建议回看该步依据"
        if not reference:
            note = "超出参考步骤数量，请确认是否多写了步骤"
            is_error = True
            if first_error is None:
                first_error = index
        steps.append(HandwritingStep(index=index, content=content, is_error=is_error, note=note))

    if first_error is None:
        advice = "步骤与参考解答一致：可以进入变式练习检验迁移。"
    else:
        advice = (
            f"第 {first_error + 1} 步开始出现偏差："
            "建议先回到该步的定义/公式，再用守护型讲解逐层提示。"
        )

    return HandwritingResult(
        steps=steps,
        first_error_step=first_error,
        confidence=recognized.confidence,
        degraded=False,
        degradation_hint=None,
        advice=advice,
    )


__all__ = [
    "DEGRADATION_HINT",
    "TUTOR_ENTRY",
    "HandwritingResult",
    "HandwritingStep",
    "PhotoSearchResult",
    "RecognizeResult",
    "diagnose_handwriting",
    "photo_search",
    "recognize",
]
