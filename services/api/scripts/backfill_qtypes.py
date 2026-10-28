"""按题型专项补题（新高考数学 19 题结构：多选 3 道、解答题 5 道）。

用途：普通队列按「每知识点总题量」推进，choice/fill 先达标后整个知识点会被跳过，
多选/解答题就永远补不出来。本脚本只按**目标题型**计数与生成：

    .venv/Scripts/python scripts/backfill_qtypes.py --qtype multi_choice --target 3
    .venv/Scripts/python scripts/backfill_qtypes.py --qtype short_answer --target 2

断点：幂等——已达标知识点自动跳过，配额耗尽退出码 2，窗口恢复后重跑同一命令。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import database_session

from app.config import settings
from app.data.curriculum import get_curriculum
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from app.services.question_pipeline import _ABORT_ERROR_CODES, QuestionPipeline

_SUBJECT_DEFAULT = ("math",)
_GRADE_DEFAULT = ("grade10", "grade11", "grade12")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按题型专项补题")
    parser.add_argument("--qtype", required=True, help="目标题型（multi_choice / short_answer）")
    parser.add_argument("--target", type=int, required=True, help="每知识点该题型的达标题量")
    parser.add_argument("--subjects", default=",".join(_SUBJECT_DEFAULT))
    parser.add_argument("--grades", default=",".join(_GRADE_DEFAULT))
    parser.add_argument("--interval", type=float, default=1.5, help="请求间隔秒")
    parser.add_argument(
        "--limit-points", type=int, default=None, help="只处理前 N 个知识点（排障）"
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    subjects = tuple(item.strip() for item in args.subjects.split(",") if item.strip())
    grades = tuple(item.strip() for item in args.grades.split(",") if item.strip())

    observability = ObservabilityService(settings)
    client = LlmClient(settings, observability)
    pipeline = QuestionPipeline(client, settings, request_interval_seconds=args.interval)
    consecutive_zero_insert = 0
    processed = 0
    try:
        async with database_session() as session:
            for subject in subjects:
                curriculum = get_curriculum(subject)
                for sort_order, point in enumerate(curriculum.points, start=1):
                    if point.grade not in grades:
                        continue
                    if args.limit_points is not None and processed >= args.limit_points:
                        return 0
                    processed += 1
                    try:
                        outcome = await pipeline.process_point(
                            session,
                            point,
                            sort_order=sort_order,
                            target=args.target,
                            qtype=args.qtype,
                        )
                    except Exception as exc:  # 单点失败不中断整批
                        await session.rollback()
                        print(
                            json.dumps(
                                {"point": point.id, "error": f"{type(exc).__name__}: {exc}"},
                                ensure_ascii=False,
                            ),
                            flush=True,
                        )
                        if any(code in str(exc) for code in _ABORT_ERROR_CODES):
                            consecutive_zero_insert += 1
                        else:
                            consecutive_zero_insert = 0
                        if consecutive_zero_insert >= 2:
                            print("配额窗口耗尽，窗口恢复后重跑同一命令。", file=sys.stderr)
                            return 2
                        continue

                    summary = {
                        "point": point.id,
                        "qtype": args.qtype,
                        "existed": outcome.existed_before,
                        "inserted": outcome.inserted,
                        "skipped": outcome.skipped,
                    }
                    print(json.dumps(summary, ensure_ascii=False), flush=True)
                    gateway_down = any(
                        code in error
                        for error in outcome.errors
                        for code in _ABORT_ERROR_CODES
                    )
                    if gateway_down and outcome.inserted == 0:
                        consecutive_zero_insert += 1
                    else:
                        consecutive_zero_insert = 0
                    if consecutive_zero_insert >= 2:
                        print("配额窗口耗尽，窗口恢复后重跑同一命令。", file=sys.stderr)
                        return 2
    finally:
        await client.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
