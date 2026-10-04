"""题库内容管线编排（P1 / §6.2 全链路）。

按 REBUILD §6.2 的顺序串起五段：

    知识图谱 → LLM 批量出题 → 自动验证（数学 SymPy/规则；语文英语规则+LLM judge）
             → 去重（embedding 相似度 >0.95）→ 难度标定 → 入库 → 抽样 5% 人审队列

三条工程约束（OpenCode Go 的用量窗口 + 用户明确要求）：

1. **断点续跑以知识点为粒度**：进库前先查该知识点已有多少题，达到
   `settings.content_min_per_point` 就跳过；已入库题的题干向量与指纹作为
   去重种子传入，保证重跑不会重复生成。跑挂只需重跑，不用全量重来。
2. **批量限速**：单请求出 `content_batch_size` 道题，尽量少请求（网关按请求
   计费）；请求之间留最小间隔，避免打满 5 小时窗口。
3. **入库即打审阅标记**：按 5% 抽样写入 `QuestionStatus.REVIEW`，其余
   `PUBLISHED`。抽样的那一批是给人审的，不是给学生看的（§8 约束 8）。

难度标定：LLM 出的 difficulty 是自评，直接当作绝对值不可信。这里用
`difficulty_band`（课程树里的人工标注）做锚点，与模型自评取中位数，再夹到
1~5 —— 属于"对照教材标注做标定"的轻量实现，公开校验题集留待后续补充。
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.data.curriculum import KnowledgePoint, get_curriculum
from app.models import (
    KnowledgePoint as KnowledgePointModel,
)
from app.models import (
    Question as QuestionModel,
)
from app.models import (
    QuestionKnowledgePoint,
    QuestionStatus,
    QuestionType,
)
from app.services.embeddings import cosine_similarity, get_embedding_provider
from app.services.question_dedupe import DEDUP_THRESHOLD, QuestionDeduplicator, fingerprint
from app.services.question_generator import GeneratedQuestion, QuestionGenerator
from app.services.question_verify import QuestionVerifier

if TYPE_CHECKING:
    from app.services.llm_client import LlmClient

logger = logging.getLogger("xueban.content.pipeline")

# P1 小学内容的学段标识；与既有 knowledge_graph 的 elementary（初中）区分
ELEMENTARY_STAGE = "grade1_2"

# 题库来源标记，便于与存量 self-built 题区分
PIPELINE_SOURCE = "llm-pipeline-v1"

# 5% 抽样人审（§6.2）：实际取值走 settings.human_review_rate，这里只是文档锚点，
# 与 config.Settings.human_review_rate 的默认值保持一致。
HUMAN_REVIEW_RATE = 0.05


@dataclass(slots=True)
class PointOutcome:
    """单个知识点的处理结果。"""

    point_id: str
    existed_before: int = 0
    generated: int = 0
    verified: int = 0
    deduped_away: int = 0
    inserted: int = 0
    for_review: int = 0
    skipped: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def total_now(self) -> int:
        return self.existed_before + self.inserted


@dataclass(slots=True)
class PipelineReport:
    """整条管线的统计，用于简报与门禁取证。"""

    outcomes: list[PointOutcome] = field(default_factory=list)

    @property
    def total_generated(self) -> int:
        return sum(o.generated for o in self.outcomes)

    @property
    def total_verified(self) -> int:
        return sum(o.verified for o in self.outcomes)

    @property
    def total_inserted(self) -> int:
        return sum(o.inserted for o in self.outcomes)

    @property
    def total_deduped(self) -> int:
        return sum(o.deduped_away for o in self.outcomes)

    @property
    def total_for_review(self) -> int:
        return sum(o.for_review for o in self.outcomes)

    @property
    def verify_pass_rate(self) -> float:
        return self.total_verified / self.total_generated if self.total_generated else 0.0

    @property
    def dedupe_removal_rate(self) -> float:
        denominator = self.total_verified + self.total_deduped
        return self.total_deduped / denominator if denominator else 0.0

    def by_subject(self) -> dict[str, dict[str, int]]:
        """按学科汇总题量（用课程树的 id 前缀推断学科）。"""
        buckets: dict[str, dict[str, int]] = {}
        for outcome in self.outcomes:
            subject = _subject_of(outcome.point_id)
            bucket = buckets.setdefault(subject, {"generated": 0, "inserted": 0, "for_review": 0})
            bucket["generated"] += outcome.generated
            bucket["inserted"] += outcome.inserted
            bucket["for_review"] += outcome.for_review
        return buckets


def _subject_of(point_id: str) -> str:
    """知识点 id 形如 `g1m-...` / `g1c-...` / `g1e-...`，第二位字母是学科。"""
    if len(point_id) >= 3 and point_id[0] == "g" and point_id[2] in {"m", "c", "e"}:
        return {"m": "math", "c": "chinese", "e": "english"}[point_id[2]]
    return "unknown"


class QuestionPipeline:
    """按知识点驱动 §6.2 全链路。"""

    def __init__(
        self,
        client: LlmClient,
        settings: Settings,
        *,
        request_interval_seconds: float = 1.5,
        rng: random.Random | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._generator = QuestionGenerator(client, settings)
        self._verifier = QuestionVerifier(client, settings)
        self._deduper = QuestionDeduplicator(settings)
        self._embeddings = get_embedding_provider(settings)
        self._interval = request_interval_seconds
        self._rng = rng or random.Random()

    # ------------------------------------------------------------ 入库工具

    async def _ensure_knowledge_point(
        self, session: AsyncSession, point: KnowledgePoint, sort_order: int
    ) -> uuid.UUID:
        """把课程树里的知识点写进 knowledge_points（幂等）。"""
        existing = await session.execute(
            select(KnowledgePointModel).where(KnowledgePointModel.code == point.id)
        )
        record = existing.scalar_one_or_none()
        if record is None:
            record = KnowledgePointModel(
                code=point.id,
                name=point.name,
                subject=point.subject,
                stage=ELEMENTARY_STAGE,
                sort_order=sort_order,
            )
            session.add(record)
            await session.flush()
        return record.id

    async def _existing_stems(
        self, session: AsyncSession, knowledge_point_id: uuid.UUID
    ) -> list[str]:
        rows = await session.execute(
            select(QuestionModel.stem)
            .join(QuestionKnowledgePoint)
            .where(QuestionKnowledgePoint.knowledge_point_id == knowledge_point_id)
        )
        return [row for row in rows.scalars().all()]

    async def _count_for_point(
        self, session: AsyncSession, knowledge_point_id: uuid.UUID
    ) -> int:
        """这个知识点**真正能被抽到**的题量：只算 PUBLISHED。

        不能简单按 `QuestionKnowledgePoint` 行数算：入库时会按 `human_review_rate`
        抽 5% 写成 `QuestionStatus.REVIEW` 留给人工审阅，而练习/诊断/考试取题一律
        `status == PUBLISHED`（见 practice_service、diagnosis_service、exam_service）。
        早先这里不过滤，于是「30 题」里有 1~2 道躺在 review 区——管线认为已达标跳过，
        学生端却只能抽到 28~29 道。实测 41 个一年级知识点里有 32 个中招。
        """
        result = await session.execute(
            select(func.count())
            .select_from(QuestionKnowledgePoint)
            .join(QuestionModel, QuestionModel.id == QuestionKnowledgePoint.question_id)
            .where(
                QuestionKnowledgePoint.knowledge_point_id == knowledge_point_id,
                QuestionModel.status == QuestionStatus.PUBLISHED,
            )
        )
        return int(result.scalar_one())

    # ------------------------------------------------------------ 难度标定

    def _calibrate_difficulty(self, question: GeneratedQuestion, point: KnowledgePoint) -> int:
        """用课程树的人工 difficulty_band 做锚点，与模型自评取中位数后夹到 1~5。

        课程树的 band 是「教材难度」（1 入门/2 基础/3 进阶），模型的 difficulty 是
        1~5 自评，两者量纲不同：band 决定基准分（1→2, 2→3, 3→4），模型自评只在
        基准上下浮动一档，避免一个知识点内难度全是 1 或全是 5。
        """
        base = {1: 2, 2: 3, 3: 4}[point.difficulty_band]
        anchor = min(5, max(1, (base + question.difficulty) // 2 + 1))
        return min(5, max(1, anchor))

    # ------------------------------------------------------------ 单知识点

    async def process_point(
        self,
        session: AsyncSession,
        point: KnowledgePoint,
        *,
        sort_order: int = 0,
        target: int | None = None,
    ) -> PointOutcome:
        """处理单个知识点；已达标则跳过（断点续跑的关键）。"""
        outcome = PointOutcome(point_id=point.id)
        target = target or self._settings.content_min_per_point

        knowledge_point_id = await self._ensure_knowledge_point(session, point, sort_order)
        await session.commit()

        existed = await self._count_for_point(session, knowledge_point_id)
        outcome.existed_before = existed
        if existed >= target:
            outcome.skipped = True
            return outcome

        seed_stems = await self._existing_stems(session, knowledge_point_id)
        seed_vectors = (
            await self._embeddings.embed(seed_stems) if seed_stems else []
        )

        need = target - existed
        generated: list[GeneratedQuestion] = []
        rounds = 0
        # 收敛目标是「生成量」而不是「入库量」，所以必须按存活率放大要生成的量。
        # 否则只差 1 题的知识点只会生成 1 道题，那道题一旦被验证拒收或被去重剔除，
        # 入库量就停在 29——实测有 5 个知识点正是这样卡住的，反复重跑也补不上。
        survival = min(1.0, max(0.1, self._settings.content_expected_survival_rate))
        # 存活率还要再乘一道「人审抽走」的折扣：入库时按 human_review_rate 抽 5%
        # 写成 REVIEW，而取题只认 PUBLISHED（见 _count_for_point）。不把这一层算进去，
        # 补出来的题量会系统性地少 5%，又是一轮「跑了仍没达标」。
        publish_rate = 1.0 - min(0.9, max(0.0, self._settings.human_review_rate))
        ask_total = math.ceil(need / (survival * publish_rate))
        max_rounds = max(1, ask_total // max(1, self._settings.content_batch_size) + 2)
        while len(generated) < ask_total and rounds < max_rounds:
            rounds += 1
            batch, report = await self._generator.generate(
                point,
                count=min(
                    self._settings.content_batch_size, ask_total - len(generated)
                ),
            )
            outcome.generated += len(batch)
            outcome.errors.extend(report.errors)
            generated.extend(batch)
            if not batch:
                # 出题整体失败（网络/限流/网关）：退避后再试，避免空转烧额度。
                # 空转到 max_rounds 也不会让本知识点"假装成功"，它会以 0 题入库、
                # 下次断点续跑时重新处理。
                outcome.errors.append(f"{point.id} 第 {rounds} 轮未产出任何题目")
                if rounds < max_rounds:
                    await asyncio.sleep(max(self._interval, 5.0 * rounds))
                continue
            if rounds < max_rounds:
                await asyncio.sleep(self._interval)

        if not generated:
            return outcome

        verified, rejected, _ = await self._verifier.verify_all(generated, point)
        outcome.verified = len(verified)
        outcome.errors.extend(
            f"{question.stem[:20]}：{result.reason}" for question, result in rejected[:5]
        )

        dedupe_result = await self._deduper.dedupe(
            verified,
            seed_vectors=seed_vectors,
            seed_fingerprints=[fingerprint(stem) for stem in seed_stems],
        )
        outcome.deduped_away = dedupe_result.removed_count

        for question in dedupe_result.kept:
            record = QuestionModel(
                subject=point.subject,
                stage=ELEMENTARY_STAGE,
                qtype=QuestionType(question.qtype),
                stem=question.stem,
                options=question.options,
                answer=question.answer,
                analysis=(
                    f"{question.analysis}\n\n【第1层·思路提示】{question.hint1}\n"
                    f"【第2层·关键步骤】{question.hint2}\n"
                    f"【第3层·完整解答】{question.hint3}"
                ),
                difficulty=self._calibrate_difficulty(question, point),
                source=PIPELINE_SOURCE,
                status=(
                    QuestionStatus.REVIEW
                    if self._rng.random() < self._settings.human_review_rate
                    else QuestionStatus.PUBLISHED
                ),
            )
            session.add(record)
            await session.flush()
            session.add(
                QuestionKnowledgePoint(question_id=record.id, knowledge_point_id=knowledge_point_id)
            )
            outcome.inserted += 1
            if record.status is QuestionStatus.REVIEW:
                outcome.for_review += 1

        await session.commit()
        return outcome

    # ------------------------------------------------------------ 全量

    async def run(
        self,
        session: AsyncSession,
        *,
        subjects: tuple[str, ...] = ("math", "chinese", "english"),
        grades: tuple[str, ...] = ("grade1", "grade2"),
        limit_points: int | None = None,
        target: int | None = None,
    ) -> PipelineReport:
        """按学科/年级跑完整树；`limit_points` 用于先小批量验证再放开。"""
        report = PipelineReport()
        sort_order = 0
        for subject in subjects:
            curriculum = get_curriculum(subject)
            for point in curriculum.points:
                if point.grade not in grades:
                    continue
                sort_order += 1
                try:
                    outcome = await self.process_point(
                        session, point, sort_order=sort_order, target=target
                    )
                except Exception as exc:  # 单点失败不应中断整批
                    logger.exception("知识点处理失败 %s", point.id)
                    report.outcomes.append(
                        PointOutcome(point_id=point.id, errors=[f"{type(exc).__name__}: {exc}"])
                    )
                    continue
                report.outcomes.append(outcome)
                logger.info(
                    "知识点 %s：已有 %d → 新增 %d（生成 %d / 验证过 %d / 去重 %d）",
                    point.id,
                    outcome.existed_before,
                    outcome.inserted,
                    outcome.generated,
                    outcome.verified,
                    outcome.deduped_away,
                )
                if limit_points is not None and len(report.outcomes) >= limit_points:
                    return report
        return report


__all__ = [
    "DEDUP_THRESHOLD",
    "ELEMENTARY_STAGE",
    "HUMAN_REVIEW_RATE",
    "PIPELINE_SOURCE",
    "PipelineReport",
    "PointOutcome",
    "QuestionPipeline",
    "cosine_similarity",
]
