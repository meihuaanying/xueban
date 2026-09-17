"""验证 Langfuse 全链路 trace（M1 / T1.5）。

前置：本机已启动 Langfuse（infra/docker compose），并已配置开发密钥。

用法（services/api 目录）：
    LANGFUSE_PUBLIC_KEY=pk-lf-xueban-dev LANGFUSE_SECRET_KEY=sk-lf-xueban-dev \
        .venv/Scripts/python scripts/verify_langfuse_trace.py

脚本动作：
1) 以「讲解请求」形态记录一次 LLM generation（prompt/响应/耗时/token）；
2) 真实经 LiteLLM 发起一次调用（无供应商 Key 时应返回明确错误且不崩溃）；
3) 通过 Langfuse 公开 API 拉取该 trace，确认可检索（UI 同源数据）。
"""

from __future__ import annotations

import asyncio
import base64
import sys
import time
import uuid

import httpx

from app.config import settings
from app.errors import LlmError
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService


def fetch_trace(trace_id: str, timeout_seconds: int = 45) -> dict[str, object] | None:
    """轮询 Langfuse 公开 API，直到 trace 可检索。"""
    auth = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()
    deadline = time.time() + timeout_seconds
    with httpx.Client(timeout=10.0) as client:
        while time.time() < deadline:
            response = client.get(
                f"{settings.langfuse_host}/api/public/traces/{trace_id}",
                headers={"Authorization": f"Basic {auth}"},
            )
            if response.status_code == 200:
                return dict(response.json())
            time.sleep(2.0)
    return None


async def main() -> int:
    """执行验证流程。"""
    trace_id = uuid.uuid4().hex
    observability = ObservabilityService(settings)
    print(f"[1] Langfuse 观测启用：{observability.enabled}")
    if not observability.enabled:
        print("未配置 LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY，无法验证")
        return 1

    print(f"[2] 记录讲解请求 trace：{trace_id}")
    observability.record_llm_call(
        trace_id=trace_id,
        name="tutor.hint.level1",
        model=settings.llm_default_model,
        input_payload=[
            {"role": "system", "content": "守护型讲解：第 1 层提示只给思路，不给答案"},
            {"role": "user", "content": "求解 2x + 3 = 7"},
        ],
        output_payload="先想一想：要让 x 单独留在一边，等号两边应该同时减去几？",
        usage={"prompt_tokens": 86, "completion_tokens": 42, "total_tokens": 128},
        latency_ms=812,
    )

    print(f"[3] 经 LiteLLM 真实调用（{settings.litellm_base_url}）")
    llm = LlmClient(settings, observability)
    try:
        result = await llm.complete(
            [{"role": "user", "content": "你好"}],
            trace_id=trace_id,
            name="llm.connectivity_check",
        )
        print(f"LLM 调用成功：{result.model} / {result.content[:40]!r}")
    except LlmError as exc:
        print(f"LLM 调用失败但错误明确（未崩溃）：{exc.code} - {exc.message[:100]}")
    finally:
        await llm.aclose()

    observability.flush()
    print("[4] 等待 Langfuse 摄取并检索 trace ...")
    trace = fetch_trace(trace_id)
    if trace is None:
        print("TRACE_NOT_FOUND：请检查 Langfuse 服务与密钥")
        return 1
    observations = trace.get("observations", [])
    print(f"TRACE_FOUND id={trace.get('id')} name={trace.get('name')}")
    if isinstance(observations, list):
        for item in observations:
            if isinstance(item, dict):
                print(
                    f"  - observation: {item.get('name')} type={item.get('type')} "
                    f"level={item.get('level')} model={item.get('model')}"
                )
    print("VERIFY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
