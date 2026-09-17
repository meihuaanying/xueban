"""LLM 客户端测试（T1.4）：主备降级由网关配置承担，本层验证重试/超时/错误映射/观测。"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.config import Settings
from app.errors import LlmError
from app.services.llm_client import LlmClient
from app.services.observability import ObservabilityService


class FakeObservation:
    """假 Langfuse 观测对象。"""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.ended = False

    def end(self) -> None:
        self.ended = True


class FakeLangfuse:
    """假 Langfuse 客户端。"""

    def __init__(self) -> None:
        self.observations: list[FakeObservation] = []
        self.events: list[dict[str, Any]] = []
        self.flushed = 0

    def start_observation(self, **kwargs: Any) -> FakeObservation:
        observation = FakeObservation(**kwargs)
        self.observations.append(observation)
        return observation

    def create_event(self, **kwargs: Any) -> None:
        self.events.append(kwargs)

    def flush(self) -> None:
        self.flushed += 1


def make_settings(**overrides: Any) -> Settings:
    """测试用配置（重试退避为 0）。"""
    base: dict[str, Any] = {
        "litellm_base_url": "http://llm.test",
        "litellm_master_key": "sk-test",
        "llm_max_retries": 1,
        "llm_retry_backoff_seconds": 0.0,
        "langfuse_public_key": "",
        "langfuse_secret_key": "",
    }
    base.update(overrides)
    return Settings(**base)


def make_observability(**overrides: Any) -> tuple[ObservabilityService, FakeLangfuse]:
    """测试用观测服务（注入假客户端）。"""
    fake = FakeLangfuse()
    return ObservabilityService(make_settings(**overrides), client=fake), fake


def success_payload(content: str = "你好，我来一步步引导你。") -> dict[str, Any]:
    """标准 Chat Completions 响应。"""
    return {
        "id": "chatcmpl-test",
        "model": "deepseek-chat",
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }


def client_with_handler(
    handler: Any, observability: ObservabilityService, **settings_overrides: Any
) -> LlmClient:
    """构造带 MockTransport 的客户端。"""
    settings = make_settings(**settings_overrides)
    return LlmClient(settings, observability, transport=httpx.MockTransport(handler))


async def test_complete_success() -> None:
    observability, _ = make_observability()
    client = client_with_handler(
        lambda request: httpx.Response(200, json=success_payload()), observability
    )
    result = await client.complete([{"role": "user", "content": "讲解这道题"}])
    assert result.content.startswith("你好")
    assert result.model == "deepseek-chat"
    assert result.usage["total_tokens"] == 20
    await client.aclose()


async def test_complete_records_observability() -> None:
    observability, fake = make_observability()
    client = client_with_handler(
        lambda request: httpx.Response(200, json=success_payload()), observability
    )
    await client.complete(
        [{"role": "user", "content": "讲解这道题"}],
        trace_id="a" * 32,
        name="tutor.hint",
    )
    assert len(fake.observations) == 1
    observation = fake.observations[0]
    assert observation.ended is True
    assert observation.kwargs["trace_context"] == {"trace_id": "a" * 32}
    assert observation.kwargs["as_type"] == "generation"
    assert observation.kwargs["usage_details"]["total_tokens"] == 20
    await client.aclose()


async def test_retry_on_500_then_success() -> None:
    observability, _ = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, text="upstream boom")
        return httpx.Response(200, json=success_payload("重试成功"))

    client = client_with_handler(handler, observability)
    result = await client.complete([{"role": "user", "content": "hi"}])
    assert calls["n"] == 2
    assert result.content == "重试成功"
    await client.aclose()


async def test_timeout_exhausts_retries() -> None:
    observability, _ = make_observability()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("模拟超时", request=request)

    client = client_with_handler(handler, observability)
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == "LLM_UNAVAILABLE"
    assert excinfo.value.status_code == 503
    await client.aclose()


async def test_auth_error_has_clear_message() -> None:
    observability, fake = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, text="unauthorized")

    client = client_with_handler(handler, observability)
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == "LLM_AUTH_FAILED"
    assert "LITELLM_MASTER_KEY" in excinfo.value.message
    assert calls["n"] == 1  # 鉴权失败不重试
    assert fake.observations and fake.observations[-1].kwargs["level"] == "ERROR"
    await client.aclose()


async def test_model_not_found() -> None:
    observability, _ = make_observability()
    client = client_with_handler(
        lambda request: httpx.Response(404, text="model not found"), observability
    )
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}], model="unknown-model")
    assert excinfo.value.code == "LLM_MODEL_NOT_FOUND"
    await client.aclose()


async def test_rate_limited() -> None:
    observability, _ = make_observability()
    client = client_with_handler(
        lambda request: httpx.Response(429, text="too many requests"), observability
    )
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == "LLM_RATE_LIMITED"
    await client.aclose()


async def test_request_rejected() -> None:
    observability, _ = make_observability()
    client = client_with_handler(
        lambda request: httpx.Response(400, text="bad request detail"), observability
    )
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == "LLM_REQUEST_REJECTED"
    assert "bad request detail" in excinfo.value.message
    await client.aclose()


async def test_bad_response_structure() -> None:
    observability, _ = make_observability()
    client = client_with_handler(lambda request: httpx.Response(200, json={}), observability)
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == "LLM_BAD_RESPONSE"
    await client.aclose()


async def test_payload_includes_model_and_temperature() -> None:
    import json

    observability, _ = make_observability()
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=success_payload())

    client = client_with_handler(handler, observability)
    await client.complete(
        [{"role": "user", "content": "hi"}], model="qwen-plus", temperature=0.2, max_tokens=256
    )
    assert captured["model"] == "qwen-plus"
    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 256
    await client.aclose()


async def test_mock_provider_returns_deterministic_hint() -> None:
    """mock 提供商：按「第 N 层」返回确定性讲解文本，且不发起网络请求。"""

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - 不应被调用
        raise AssertionError("mock 模式不应发起网络请求")

    observability, _ = make_observability()
    client = client_with_handler(handler, observability, llm_provider="mock")
    result = await client.complete(
        [
            # 系统提示词中出现「第 3 层」属于干扰项，不应影响层级识别
            {"role": "system", "content": "绝不直接给答案，除非推进到第 3 层（全解）。"},
            {
                "role": "user",
                "content": "题目：1+1=？\n学生当前求助层级：第 2 层 / 共 3 层",
            },
        ]
    )
    assert result.model == "mock"
    assert "关键步骤" in result.content
    assert "答案" not in result.content
    await client.aclose()


async def test_mock_provider_stream_yields_incrementally() -> None:
    """mock 流式：多段增量拼接等于完整文本。"""
    observability, _ = make_observability()
    client = client_with_handler(
        lambda request: httpx.Response(500), observability, llm_provider="mock"
    )
    chunks = [
        chunk
        async for chunk in client.stream_complete(
            [
                {"role": "system", "content": "绝不直接给答案，除非推进到第 3 层。"},
                {
                    "role": "user",
                    "content": "学生当前求助层级：第 1 层 / 共 3 层\n只给方向。",
                },
            ]
        )
    ]
    assert len(chunks) >= 2
    assert "思路提示" in "".join(chunks)
    await client.aclose()
