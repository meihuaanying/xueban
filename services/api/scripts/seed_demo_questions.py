"""种子脚本：生成演示题库（导出 JSON + 入库 + 向量化）。

用法（services/api 目录）：
    .venv/Scripts/python scripts/seed_demo_questions.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import database_session
from sqlalchemy import select

from app.config import settings
from app.data.demo_questions import generate_demo_records
from app.models import Question, QuestionStatus
from app.services.embeddings import get_embedding_provider
from app.services.import_service import import_questions
from app.services.rerank import get_rerank_provider
from app.services.retrieval_service import RetrievalService

EXPORT_PATH = Path(__file__).resolve().parents[1] / "data" / "demo" / "demo_questions.json"


def export_records(records: list[dict[str, object]]) -> Path:
    """导出为可再次导入的 JSON 文件。"""
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_PATH.write_text(
        json.dumps({"questions": records}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return EXPORT_PATH


async def main() -> int:
    """生成、导出、导入并向量化。"""
    records = generate_demo_records()
    path = export_records(records)
    print(f"已生成演示题库 {len(records)} 条 → {path}")

    rows = [(index, record) for index, record in enumerate(records, start=1)]
    async with database_session() as session:
        report = await import_questions(session, rows)
        await session.commit()
        print(
            f"入库：total={report.total} imported={report.imported} "
            f"skipped={report.skipped} invalid={report.invalid}"
        )
        for issue in report.issues[:10]:
            print(f"  行 {issue.row}: {issue.message}")

        pending = (
            (
                await session.execute(
                    select(Question).where(
                        Question.embedding.is_(None), Question.status == QuestionStatus.PUBLISHED
                    )
                )
            )
            .scalars()
            .all()
        )
        if pending:
            retriever = RetrievalService(
                get_embedding_provider(settings), get_rerank_provider(settings)
            )
            indexed = await retriever.index_questions(session, list(pending))
            await session.commit()
            print(f"已向量化 {indexed} 条（provider={settings.embedding_provider}）")
        else:
            print("全部题目均已向量化，跳过")
    return 0 if report.invalid == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
