"""题库导入 CLI（T2.1）。

用法（services/api 目录）：
    .venv/Scripts/python scripts/import_questions.py             # 导入默认演示题库
    .venv/Scripts/python scripts/import_questions.py --validate  # 只校验（门禁命令）
    .venv/Scripts/python scripts/import_questions.py --file custom.json
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import database_session

from app.services.import_service import ImportReport, import_questions, load_records

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "data" / "demo" / "demo_questions.json"


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="学伴题库导入")
    parser.add_argument("--file", type=str, default=None, help="导入文件（.json/.csv/.xlsx）")
    parser.add_argument("--validate", action="store_true", help="只校验不入库")
    parser.add_argument("--source", type=str, default=None, help="覆盖来源标记")
    return parser.parse_args()


def print_report(report: ImportReport) -> None:
    """输出导入报告。"""
    print(
        f"导入报告：total={report.total} imported={report.imported} "
        f"skipped={report.skipped} invalid={report.invalid}"
    )
    for issue in report.issues[:20]:
        print(f"  行 {issue.row}: {issue.message}")
    if len(report.issues) > 20:
        print(f"  ... 其余 {len(report.issues) - 20} 条略")


async def run(args: argparse.Namespace) -> int:
    """执行导入/校验。"""
    path = Path(args.file) if args.file else DEFAULT_FILE
    if not path.exists():
        print(f"文件不存在：{path}（可先运行 scripts/seed_demo_questions.py 生成）")
        return 2
    rows = load_records(path)
    async with database_session() as session:
        report = await import_questions(
            session, rows, validate_only=args.validate, source_default=args.source
        )
        if not args.validate:
            await session.commit()
    mode = "校验" if args.validate else "导入"
    print(f"{mode}完成：{path}（共 {len(rows)} 行）")
    print_report(report)
    return 0 if report.ok else 1


def main() -> int:
    """入口。"""
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
