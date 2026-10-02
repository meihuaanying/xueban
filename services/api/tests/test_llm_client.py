"""LLM 客户端测试（T1.4 / P1）：验证重试、超时、错误映射、观测与网关回退。"""

from __future__ import annotations

import json
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
    """测试用配置（重试退避为 0，429 重试次数也压到最小以保证用例确定）。"""
    base: dict[str, Any] = {
        "litellm_base_url": "http://llm.test",
        "litellm_master_key": "sk-test",
        "llm_max_retries": 1,
        "llm_retry_backoff_seconds": 0.0,
        "llm_rate_limit_retries": 0,
        "llm_rate_limit_backoff_seconds": 0.0,
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


async def test_empty_content_retries_then_fails_with_clear_code() -> None:
    """推理模型偶发把预算耗在 reasoning 上、正文为空；应退避重试并给明确错误码。"""
    observability, _ = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        payload = success_payload()
        payload["choices"][0]["message"]["content"] = None
        return httpx.Response(200, json=payload)

    client = client_with_handler(
        handler, observability, llm_max_retries=2, llm_rate_limit_retries=2
    )
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == "LLM_EMPTY_CONTENT"
    assert calls["n"] == 3
    await client.aclose()


async def test_empty_content_recovers_on_retry() -> None:
    """第一次空内容、第二次正常时，不应把整次调用判失败。"""
    observability, _ = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            payload = success_payload()
            payload["choices"][0]["message"]["content"] = ""
            return httpx.Response(200, json=payload)
        return httpx.Response(200, json=success_payload())

    client = client_with_handler(handler, observability)
    result = await client.complete([{"role": "user", "content": "hi"}])
    assert result.content.startswith("你好")
    assert calls["n"] == 2
    await client.aclose()


async def test_empty_content_is_not_retried_for_tool_only_reply() -> None:
    """结构异常（连 choices 都没有）不该被当成空内容无限重试。"""
    observability, _ = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"unexpected": "shape"})

    client = client_with_handler(handler, observability)
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == "LLM_BAD_RESPONSE"
    assert calls["n"] == 1
    await client.aclose()


async def test_falls_back_to_secondary_gateway_after_rate_limit() -> None:
    """主网关用量窗口耗尽后应自动切到备用网关，而不是让整批任务失败。"""
    observability, _ = make_observability()
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "host": request.url.host,
                "model": json.loads(request.content.decode("utf-8"))["model"],
            }
        )
        if request.url.host == "primary.test":
            return httpx.Response(429, text="usage window exhausted")
        return httpx.Response(200, json=success_payload())

    settings = make_settings(
        litellm_base_url="https://primary.test/v1",
        llm_rate_limit_retries=0,
        llm_fallback_base_url="https://backup.test/v1",
        llm_fallback_master_key="sk-backup",
        llm_fallback_model="deepseek-v4-flash",
    )
    client = LlmClient(settings, observability, transport=httpx.MockTransport(handler))

    result = await client.complete([{"role": "user", "content": "hi"}], model="kimi-k3")

    assert result.content.startswith("你好")
    assert seen[0]["host"] == "primary.test"
    assert seen[0]["model"] == "kimi-k3"
    assert seen[-1]["host"] == "backup.test"
    assert seen[-1]["model"] == "deepseek-v4-flash", "备用网关应使用映射后的模型名"
    assert client.gateway_name == "fallback"
    await client.aclose()


async def test_no_fallback_configured_keeps_raising_rate_limit() -> None:
    """没有备用网关时仍按原样抛 LLM_RATE_LIMITED。"""
    observability, _ = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, text="usage window exhausted")

    client = client_with_handler(handler, observability, llm_rate_limit_retries=0)
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == "LLM_RATE_LIMITED"
    assert calls["n"] == 1
    assert client.gateway_name == "primary"
    await client.aclose()


def test_upstream_root_strips_v1_suffix() -> None:
    """base_url 带 /v1 时要剥掉，否则 httpx 会丢弃路径部分打到站点首页。"""
    assert LlmClient._upstream_root("https://x.dev/v1") == "https://x.dev"
    assert LlmClient._upstream_root("https://x.dev/v1/") == "https://x.dev"
    assert LlmClient._upstream_root("http://localhost:4000") == "http://localhost:4000"
    assert (
        LlmClient._upstream_root("https://opencode.ai/zen/go/v1") == "https://opencode.ai/zen/go"
    )


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


async def test_rate_limited_retries_then_succeeds() -> None:
    """网关用量窗口限流（429）应退避重试，而不是立刻失败。"""
    observability, _ = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(429, text="usage window exhausted")
        return httpx.Response(200, json=success_payload())

    client = client_with_handler(handler, observability, llm_rate_limit_retries=2)
    result = await client.complete([{"role": "user", "content": "hi"}])
    assert result.content.startswith("你好")
    assert calls["n"] == 3
    await client.aclose()


