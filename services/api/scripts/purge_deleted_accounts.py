"""物理删除超过保留期的注销账号（规格书 §10：注销后 30 天内物理删除）。

用法（services/api 目录）：
    .venv/Scripts/python -m scripts.purge_deleted_accounts --dry-run
    .venv/Scripts/python -m scripts.purge_deleted_accounts            # 默认保留 30 天
    .venv/Scripts/python -m scripts.purge_deleted_accounts --days 0   # 演练：立即清理

建议：生产由 crontab 每日 04:00 执行（日志留存）；子表数据按外键级联删除。
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.services import auth_service
from scripts._common import database_session


async def main() -> int:
    parser = argparse.ArgumentParser(description="注销账号物理删除（purge）")
    parser.add_argument("--days", type=int, default=30, help="保留天数（默认 30）")
    parser.add_argument("--dry-run", action="store_true", help="只列出将删除的账号，不执行")
    args = parser.parse_args()

    async with database_session() as session:
        user_ids = await auth_service.purge_deleted_accounts(
            session, retention_days=args.days, dry_run=args.dry_run
        )
        if not args.dry_run:
            await session.commit()

    mode = "DRY-RUN" if args.dry_run else "PURGED"
    print(f"{mode}: 保留期 {args.days} 天，匹配账号 {len(user_ids)} 个")
    for user_id in user_ids[:20]:
        print(f"  - {user_id}")
    if len(user_ids) > 20:
        print(f"  ... 其余 {len(user_ids) - 20} 个")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
