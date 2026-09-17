"""请求中间件：trace_id 注入 + 访问日志。

说明：两者均为纯 ASGI 中间件（不基于 BaseHTTPMiddleware）。
BaseHTTPMiddleware 会为每个请求创建任务组与流桥接，在高并发下引入
大量事件循环回调开销（实测占单请求 CPU 的主要部分），故以纯 ASGI 实现。
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from starlette.datastructures import MutableHeaders

logger = logging.getLogger("xueban.access")

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


class TraceIdMiddleware:
    """为每个请求分配 trace_id（优先复用上游传入），并写入响应头。"""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        incoming = headers.get(b"x-trace-id")
        trace_id = incoming.decode("latin-1") if incoming else uuid.uuid4().hex
        state = scope.setdefault("state", {})
        state["trace_id"] = trace_id

        async def send_with_trace_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Trace-Id"] = trace_id
            await send(message)

        await self.app(scope, receive, send_with_trace_id)


class RequestLogMiddleware:
    """记录请求方法/路径/状态码/耗时。"""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status_holder = {"status": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            method = scope.get("method", "-")
            path = scope.get("path", "-")
            status = status_holder["status"]
            trace_id = (scope.get("state") or {}).get("trace_id")
            logger.info(
                "%s %s -> %s (%sms)",
                method,
                path,
                status,
                elapsed_ms,
                extra={
                    "trace_id": trace_id,
                    "context": {
                        "method": method,
                        "path": path,
                        "status": status,
                        "elapsed_ms": elapsed_ms,
                    },
                },
            )
