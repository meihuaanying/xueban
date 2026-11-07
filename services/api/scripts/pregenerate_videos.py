"""§5.3 视频预生成：按题库热度生成 Top N 知识点的 Manim 讲解视频。

用法（services/api 目录）：
    # 看会挑哪些知识点（不生成）
    .venv/Scripts/python scripts/pregenerate_videos.py --limit 100 --dry-run
    # 正式生成（幂等：已 ready 的自动跳过；配额窗口耗尽会中止，重跑同命令续传）
    .venv/Scripts/python scripts/pregenerate_videos.py --limit 100
    # 指定知识点 / 其它学段学科
    .venv/Scripts/python scripts/pregenerate_videos.py --knowledge g10m-set-concept
    .venv/Scripts/python scripts/pregenerate_videos.py --subject math --stage junior --limit 30

产物：MinIO 的 ``explainer/video/<cache_key>.mp4`` + ``explainer_contents`` 行
（video_key / duration_seconds / script 六阶段快照），学生端命中缓存秒开。

注意：本脚本与题库生成队列共用同一个 LLM 网关配额（5 小时窗口）。两者不要
同时跑；视频每条要 4 次 LLM + 1 次渲染，建议放在题库队列空窗期执行。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import database_session
from sqlalchemy import func, select

from app.config import settings
from app.data.curriculum import find_point, stage_for_grade
from app.models import (
    ExplainerStatus,
    Question,
    QuestionKnowledgePoint,
    QuestionStatus,
)
from app.models import (
    KnowledgePoint as KnowledgePointModel,
)
from app.services import explainer_video
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService
from app.services.safety_service import SafetyService
from app.services.storage_service import StorageService
from app.services.tts import get_tts_provider


async def select_points(
    session: Any, *, subject: str, stage: str, limit: int
) -> list[tuple[str, str, int]]:
    """按 PUBLISHED 题量降序选知识点（同一知识点跨年级只算一次）。"""
    count = func.count(func.distinct(Question.id))
    rows = await session.execute(
        select(KnowledgePointModel.code, KnowledgePointModel.name, count)
        .join(
            QuestionKnowledgePoint,
            QuestionKnowledgePoint.knowledge_point_id == KnowledgePointModel.id,
        )
        .join(Question, Question.id == QuestionKnowledgePoint.question_id)
        .where(
            KnowledgePointModel.subject == subject,
            KnowledgePointModel.stage == stage,
            Question.status == QuestionStatus.PUBLISHED,
        )
        .group_by(KnowledgePointModel.code, KnowledgePointModel.name)
        .order_by(count.desc(), KnowledgePointModel.code)
        .limit(limit)
    )
    return [(code, name, int(total)) for code, name, total in rows.all()]


async def run(args: argparse.Namespace) -> int:
    toolchain = explainer_video.build_toolchain(settings)
    missing = toolchain.availability()
    if missing is not None:
        print(f"[fail] 视频工具链不完整：{missing}", file=sys.stderr)
        print("       先跑：.venv/Scripts/python scripts/check_manim.py", file=sys.stderr)
        return 1

    observability = ObservabilityService(settings)
    llm = LlmClient(settings, observability)
    tts = get_tts_provider(settings)
    storage = StorageService(settings)
    safety = SafetyService(settings)
    await storage.ensure_bucket()

    created = ready = failed = skipped = 0
    consecutive_failures = 0
    try:
        async with database_session() as session:
            if args.knowledge:
                targets = []
                for code in args.knowledge:
                    point = find_point(code)
                    if point is None:
                        print(f"[skip] 课程树没有知识点 {code}", file=sys.stderr)
                        continue
                    targets.append((point.id, point.name, -1))
            else:
                targets = await select_points(
                    session, subject=args.subject, stage=args.stage, limit=args.limit
                )
            if not targets:
                print("[warn] 没有可生成的知识点（题库还没达到可用量？）")
                return 0
            print(f"[plan] 选中 {len(targets)} 个知识点")
            for index, (code, name, total) in enumerate(targets, start=1):
                point = find_point(code)
                if point is None:
                    skipped += 1
                    continue
                if args.dry_run:
                    print(f"  {index:>3}. {code}  {name}  题量={total}")
                    continue
                content = await explainer_video.reserve_video_content(
                    session, point=point, settings=settings
                )
                if (
                    content.status is ExplainerStatus.READY
                    and content.video_key
                    and not args.force
                ):
                    ready += 1
                    print(f"[skip] {index}/{len(targets)} {name} 已有视频")
                    continue
                print(
                    f"[gen ] {index}/{len(targets)} {code} {name} "
                    f"（{stage_for_grade(point.grade)}·题量 {total}）"
                )
                content = await explainer_video.generate_video(
                    session,
                    content_id=content.id,
                    llm=llm,
                    settings=settings,
                    tts=tts,
                    storage=storage,
                    toolchain=toolchain,
                    safety=safety,
                    force=args.force,
                )
                await session.commit()
                if content.status is ExplainerStatus.READY and content.video_key:
                    created += 1
                    consecutive_failures = 0
                    repairs = len(content.script.get("repairs", []))
                    print(
                        f"       ok  {content.duration_seconds}s  "
                        f"{content.byte_size // 1024}KB  repairs={repairs}"
                    )
                else:
                    failed += 1
                    consecutive_failures += 1
                    print(f"       fail {content.error}", file=sys.stderr)
                    if consecutive_failures >= args.max_failures:
                        print(
                            f"[abort] 连续 {consecutive_failures} 条失败，"
                            "先排查（可能是配额窗口耗尽/网关异常），重跑同命令可续传",
                            file=sys.stderr,
                        )
                        break
                if args.delay > 0:
                    await asyncio.sleep(args.delay)
    finally:
        await llm.aclose()
        observability.flush()

    print(
        f"[done] created={created} ready={ready} failed={failed} skipped={skipped}"
    )
    return 0 if failed == 0 else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manim 视频讲解预生成（§5.3）")
    parser.add_argument("--limit", type=int, default=100, help="按题量选前 N 个知识点")
    parser.add_argument("--subject", default="math", help="学科代码（默认 math）")
    parser.add_argument(
        "--stage", default="senior", choices=("primary", "junior", "senior")
    )
    parser.add_argument(
        "--knowledge",
        action="append",
        default=[],
        help="指定知识点编码（可重复；给了就不按题量选）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只列出候选，不生成")
    parser.add_argument(
        "--force", action="store_true", help="已 ready 的也重新生成（覆盖同键产物）"
    )
    parser.add_argument("--delay", type=float, default=0.0, help="每条之间的间隔秒数")
    parser.add_argument(
        "--max-failures", type=int, default=3, help="连续失败多少条后中止（默认 3）"
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
