"""为压测/联调准备一个带学情数据的账号（重设密码）。

用法（services/api 目录，Windows 用 .venv/Scripts/python）：
    python -m scripts.prepare_load_user --phone 17136015493 --password load-test-123
    python -m scripts.prepare_load_user --pick  # 自动挑选数据最丰富的用户

仅用于本地/预发环境；生产环境禁止执行。
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import func, select

from app.models import User
from app.services.security import hash_password
from scripts._common import database_session


async def _pick_phone() -> str | None:
    """挑选 plan_tasks 最多的用户。"""
    from app.models import PlanTask

    async with database_session() as session:
        stmt = (
            select(User.phone, func.count(PlanTask.id).label("tasks"))
            .join(PlanTask, PlanTask.user_id == User.id)
            .group_by(User.phone)
            .order_by(func.count(PlanTask.id).desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).first()
        return row[0] if row else None


async def _reset(phone: str, password: str) -> int:
    async with database_session() as session:
        user = (await session.execute(select(User).where(User.phone == phone))).scalar_one_or_none()
        if user is None:
            print(f"用户不存在: {phone}", file=sys.stderr)
            return 1
        user.password_hash = hash_password(password)
        await session.commit()
        print(f"OK: {phone} 密码已重置（{len(password)} 字符）")
        return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="压测账号准备")
    parser.add_argument("--phone", help="目标手机号")
    parser.add_argument("--password", default="load-test-123", help="新密码")
    parser.add_argument("--pick", action="store_true", help="自动挑选数据最丰富的用户")
    args = parser.parse_args()

    phone = args.phone
    if args.pick:
        phone = await _pick_phone()
        if not phone:
            print("未找到可挑选的用户", file=sys.stderr)
            return 1
        print(f"已挑选: {phone}")
    if not phone:
        parser.error("需要 --phone 或 --pick")

    return await _reset(phone, args.password)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