async def test_rate_limit_retry_budget_is_independent() -> None:
    """429 的重试预算独立于普通 5xx，不应被 llm_max_retries 截断。"""
    observability, _ = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, text="usage window exhausted")

    client = client_with_handler(
        handler, observability, llm_max_retries=1, llm_rate_limit_retries=3
    )
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == "LLM_RATE_LIMITED"
    assert calls["n"] == 4, "应有 1 次初始请求 + 3 次 429 退避重试"
    await client.aclose()


async def test_upstream_500_uses_normal_budget() -> None:
    """5xx 只按 llm_max_retries 重试，不占用 429 的额外预算。"""
    observability, _ = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="boom")

    client = client_with_handler(
        handler, observability, llm_max_retries=1, llm_rate_limit_retries=5
    )
    with pytest.raises(LlmError) as excinfo:
        await client.complete([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == "LLM_UPSTREAM_ERROR"
    assert calls["n"] == 2
    await client.aclose()


async def test_sends_user_agent_and_session_header() -> None:
    """网关要求：必须自带 UA 与 x-opencode-session，缺失会被 400 拒。"""
    observability, _ = make_observability()
    seen: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers)
        return httpx.Response(200, json=success_payload())

    client = client_with_handler(handler, observability)
    await client.complete([{"role": "user", "content": "hi"}])
    headers = seen[0]
    assert headers["User-Agent"] == "xueban-content-pipeline/1.0"
    assert headers["x-opencode-session"].startswith("xueban-")
    await client.aclose()


async def test_session_id_is_stable_across_calls() -> None:
    """同一客户端的会话 ID 保持稳定，便于网关命中提示缓存。"""
    observability, _ = make_observability()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["x-opencode-session"])
        return httpx.Response(200, json=success_payload())

    client = client_with_handler(handler, observability)
    await client.complete([{"role": "user", "content": "第一句"}])
    await client.complete([{"role": "user", "content": "第二句"}])
    assert seen[0] == seen[1]
    assert client.session_id == seen[0]
    await client.aclose()


async def test_bind_session_switches_session() -> None:
    """内容管线按知识点分组时显式绑定会话。"""
    observability, _ = make_observability()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["x-opencode-session"])
        return httpx.Response(200, json=success_payload())

    client = client_with_handler(handler, observability)
    client.bind_session("xueban-g1m-add-within-10")
    await client.complete([{"role": "user", "content": "出题"}])
    assert seen == ["xueban-g1m-add-within-10"]
    assert client.session_id == "xueban-g1m-add-within-10"
    await client.aclose()


async def test_stream_retries_before_first_delta() -> None:
    """流式在吐出任何增量之前允许退避重试。"""
    observability, _ = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="usage window exhausted")
        body = (
            'data: {"choices":[{"delta":{"content":"第一"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"第二"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            200, content=body.encode("utf-8"), headers={"content-type": "text/event-stream"}
        )

    client = client_with_handler(handler, observability, llm_rate_limit_retries=2)
    deltas = [d async for d in client.stream_complete([{"role": "user", "content": "hi"}])]
    assert deltas == ["第一", "第二"]
    assert calls["n"] == 2
    await client.aclose()


async def test_stream_does_not_retry_after_first_delta() -> None:
    """已经产出增量后不再重试，避免调用方收到重复内容。"""
    observability, _ = make_observability()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            body = 'data: {"choices":[{"delta":{"content":"片段"}}]}\n\n'
            return httpx.Response(
                200, content=body.encode("utf-8"), headers={"content-type": "text/event-stream"}
            )
        body = 'data: {"choices":[{"delta":{"content":"重复"}}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(
            200, content=body.encode("utf-8"), headers={"content-type": "text/event-stream"}
        )

    client = client_with_handler(handler, observability, llm_rate_limit_retries=3)
    collected = [d async for d in client.stream_complete([{"role": "user", "content": "hi"}])]
    assert collected == ["片段"]
    assert calls["n"] == 1, "吐出增量后不得重试"
    await client.aclose()


async def test_stream_transport_error_maps_to_unavailable() -> None:
    """建连异常统一映射为 LLM_UNAVAILABLE，而不是裸抛 httpx 错误。"""
    observability, _ = make_observability()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection reset")

    client = client_with_handler(handler, observability, llm_max_retries=1)
    with pytest.raises(LlmError) as excinfo:
        [d async for d in client.stream_complete([{"role": "user", "content": "hi"}])]
    assert excinfo.value.code == "LLM_UNAVAILABLE"
    await client.aclose()


async def test_stream_error_status_is_mapped() -> None:
    """流式收到的错误状态码与非流式共用同一套错误码映射。"""
    observability, _ = make_observability()
    client = client_with_handler(
        lambda request: httpx.Response(401, text='{"error":{"message":"bad key"}}'),
        observability,
    )
    with pytest.raises(LlmError) as excinfo:
        [d async for d in client.stream_complete([{"role": "user", "content": "hi"}])]
    assert excinfo.value.code == "LLM_AUTH_FAILED"
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
