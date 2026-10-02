"""题库内容管线命令行（P1 / §6.2）。

用法（services/api 目录下）：
    # 先小批量验证一个知识点
    .venv/Scripts/python scripts/run_content_pipeline.py --limit-points 1 --target 5
    # 放开跑全量（按知识点断点续跑，可反复执行直到达标）
    .venv/Scripts/python scripts/run_content_pipeline.py

参数：
    --limit-points  只处理前 N 个知识点（先小批量验证再放开）
    --target        每个知识点的目标题量，默认取 settings.content_min_per_point
    --subjects      逗号分隔的学科，默认 math,chinese,english
    --grades        逗号分隔的年级，默认 grade1,grade2
    --no-judge      跳过 LLM judge（只跑规则通道；仅用于排障，不建议）

断点续跑：以知识点为粒度。已入库题量达到目标就跳过该知识点，所以跑挂了
直接重跑即可；已入库题还会作为去重种子，避免重新生成重复题。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import database_session
from sqlalchemy import func, select

from app.config import settings
from app.models import KnowledgePoint, Question, QuestionKnowledgePoint
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from app.services.question_pipeline import (
    ELEMENTARY_STAGE,
    QuestionPipeline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="学伴题库内容管线（P1 / §6.2）")
    parser.add_argument("--limit-points", type=int, default=None)
    parser.add_argument("--target", type=int, default=None)
    parser.add_argument("--subjects", default="math,chinese,english")
    parser.add_argument("--grades", default="grade1,grade2")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument(
        "--interval",
        type=float,
        default=1.5,
        help="请求间隔秒数（Go 有用量窗口，别打太满）",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    subjects = tuple(part.strip() for part in args.subjects.split(",") if part.strip())
    grades = tuple(part.strip() for part in args.grades.split(",") if part.strip())
    target = args.target or settings.content_min_per_point

    observability = ObservabilityService(settings)
    client = LlmClient(settings, observability)
    pipeline = QuestionPipeline(client, settings, request_interval_seconds=args.interval)
    if args.no_judge:
        # 排障开关：judge 一律放行，只跑规则通道。正式出库必须走完整双通道，
        # 这里只用于定位网关连通性/额度问题。
        pipeline._verifier.judge = _disabled_judge

    try:
        async with database_session() as session:
            report = await pipeline.run(
                session,
                subjects=subjects,
                grades=grades,
                limit_points=args.limit_points,
                target=target,
            )
            summary = {
                "points_processed": len(report.outcomes),
                "points_skipped": sum(1 for o in report.outcomes if o.skipped),
                "generated": report.total_generated,
                "verified": report.total_verified,
                "deduped_away": report.total_deduped,
                "inserted": report.total_inserted,
                "for_review": report.total_for_review,
                "verify_pass_rate": round(report.verify_pass_rate, 4),
                "dedupe_removal_rate": round(report.dedupe_removal_rate, 4),
                "by_subject": report.by_subject(),
                "target_per_point": target,
                "generation_model": settings.content_generation_model,
                "judge_model": settings.content_judge_model,
                # 出题失败与验证拒绝都记在这里。只给样本而不是全文：全量跑会
                # 有上千条，逐条打印会把真正的异常淹没在正常拒绝里。
                "error_count": sum(len(o.errors) for o in report.outcomes),
                "error_sample": [
                    f"{o.point_id}：{msg}"
                    for o in report.outcomes
                    for msg in o.errors
                ][:10],
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            await session.commit()

            totals = await _db_totals(session)
            print(json.dumps(totals, ensure_ascii=False, indent=2))
    finally:
        await client.aclose()
    return 0


async def _db_totals(session: object) -> dict[str, int]:
    """核对数据库里的实际入库量，避免报告与库不一致。"""
    rows = (
        await session.execute(  # type: ignore[attr-defined]
            select(Question.subject, func.count())
            .where(Question.stage == ELEMENTARY_STAGE)
            .group_by(Question.subject)
        )
    ).all()
    by_subject = {subject: int(count) for subject, count in rows}
    total = await session.scalar(  # type: ignore[attr-defined]
        select(func.count()).select_from(Question).where(Question.stage == ELEMENTARY_STAGE)
    )
    points = await session.scalar(  # type: ignore[attr-defined]
        select(func.count())
        .select_from(KnowledgePoint)
        .where(KnowledgePoint.stage == ELEMENTARY_STAGE)
    )
    below = (
        await session.execute(  # type: ignore[attr-defined]
            select(func.count())
            .select_from(QuestionKnowledgePoint)
            .join(
                Question,
                Question.id == QuestionKnowledgePoint.question_id,
            )
            .where(Question.stage == ELEMENTARY_STAGE)
            .group_by(QuestionKnowledgePoint.knowledge_point_id)
            .having(func.count() < settings.content_min_per_point)
        )
    ).all()
    return {
        "db_total_questions": int(total or 0),
        "db_knowledge_points": int(points or 0),
        "db_by_subject": by_subject,
        "db_points_below_target": len(below),
    }


async def _disabled_judge(*args: object, **kwargs: object) -> tuple[bool, int, str]:
    """排障用：judge 一律放行。"""
    del args, kwargs
    return True, 100, "judge 已按 --no-judge 跳过"


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
