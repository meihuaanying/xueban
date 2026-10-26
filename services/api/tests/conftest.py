"""测试基座：独立测试库 + Alembic 迁移 + 应用装配 + 数据清理。"""

from __future__ import annotations

import asyncio
import itertools
import os
import random
import secrets
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlsplit

import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

API_DIR = Path(__file__).resolve().parents[1]

DEFAULT_TEST_URL = "postgresql+asyncpg://xueban:change-me@localhost:5432/xueban_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)

# 必须在导入 app.* 之前覆盖环境变量（Settings 为进程级单例）
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "testing"
# Settings 会读仓库根的 .env（其中 CORS_ALLOW_ORIGINS 是生产验证端口），
# 所以测试必须在导入 app.* 之前显式覆盖，否则 CORS 用例会被生产配置影响。
os.environ["CORS_ALLOW_ORIGINS"] = "http://localhost:3000"
# 同理：本地 .env 把 OCR 设为 mock，而 OCR 契约用例要求走 service 分支
os.environ["OCR_PROVIDER"] = "service"

from app.db import Base  # noqa: E402
from app.main import create_app, init_app_state  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.services.auth_service import issue_token_pair  # noqa: E402
from app.services.security import hash_password  # noqa: E402

_phone_counter = itertools.count(1)


def next_phone() -> str:
    """生成测试用手机号（符合 1[3-9]xxxxxxxxx）。

    使用「随机段 + 进程内递增」避免历史残留数据导致的冲突（失败用例可能未清库）。
    """
    suffix = (random.randrange(10_000) * 100_000 + next(_phone_counter)) % 100_000_000
    return f"139{suffix:08d}"


def _database_name(url: str) -> str:
    """从 URL 提取数据库名。"""
    return urlsplit(url).path.lstrip("/")


def _admin_url(url: str) -> str:
    """构造同实例的 postgres 维护库连接串。"""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/postgres"


async def _ensure_test_database() -> None:
    """确保测试数据库存在。"""
    engine = create_async_engine(_admin_url(TEST_DATABASE_URL), isolation_level="AUTOCOMMIT")
    name = _database_name(TEST_DATABASE_URL)
    async with engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await engine.dispose()


def _run_migrations() -> None:
    """在独立线程内执行 Alembic（env.py 内部使用 asyncio.run）。"""
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    command.upgrade(config, "head")


def _truncate_statement() -> str:
    """清空全部业务表的 TRUNCATE 语句（无 RETURNING，不能进参数化查询）。"""
    tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    return f"TRUNCATE {tables} RESTART IDENTITY CASCADE"


async def _wipe_test_database() -> None:
    """把测试库清成空库（会话开始时调用）。

    会话开始前必须清：``clean_database`` 只在**每个用例之后**清，而一次被中断的
    运行（服务器重启、进程被杀）不会执行到 teardown，残留数据就会成为下一次运行
    第一个测试的输入。这类污染的特征是「单跑通过、全量失败」，且失败点看起来
    与真正的原因毫无关系（本次实测：账号注销的 purge 用例报 ``purged == []``）。

    这里不做 DROP DATABASE：迁移要保留。清空即可，而且比 DROP 便宜得多。
    """
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(_truncate_statement()))
            # 清完必须复查：漏掉的表会让残留溜进本次运行，而症状出现在某个毫不
            # 相干的测试里。宁可在这里直接炸，也不要事后逐个用例地猜。
            for name in Base.metadata.tables:
                left = await conn.scalar(
                    text(f'SELECT count(*) FROM "{name}"')
                )
                if left:
                    raise RuntimeError(
                        f"测试库清空失败：{name} 仍有 {left} 行。"
                        "通常是 Base.metadata 未导入某个模型导致 TRUNCATE 漏表。"
                    )
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database() -> AsyncIterator[None]:
    """会话级：建库 + 迁移到最新 + 清空上一次运行的残留。"""
    await _ensure_test_database()
    await asyncio.to_thread(_run_migrations)
    await _wipe_test_database()
    yield


@pytest_asyncio.fixture(scope="session")
async def engine(prepare_database: None) -> AsyncIterator[AsyncEngine]:
    """会话级引擎。

    使用 NullPool：测试函数运行在各自的 event loop（pytest-asyncio 默认），
    连接池跨 loop 复用会触发 "attached to a different loop"，NullPool 规避该问题。
    """
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """会话工厂。"""
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture()
def app(sessionmaker: async_sessionmaker[AsyncSession]):  # type: ignore[no-untyped-def]
    """测试应用（不跑 lifespan，直接注入会话工厂）。"""
    application = create_app()
    application.state.sessionmaker = sessionmaker
    init_app_state(application)
    return application


@pytest_asyncio.fixture()
async def client(app) -> AsyncIterator[AsyncClient]:  # type: ignore[no-untyped-def]
    """ASGI 测试客户端。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client


@pytest_asyncio.fixture(autouse=True)
async def clean_database(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    """用例结束后清库（保留失败现场于用例执行期间）。"""
    yield
    async with sessionmaker() as session:
        await session.execute(text(_truncate_statement()))
        await session.commit()


@pytest_asyncio.fixture()
async def admin_token(sessionmaker: async_sessionmaker[AsyncSession]) -> str:
    """直建管理员并签发访问令牌（用于 RBAC 测试）。"""
    async with sessionmaker() as session:
        user = User(
            phone=next_phone(),
            role=UserRole.ADMIN,
            # 直建账号的口令运行时生成：源码里不留口令字面量（安全扫描红线）
            password_hash=hash_password("Adm-" + secrets.token_urlsafe(12)),
            nickname="测试管理员",
        )
        session.add(user)
        await session.flush()
        pair = await issue_token_pair(session, user)
        await session.commit()
        return pair.access_token


def auth_headers(access_token: str) -> dict[str, str]:
    """构造鉴权请求头。"""
    return {"Authorization": f"Bearer {access_token}"}


def unique_tag() -> str:
    """短随机串（构造对象键等）。"""
    return uuid.uuid4().hex[:8]
