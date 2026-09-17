"""导出 promptfoo 评测用例与提示词快照（F-11 红线评测，T3.4）。

用法（services/api 目录）：
    .venv/Scripts/python scripts/export_eval_cases.py [--limit 50]

产物：
    evals/tutor_cases.json      —— 50 条评测用例（题干 + 标准答案 + 知识点）
    evals/prompts/tutor_level1.txt —— 第 1 层提示词快照（与 app/services/prompts.py 同步生成）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import database_session
from sqlalchemy import select

from app.models import Question, QuestionStatus
from app.services.prompts import (
    TUTOR_LEVEL_INSTRUCTIONS,
    TUTOR_SYSTEM_PROMPT,
    TUTOR_USER_TEMPLATE,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
EVALS_DIR = REPO_ROOT / "evals"


def write_prompt_snapshot() -> Path:
    """生成第 1 层提示词快照（保持与代码一致）。"""
    prompts_dir = EVALS_DIR / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    template = TUTOR_USER_TEMPLATE.format(
        stem="{{stem}}",
        qtype="{{qtype}}",
        options_block="",
        level=1,
        history_block="",
        level_instruction=TUTOR_LEVEL_INSTRUCTIONS[1],
    )
    content = f"[system]\n{TUTOR_SYSTEM_PROMPT}\n\n[user]\n{template}\n"
    path = prompts_dir / "tutor_level1.txt"
    path.write_text(content, encoding="utf-8")
    return path


async def export_cases(limit: int) -> Path:
    """导出评测用例。"""
    async with database_session() as session:
        questions = (
            (
                await session.execute(
                    select(Question)
                    .where(Question.status == QuestionStatus.PUBLISHED)
                    .order_by(Question.created_at)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
    cases = [
        {
            "description": f"红线评测 #{index}",
            "vars": {
                "stem": question.stem,
                "qtype": question.qtype.value,
                "answer": question.answer,
                # 供 mock provider 直连本机 API（/v1/tutor/session）复现讲解链路
                "question_id": str(question.id),
            },
        }
        for index, question in enumerate(questions, start=1)
    ]
    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    path = EVALS_DIR / "tutor_cases.json"
    path.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


async def main() -> int:
    """入口。"""
    parser = argparse.ArgumentParser(description="导出 promptfoo 评测用例")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    cases_path = await export_cases(args.limit)
    prompt_path = write_prompt_snapshot()
    print(f"评测用例：{cases_path}（{args.limit} 条上限）")
    print(f"提示词快照：{prompt_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
