"""A/B 实验服务（F-47）：确定性分组 + 显著性检验。"""

from __future__ import annotations

import hashlib
import math
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.errors import ConflictError, NotFoundError
from app.models import (
    Experiment,
    ExperimentAssignment,
    PracticeRecord,
)

SUCCESS_ACCURACY = 0.8
MIN_ATTEMPTS = 5


def pick_variant(*, key: str, user_id: uuid.UUID, variants: list[dict[str, Any]]) -> str:
    """确定性分组：同一用户对同一实验恒定落入同一组（加权哈希）。"""
    if not variants:
        raise ConflictError("实验缺少分组定义", code="EXPERIMENT_NO_VARIANTS")
    digest = hashlib.md5(f"{key}:{user_id}".encode()).hexdigest()
    bucket = int(digest, 16) % sum(int(variant.get("weight", 1)) for variant in variants)
    cursor = 0
    for variant in variants:
        cursor += int(variant.get("weight", 1))
        if bucket < cursor:
            return str(variant["name"])
    return str(variants[-1]["name"])


async def create_experiment(
    session: AsyncSession,
    *,
    key: str,
    name: str,
    description: str | None,
    variants: list[dict[str, Any]],
    metric: str,
) -> Experiment:
    """创建实验（key 唯一）。"""
    existing = await session.scalar(select(Experiment).where(Experiment.key == key))
    if existing is not None:
        raise ConflictError("实验 key 已存在", code="EXPERIMENT_KEY_EXISTS")
    names = [str(variant["name"]) for variant in variants]
    if len(set(names)) != len(names):
        raise ConflictError("实验分组名称重复", code="EXPERIMENT_VARIANT_DUPLICATE")
    experiment = Experiment(
        key=key,
        name=name,
        description=description,
        variants=variants,
        metric=metric,
        status="running",
        started_at=utcnow(),
    )
    session.add(experiment)
    await session.flush()
    return experiment


async def get_experiment(session: AsyncSession, *, experiment_id: uuid.UUID) -> Experiment:
    """按 id 读取实验。"""
    experiment = await session.get(Experiment, experiment_id)
    if experiment is None:
        raise NotFoundError("实验不存在", code="EXPERIMENT_NOT_FOUND")
    return experiment


async def assign(session: AsyncSession, *, experiment: Experiment, user_id: uuid.UUID) -> str:
    """获取/写入用户分组（幂等；并发冲突时回读既有分组）。"""
    existing = await session.scalar(
        select(ExperimentAssignment).where(
            ExperimentAssignment.experiment_id == experiment.id,
            ExperimentAssignment.user_id == user_id,
        )
    )
    if existing is not None:
        return existing.variant
    variant = pick_variant(key=experiment.key, user_id=user_id, variants=list(experiment.variants))
    assignment = ExperimentAssignment(
        experiment_id=experiment.id, user_id=user_id, variant=variant
    )
    session.add(assignment)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == experiment.id,
                ExperimentAssignment.user_id == user_id,
            )
        )
        if existing is None:
            raise
        return str(existing.variant)
    return variant


def two_proportion_z_test(
    *, successes_a: int, total_a: int, successes_b: int, total_b: int
) -> tuple[float | None, float | None]:
    """两比例 z 检验（双侧）；样本不足返回 (None, None)。"""
    if total_a == 0 or total_b == 0:
        return None, None
    rate_a = successes_a / total_a
    rate_b = successes_b / total_b
    pooled = (successes_a + successes_b) / (total_a + total_b)
    standard_error = math.sqrt(pooled * (1 - pooled) * (1 / total_a + 1 / total_b))
    if standard_error == 0:
        return None, None
    z_score = (rate_a - rate_b) / standard_error
    p_value = math.erfc(abs(z_score) / math.sqrt(2))
    return round(z_score, 4), round(p_value, 4)


async def _user_outcome(session: AsyncSession, *, user_id: uuid.UUID) -> tuple[int, int]:
    """用户实验结果：返回 (成功标记, 是否有效样本)。"""
    row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(PracticeRecord.is_correct.is_(True)).label("correct"),
            ).where(PracticeRecord.user_id == user_id)
        )
    ).one()
    total = int(row[0] or 0)
    if total < MIN_ATTEMPTS:
        return 0, 0
    accuracy = int(row[1] or 0) / total
    return (1 if accuracy >= SUCCESS_ACCURACY else 0), 1


async def report(session: AsyncSession, *, experiment: Experiment) -> dict[str, Any]:
    """生成实验报告：分组指标 + 与对照组的显著性检验。"""
    assignments = (
        await session.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == experiment.id
            )
        )
    ).scalars().all()
    grouped: dict[str, list[uuid.UUID]] = {}
    for assignment in assignments:
        grouped.setdefault(assignment.variant, []).append(assignment.user_id)

    stats: list[dict[str, Any]] = []
    for variant in experiment.variants:
        name = str(variant["name"])
        user_ids = grouped.get(name, [])
        successes = 0
        evaluated = 0
        for user_id in user_ids:
            success, valid = await _user_outcome(session, user_id=user_id)
            successes += success
            evaluated += valid
        stats.append(
            {
                "name": name,
                "participants": len(user_ids),
                "evaluated": evaluated,
                "successes": successes,
                "conversion_rate": round(successes / evaluated, 4) if evaluated else 0.0,
            }
        )

    baseline = next((item for item in stats if item["evaluated"] > 0), None)
    variants_report: list[dict[str, Any]] = []
    for index, item in enumerate(stats):
        entry = {
            "name": item["name"],
            "participants": item["participants"],
            "successes": item["successes"],
            "conversion_rate": item["conversion_rate"],
            "mean_score": item["conversion_rate"],
            "z_score": None,
            "p_value": None,
            "significant": False,
        }
        if baseline is not None and index > 0 and item["evaluated"] > 0:
            z_score, p_value = two_proportion_z_test(
                successes_a=item["successes"],
                total_a=item["evaluated"],
                successes_b=baseline["successes"],
                total_b=baseline["evaluated"],
            )
            entry["z_score"] = z_score
            entry["p_value"] = p_value
            entry["significant"] = bool(p_value is not None and p_value < 0.05)
        variants_report.append(entry)

    conclusion = "样本不足，暂无法判定显著差异"
    if any(entry["significant"] for entry in variants_report):
        winner = max(variants_report, key=lambda entry: entry["conversion_rate"])
        conclusion = f"分组「{winner['name']}」显著优于对照组（p<0.05）"
    elif baseline is not None:
        conclusion = "各组差异不显著，建议继续积累样本"

    return {
        "experiment_id": experiment.id,
        "key": experiment.key,
        "metric": experiment.metric,
        "variants": variants_report,
        "total_participants": len(assignments),
        "conclusion": conclusion,
    }


async def list_experiments(session: AsyncSession) -> list[Experiment]:
    """实验列表。"""
    result = await session.execute(select(Experiment).order_by(Experiment.created_at.desc()))
    return list(result.scalars().all())


__all__ = [
    "assign",
    "create_experiment",
    "get_experiment",
    "list_experiments",
    "pick_variant",
    "report",
    "two_proportion_z_test",
]
