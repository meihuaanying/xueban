"""后端活体冒烟：真实启动 uvicorn 并访问关键接口（M1 / T1.8 证据）。

用法（services/api 目录）：
    .venv/Scripts/python scripts/smoke_live.py
"""

from __future__ import annotations

import random
import sys
import threading
import time

import httpx
import uvicorn

from app.main import app

BASE_URL = "http://127.0.0.1:8001"


def start_server() -> uvicorn.Server:
    """后台线程启动 uvicorn（含 lifespan）。"""
    config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server


def wait_ready(timeout_seconds: float = 30.0) -> None:
    """等待服务就绪。"""
    deadline = time.time() + timeout_seconds
    with httpx.Client() as client:
        while time.time() < deadline:
            try:
                response = client.get(f"{BASE_URL}/healthz", timeout=2.0)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
    raise RuntimeError("服务未在预期时间内就绪")


def main() -> int:
    """执行冒烟流程。"""
    server = start_server()
    try:
        wait_ready()
        with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
            health = client.get("/healthz")
            print(f"[PASS] /healthz -> {health.status_code} {health.json()}")

            docs = client.get("/docs")
            print(f"[{'PASS' if docs.status_code == 200 else 'FAIL'}] /docs -> {docs.status_code}")

            schema = client.get("/openapi.json").json()
            print(
                f"[PASS] /openapi.json 路径数={len(schema['paths'])} "
                f"标题={schema['info']['title']}"
            )

            phone = f"137{random.randint(10000000, 99999999)}"
            register = client.post(
                "/v1/auth/register",
                json={"phone": phone, "password": "smoke-pass-123", "role": "student"},
            )
            status_text = f"[{'PASS' if register.status_code == 201 else 'FAIL'}]"
            print(f"{status_text} 注册 -> {register.status_code}")
            token = register.json()["access_token"]

            me = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            status_text = f"[{'PASS' if me.status_code == 200 else 'FAIL'}]"
            print(f"{status_text} /v1/auth/me -> {me.json()['phone']}")

            subscription = client.get(
                "/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"}
            )
            print(
                f"[{'PASS' if subscription.status_code == 200 else 'FAIL'}] 订阅状态 -> "
                f"{subscription.json()['plan']}"
            )

            trace_header = health.headers.get("X-Trace-Id")
            print(f"[{'PASS' if trace_header else 'FAIL'}] X-Trace-Id -> {trace_header}")
    finally:
        server.should_exit = True
        time.sleep(1.0)

    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
