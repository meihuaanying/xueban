"""基础设施工具测试：db 工具、日志配置、OpenAPI 导出。"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.db import create_engine, jsonable, session_scope
from app.logging_setup import JsonFormatter, setup_logging


def test_jsonable_recurses() -> None:
    value = {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "when": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        "day": date(2026, 1, 2),
        "nested": [{"inner": uuid.UUID(int=2)}],
        "plain": 3,
    }
    converted = jsonable(value)
    assert converted["id"] == "00000000-0000-0000-0000-000000000001"
    assert converted["day"] == "2026-01-02"
    assert converted["when"].startswith("2026-01-02T03:04:05")
    assert converted["nested"][0]["inner"] == uuid.UUID(int=2).__str__()
    assert converted["plain"] == 3


async def test_session_scope_executes_query(
    sessionmaker: async_sessionmaker,
) -> None:
    async for session in session_scope(sessionmaker):
        value = await session.scalar(text("SELECT 1"))
        assert value == 1


async def test_create_engine_roundtrip() -> None:
    import os

    engine: AsyncEngine = create_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT 1")) == 1
    await engine.dispose()


def test_setup_logging_idempotent() -> None:
    setup_logging()
    setup_logging()
    root = logging.getLogger()
    formatters = [type(handler.formatter) for handler in root.handlers]
    assert formatters.count(JsonFormatter) == 1


def test_json_formatter_includes_context() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="xueban.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="请求完成",
        args=(),
        exc_info=None,
    )
    record.trace_id = "t-123"
    record.context = {"path": "/healthz", "status": 200}
    payload = json.loads(formatter.format(record))
    assert payload["trace_id"] == "t-123"
    assert payload["path"] == "/healthz"
    assert payload["message"] == "请求完成"


def test_json_formatter_with_exception() -> None:
    formatter = JsonFormatter()
    try:
        raise ValueError("模拟异常")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="xueban.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="失败",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert "ValueError" in payload["exc"]
