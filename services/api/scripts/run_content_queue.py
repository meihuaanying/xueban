"""题库生成队列（按学段优先级逐段跑，配额窗口耗尽即停并可续跑）。

用法（services/api 目录）：
    # 查看默认队列
    .venv/Scripts/python scripts/run_content_queue.py --list
    # 从第 0 段开始跑（默认）
    .venv/Scripts/python scripts/run_content_queue.py
    # 从上一次中断处继续
    .venv/Scripts/python scripts/run_content_queue.py --resume

设计：
- 每段 = (subjects, grades)。段内按知识点断点续跑（已达标自动跳过）；
- 任一段因 `LLM_RATE_LIMITED` 提前中止 → 记录 next_index 并返回退出码 2，
  窗口恢复后用 --resume 继续，不重复已完成的段；
- 优先级：高中语数英（高考 450 分）→ 高中选考六科 → 初中九科 → 小学。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import database_session

from app.config import settings
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from app.services.question_pipeline import QuestionPipeline

STATE_PATH = Path(__file__).resolve().parents[1] / ".pipeline_queue_state.json"


@dataclass(frozen=True, slots=True)
class Segment:
    name: str
    subjects: tuple[str, ...]
    grades: tuple[str, ...]


def default_queue() -> list[Segment]:
    """按「高中生可用」优先的顺序排列；每段单独可断点续跑。"""
    return [
        Segment("高中数学（收尾）", ("math",), ("grade10", "grade11", "grade12")),
        Segment("高中语文", ("chinese",), ("grade10", "grade11", "grade12")),
        Segment("高中英语", ("english",), ("grade10", "grade11", "grade12")),
        Segment("高中物理", ("physics",), ("grade10", "grade11", "grade12")),
        Segment("高中化学", ("chemistry",), ("grade10", "grade11", "grade12")),
        Segment("高中生物", ("biology",), ("grade10", "grade11", "grade12")),
        Segment("高中历史", ("history",), ("grade10", "grade11", "grade12")),
        Segment("高中地理", ("geography",), ("grade10", "grade11", "grade12")),
        Segment("高中政治", ("politics",), ("grade10", "grade11", "grade12")),
        Segment("初中数学", ("math",), ("grade7", "grade8", "grade9")),
        Segment("初中语文", ("chinese",), ("grade7", "grade8", "grade9")),
        Segment("初中英语", ("english",), ("grade7", "grade8", "grade9")),
        Segment("初中物理", ("physics",), ("grade8", "grade9")),
        Segment("初中化学", ("chemistry",), ("grade9",)),
        Segment("初中生物", ("biology",), ("grade7", "grade8")),
        Segment("初中历史", ("history",), ("grade7", "grade8", "grade9")),
        Segment("初中地理", ("geography",), ("grade7", "grade8")),
        Segment("初中政治", ("politics",), ("grade7", "grade8", "grade9")),
        Segment("小学高年级数学", ("math",), ("grade3", "grade4", "grade5", "grade6")),
        Segment("小学低年级数学", ("math",), ("grade1", "grade2")),
        Segment("小学高年级语文", ("chinese",), ("grade3", "grade4", "grade5", "grade6")),
        Segment("小学低年级语文", ("chinese",), ("grade1", "grade2")),
        Segment("小学高年级英语", ("english",), ("grade3", "grade4", "grade5", "grade6")),
        Segment("小学低年级英语", ("english",), ("grade1", "grade2")),
    ]


def load_state() -> int:
    if not STATE_PATH.exists():
        return 0
    try:
        return int(json.loads(STATE_PATH.read_text(encoding="utf-8")).get("next_index", 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return 0


def save_state(next_index: int, segment: str) -> None:
    STATE_PATH.write_text(
        json.dumps({"next_index": next_index, "segment": segment}, ensure_ascii=False),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="题库生成队列（广东九科）")
    parser.add_argument("--list", action="store_true", help="只打印队列")
    parser.add_argument("--resume", action="store_true", help="从上次中断的段继续")
    parser.add_argument("--start-index", type=int, default=None, help="从指定段开始")
    parser.add_argument("--target", type=int, default=None, help="每知识点目标题量")
    parser.add_argument("--interval", type=float, default=1.5, help="请求间隔秒")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    queue = default_queue()
    if args.list:
        for index, segment in enumerate(queue):
            subjects = ",".join(segment.subjects)
            grades = ",".join(segment.grades)
            print(f"{index:02d} {segment.name}: {subjects} / {grades}")
        return 0

    start = args.start_index
    if start is None:
        start = load_state() if args.resume else 0
    start = max(0, min(start, len(queue)))
    target = args.target or settings.content_min_per_point

    observability = ObservabilityService(settings)
    client = LlmClient(settings, observability)
    try:
        async with database_session() as session:
            for index in range(start, len(queue)):
                segment = queue[index]
                pipeline = QuestionPipeline(
                    client, settings, request_interval_seconds=args.interval
                )
                print(
                    json.dumps(
                        {"segment": segment.name, "index": index, "status": "start"},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                report = await pipeline.run(
                    session,
                    subjects=segment.subjects,
                    grades=segment.grades,
                    target=target,
                )
                summary = {
                    "segment": segment.name,
                    "index": index,
                    "points": len(report.outcomes),
                    "inserted": report.total_inserted,
                    "aborted_reason": report.aborted_reason,
                }
                print(json.dumps(summary, ensure_ascii=False), flush=True)
                if report.aborted_reason:
                    save_state(index, segment.name)
                    print(
                        "配额窗口耗尽，已记录断点；窗口恢复后运行 --resume 继续。",
                        file=sys.stderr,
                    )
                    return 2
                save_state(index + 1, segment.name)
    finally:
        await client.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
