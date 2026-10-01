"""题目去重（P1 / §6.2 第四段）。

§6.2 要求"embedding 相似度 >0.95 判重"。这里用 `lexical` 词面向量：

- 它不理解同义改写，所以**判重是保守的**——阈值 0.95 下宁可漏判（留着进人审），
  也不误判（把好题删掉）。漏判的代价由后续 5% 人审队列兜住。
- 判重是**两两**比较，为避免 O(n²) 在大批量下过慢，先用题干归一化后的精确
  指纹做一次 O(n) 粗筛，命中指纹的直接判重，未命中的才走向量比较。
- 跨批次有效：调用方把已入库题目的向量传进来当"种子"，就能拦住断点续跑时
  重新生成的重复题。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.config import Settings
from app.services.embeddings import cosine_similarity, get_embedding_provider
from app.services.question_generator import GeneratedQuestion

# §6.2 规定的判重阈值
DEDUP_THRESHOLD = 0.95

_PUNCT_RE = re.compile(r"[\s，。、；：？！,.;:?!\-—_()（）【】\"'“”‘’…·]+")


def fingerprint(stem: str) -> str:
    """题干归一化指纹：全角转半角、去标点空白、统一小写。

    只用于 O(n) 粗筛；真正的判重仍以向量余弦为准。
    """
    normalized = unicodedata.normalize("NFKC", stem).lower()
    return _PUNCT_RE.sub("", normalized)


@dataclass(slots=True)
class DedupeResult:
    """去重结果与统计。"""

    kept: list[GeneratedQuestion] = field(default_factory=list)
    duplicates: list[tuple[GeneratedQuestion, float, str]] = field(default_factory=list)

    @property
    def removed_count(self) -> int:
        return len(self.duplicates)

    @property
    def removal_rate(self) -> float:
        total = len(self.kept) + len(self.duplicates)
        return self.removed_count / total if total else 0.0


class QuestionDeduplicator:
    """按向量余弦相似度剔除近重复题目。"""

    def __init__(self, settings: Settings, *, threshold: float | None = None) -> None:
        self._threshold = settings.dedup_threshold if threshold is None else threshold
        self._provider = get_embedding_provider(settings)

    async def dedupe(
        self,
        questions: list[GeneratedQuestion],
        *,
        seed_vectors: list[list[float]] | None = None,
        seed_fingerprints: Iterable[str] | None = None,
    ) -> DedupeResult:
        """去重；seed_* 用于把已入库的题当种子，跨批次拦截重复。"""
        result = DedupeResult()
        if not questions:
            return result

        vectors = await self._provider.embed([question.stem for question in questions])
        if len(vectors) != len(questions):
            raise ValueError("向量化结果与题目数量不匹配")

        seen_fingerprints: set[str] = set(seed_fingerprints or ())
        kept_vectors: list[list[float]] = list(seed_vectors or [])
        kept_fingerprints: set[str] = set(seen_fingerprints)

        for question, vector in zip(questions, vectors, strict=True):
            mark = fingerprint(question.stem)
            if mark in kept_fingerprints:
                result.duplicates.append((question, 1.0, "题干归一化后完全相同"))
                continue

            duplicate_of = None
            best_score = 0.0
            for index, existing in enumerate(kept_vectors):
                score = cosine_similarity(vector, existing)
                if score > best_score:
                    best_score = score
                    if score > self._threshold:
                        duplicate_of = index
                        break

            if duplicate_of is not None:
                result.duplicates.append(
                    (question, best_score, f"与已保留题目相似度 {best_score:.4f}")
                )
                continue

            result.kept.append(question)
            kept_vectors.append(vector)
            kept_fingerprints.add(mark)

        return result


__all__ = ["DEDUP_THRESHOLD", "DedupeResult", "QuestionDeduplicator", "fingerprint"]
