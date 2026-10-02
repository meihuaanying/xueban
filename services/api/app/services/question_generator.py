"""题目生成器（P1 / §6.2 第一段：LLM 批量出题）。

职责边界：
- 只负责「按知识点批量出题」并把 LLM 返回的 JSON 收敛成 `GeneratedQuestion`；
- **不做校验**（校验在 `question_verify.py`）、**不去重**（在 `question_dedupe.py`）、
  **不写库**（在 `question_pipeline.py`），保证每段可单独测试与断点续跑。

限速与断点：
- 每次请求出 `settings.content_batch_size` 道，Go 网关按请求计费，批量越大越省额度；
- 会话 ID 绑定到知识点（`bind_session`），同一知识点重试时能命中网关提示缓存；
- 429/5xx 的退避重试由 `LlmClient` 负责，本层只负责业务级重试（JSON 不合法时重问）。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.data.curriculum import KnowledgePoint
from app.data.curriculum import grade_name as _grade_name
from app.data.curriculum import subject_name as _subject_name
from app.errors import LlmError
from app.services.llm_client import LlmClient
from app.services.prompts import (
    QUESTION_GEN_SYSTEM_PROMPT,
    QUESTION_GEN_USER_TEMPLATE,
)

logger = logging.getLogger("xueban.content.gen")

# 允许的题型：与 Question.qtype 的取值对齐
ALLOWED_QTYPES = frozenset({"choice", "judge", "fill", "match", "oral", "pick_hanzi"})

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class QuestionGenerationError(Exception):
    """出题失败（连续重试仍拿不到合法结构）。"""


@dataclass(frozen=True, slots=True)
class GeneratedQuestion:
    """一道待验证的题目。"""

    qtype: str
    stem: str
    options: dict[str, str] | None
    answer: str
    analysis: str
    hint1: str
    hint2: str
    hint3: str
    difficulty: int
    knowledge_point_id: str

    def to_public_dict(self) -> dict[str, Any]:
        """给 judge / 去重用的只读视图。"""
        return {
            "qtype": self.qtype,
            "stem": self.stem,
            "options": self.options,
            "answer": self.answer,
            "analysis": self.analysis,
            "hint1": self.hint1,
            "hint2": self.hint2,
            "hint3": self.hint3,
            "difficulty": self.difficulty,
            "knowledge_point_id": self.knowledge_point_id,
        }


@dataclass(slots=True)
class GenerationReport:
    """一次出题的统计，便于断点续跑与后续简报。"""

    requested: int = 0
    produced: int = 0
    rejected_structure: int = 0
    requests: int = 0
    errors: list[str] = field(default_factory=list)


def _strip_fence(raw: str) -> str:
    """LLM 常把 JSON 包在 ```json 代码块里，去掉外壳。"""
    match = _FENCE_RE.search(raw)
    return match.group(1) if match else raw


def _extract_questions(raw: str) -> list[dict[str, Any]]:
    """从模型输出里取出题目数组，容忍前后废话但不容忍非法 JSON。"""
    payload = json.loads(_strip_fence(raw))
    items: object = payload
    if isinstance(payload, dict):
        items = payload.get("questions")
    if not isinstance(items, list):
        raise ValueError("未找到 questions 数组")
    return [item for item in items if isinstance(item, dict)]


def _coerce_question(
    item: dict[str, Any], point: KnowledgePoint
) -> GeneratedQuestion | None:
    """把一条原始 JSON 收敛成 GeneratedQuestion；结构不合法返回 None。"""
    qtype = str(item.get("qtype", "")).strip()
    stem = str(item.get("stem", "")).strip()
    answer = str(item.get("answer", "")).strip()
    analysis = str(item.get("analysis", "")).strip()
    hints = [str(item.get(key, "")).strip() for key in ("hint1", "hint2", "hint3")]

    if qtype not in ALLOWED_QTYPES or not stem or not answer or not analysis:
        return None
    if not all(hints):
        return None

    options: dict[str, str] | None = None
    raw_options = item.get("options")
    if isinstance(raw_options, dict) and raw_options:
        options = {str(key): str(value).strip() for key, value in raw_options.items()}
        options = {key: value for key, value in options.items() if value}
        if not options:
            options = None

    difficulty_raw = item.get("difficulty", 3)
    try:
        difficulty = int(difficulty_raw)
    except (TypeError, ValueError):
        difficulty = 3
    difficulty = max(1, min(5, difficulty))

    return GeneratedQuestion(
        qtype=qtype,
        stem=stem,
        options=options,
        answer=answer,
        analysis=analysis,
        hint1=hints[0],
        hint2=hints[1],
        hint3=hints[2],
        difficulty=difficulty,
        knowledge_point_id=point.id,
    )


class QuestionGenerator:
    """按知识点批量出题。"""

    def __init__(self, client: LlmClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def _build_messages(self, point: KnowledgePoint, count: int) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": QUESTION_GEN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": QUESTION_GEN_USER_TEMPLATE.format(
                    subject=point.subject,
                    subject_name=_subject_name(point.subject),
                    grade_name=_grade_name(point.grade),
                    unit_name=point.unit_name,
                    point_name=point.name,
                    objective=point.objective,
                    question_types="、".join(point.question_types),
                    count=count,
                ),
            },
        ]

    def _token_budget(self, count: int) -> int:
        """按题量给 token 预算。

        推理模型的 reasoning 开销随题量线性增长，固定值不可靠：题量一大就
        会把预算全花在推理上、正文被截断成非法 JSON。这里按每题预留再留出
        余量，并受 content_max_tokens 兜底。
        """
        per_question = self._settings.content_tokens_per_question
        return min(
            self._settings.content_max_tokens,
            per_question * max(1, count) + per_question * 2,
        )

    async def generate(
        self, point: KnowledgePoint, *, count: int, max_rounds: int = 3
    ) -> tuple[list[GeneratedQuestion], GenerationReport]:
        """为单个知识点出题；JSON 不合法时重问，最多 max_rounds 轮。"""
        report = GenerationReport(requested=count)
        collected: list[GeneratedQuestion] = []
        remaining = count

        for round_index in range(max_rounds):
            if remaining <= 0:
                break
            # 绑定会话：同一知识点的多轮请求共享会话，命中网关提示缓存
            self._client.bind_session(f"{self._settings.llm_session_prefix}-gen-{point.id}")
            messages = self._build_messages(point, remaining)
            report.requests += 1
            try:
                result = await self._client.complete(
                    messages,
                    model=self._settings.content_generation_model,
                    temperature=0.85,
                    max_tokens=self._token_budget(remaining),
                    name=f"content.generate.{point.subject}",
                )
            except LlmError as exc:
                report.errors.append(f"{point.id} 第 {round_index + 1} 轮：{exc.code}")
                logger.warning("出题失败 %s：%s", point.id, exc.code)
                break

            try:
                items = _extract_questions(result.content)
            except (ValueError, json.JSONDecodeError) as exc:
                report.rejected_structure += 1
                report.errors.append(f"{point.id} 第 {round_index + 1} 轮结构不合法：{exc}")
                logger.warning("出题结构不合法 %s：%s", point.id, exc)
                continue

            produced = 0
            for item in items:
                question = _coerce_question(item, point)
                if question is None:
                    report.rejected_structure += 1
                    continue
                collected.append(question)
                produced += 1
            remaining = count - len(collected)
            if produced == 0 and not items:
                report.rejected_structure += 1

        report.produced = len(collected)
        return collected[:count], report


__all__ = [
    "ALLOWED_QTYPES",
    "GeneratedQuestion",
    "GenerationReport",
    "QuestionGenerationError",
    "QuestionGenerator",
]
