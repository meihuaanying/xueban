"""LLM 客户端：经 LiteLLM 网关调用主模型（fallback 链由网关配置兜底）。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings
from app.errors import LlmError
from app.services.observability import ObservabilityService

logger = logging.getLogger("xueban.llm")


@dataclass(slots=True)
class LlmResult:
    """一次补全调用结果。"""

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


def _visible_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """截断超长消息（观测用，避免超大 payload）。"""
    return [
        {**message, "content": message.get("content", "")[:2000]} for message in messages
    ]


# mock 提供商的确定性讲解文本（按三层提示口径，供离线开发/E2E/CI 使用）
MOCK_HINT_TEXTS: dict[int, str] = {
    1: (
        "思路提示：先看题目的已知条件与所求量，回忆与之相关的定义和公式，"
        "想一想它们之间是什么关系。可以先列出已知条件，再判断需要用到哪个知识点。"
    ),
    2: (
        "关键步骤：第一步，整理已知条件并写出对应关系式；第二步，选择合适的公式代入；"
        "第三步，先化简再计算，注意符号与单位。请先自己完成最后的计算。"
    ),
    3: (
        "完整解答：按已知条件逐步代入公式，化简后得到结果（本段为 mock 演示内容，"
        "真实讲解由模型生成）。方法要点：先明确所求量，再选择公式，最后规范计算并检验。"
        "请用自己的话复述一遍思路。"
    ),
}


def _mock_level(messages: list[dict[str, str]]) -> int | None:
    """从当前请求（最后一条 user 消息）识别求助层级。

    只扫描 user 消息：系统提示词中也出现「第 3 层」等字样，不能作为判断依据。
    """
    user_texts = [
        message.get("content", "") for message in messages if message.get("role") == "user"
    ]
    text = user_texts[-1] if user_texts else ""
    for level in (3, 2, 1):
        if f"第 {level} 层" in text:
            return level
    return None


def _mock_text(messages: list[dict[str, str]]) -> str:
    """按上下文生成确定性 mock 输出。"""
    level = _mock_level(messages)
    if level is not None:
        return MOCK_HINT_TEXTS[level]
    text = "\n".join(message.get("content", "") for message in messages)
    if "JSON" in text or "json" in text:
        return "{}"
    return "（mock 输出）这是学伴离线模式返回的确定性内容，用于开发与自动化测试。"


class LlmClient:
    """与 LiteLLM 网关通信的异步客户端。

    - 超时：settings.llm_timeout_seconds
    - 重试：网络类错误与 5xx 重试 llm_max_retries 次；429（网关用量窗口限流）
      单独用 llm_rate_limit_retries 次预算与更长的退避基数（限流不是故障）
    - 会话：带 x-opencode-session 与自定义 User-Agent，网关据此路由与命中提示缓存；
      同一生成任务跨重试保持同一 session_id，可用 bind_session 显式绑定
    - 降级：主备模型切换由 LiteLLM 的 fallbacks 配置负责，本客户端只消费网关结果
    - 观测：每次调用写入 Langfuse（含失败）
    """

    def __init__(
        self,
        settings: Settings,
        observability: ObservabilityService,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._observability = observability
        self._client = httpx.AsyncClient(
            base_url=settings.litellm_base_url.rstrip("/"),
            timeout=settings.llm_timeout_seconds,
            headers={
                "Authorization": f"Bearer {settings.litellm_master_key}",
                # 网关要求：必须自带 UA（不能是 httpx 默认值），并带稳定的会话 ID，
                # 否则报 MissingSessionID（HTTP 400）且无法命中提示缓存。
                "User-Agent": settings.llm_user_agent,
                "x-opencode-session": f"{settings.llm_session_prefix}-{uuid.uuid4().hex[:16]}",
            },
            transport=transport,
        )

    async def aclose(self) -> None:
        """关闭底层连接。"""
        await self._client.aclose()

    @property
    def session_id(self) -> str:
        """当前会话 ID：同一「生成任务」跨重试保持不变，便于网关命中缓存。"""
        return str(self._client.headers["x-opencode-session"])

    def bind_session(self, session_id: str) -> None:
        """把后续请求绑定到指定会话（内容管线按知识点分组时复用缓存用）。"""
        self._client.headers["x-opencode-session"] = session_id

    def _should_retry(self, status_code: int) -> bool:
        """429 是用量窗口限流，5xx 是上游抖动，两者都值得退避重试。"""
        return status_code == 429 or status_code >= 500

    async def _sleep_backoff(self, attempt: int, *, rate_limited: bool) -> None:
        """指数退避；命中 429 时用更长、更保守的基数。"""
        base = (
            self._settings.llm_rate_limit_backoff_seconds
            if rate_limited
            else self._settings.llm_retry_backoff_seconds
        )
        await asyncio.sleep(base * (2**attempt))

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        trace_id: str | None = None,
        name: str = "llm.chat",
    ) -> LlmResult:
        """调用 Chat Completions；失败抛出带明确错误码的 LlmError。"""
        if self._settings.llm_provider == "mock":
            return self._mock_complete(messages, name=name, trace_id=trace_id)
        target_model = model or self._settings.llm_default_model
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        # 429（网关用量窗口限流）与 5xx（上游抖动）共用同一个循环，但 429 有独立的
        # 重试预算与更长的退避基数——限流不是故障，重试要更保守。
        attempts = (
            max(self._settings.llm_max_retries, self._settings.llm_rate_limit_retries) + 1
        )
        last_error: Exception | None = None
        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                response = await self._client.post("/v1/chat/completions", json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                logger.warning("LLM 网络异常（第 %s 次）：%s", attempt + 1, exc)
                if attempt < attempts - 1:
                    await self._sleep_backoff(attempt, rate_limited=False)
                    continue
                break

            latency_ms = int((time.perf_counter() - started) * 1000)
            if response.status_code == 429:
                last_error = LlmError(
                    "模型用量窗口已用尽，请稍后重试", code="LLM_RATE_LIMITED", status_code=429
                )
                logger.warning("LLM 触发用量窗口限流（第 %s 次）", attempt + 1)
                if attempt < self._settings.llm_rate_limit_retries:
                    await self._sleep_backoff(attempt, rate_limited=True)
                    continue
                break

            if response.status_code >= 500:
                last_error = LlmError(
                    "模型服务暂时不可用，请稍后重试", code="LLM_UPSTREAM_ERROR", status_code=503
                )
                logger.warning("LLM 上游 %s（第 %s 次）", response.status_code, attempt + 1)
                if attempt < self._settings.llm_max_retries:
                    await self._sleep_backoff(attempt, rate_limited=False)
                    continue
                break

            if response.status_code >= 400:
                error = self._map_client_error(response, target_model)
                self._observability.record_llm_call(
                    trace_id=trace_id,
                    name=name,
                    model=target_model,
                    input_payload=_visible_messages(messages),
                    output_payload=None,
                    latency_ms=latency_ms,
                    error=f"{error.code}: {error.message}",
                )
                raise error

            data: dict[str, Any] = response.json()
            content = self._extract_content(data)
            usage = self._extract_usage(data)
            result = LlmResult(
                content=content,
                model=str(data.get("model", target_model)),
                usage=usage,
                latency_ms=latency_ms,
                raw={key: data.get(key) for key in ("id", "model", "finish_reason")},
            )
            self._observability.record_llm_call(
                trace_id=trace_id,
                name=name,
                model=result.model,
                input_payload=_visible_messages(messages),
                output_payload=content,
                usage=usage,
                latency_ms=latency_ms,
            )
            return result

        error = last_error if isinstance(last_error, LlmError) else LlmError(
            "模型服务不可用，请稍后重试", code="LLM_UNAVAILABLE", status_code=503
        )
        self._observability.record_llm_call(
            trace_id=trace_id,
            name=name,
            model=target_model,
            input_payload=_visible_messages(messages),
            output_payload=None,
            error=f"{error.code}: {error.message}",
        )
        raise error

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        """从 LiteLLM 错误响应中提取可读细节（兼容 OpenAI 错误结构）。"""
        try:
            payload = response.json()
        except ValueError:
            return response.text[:200]
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str):
                    return message[:200]
            message = payload.get("message")
            if isinstance(message, str):
                return message[:200]
        return response.text[:200]

    @staticmethod
    def _map_client_error_parts(status_code: int, text: str, model: str) -> LlmError:
        """按状态码构造明确错误（JSON/流式共用）。"""
        detail = LlmClient._error_detail_from_text(text)
        if status_code == 401:
            return LlmError(
                f"模型网关鉴权失败：请检查 LITELLM_MASTER_KEY 或供应商 API Key（{detail}）",
                code="LLM_AUTH_FAILED",
                status_code=503,
            )
        if status_code == 404:
            return LlmError(
                f"模型不存在：{model}（请检查 LiteLLM 模型配置）",
                code="LLM_MODEL_NOT_FOUND",
                status_code=503,
            )
        if status_code == 429:
            return LlmError(
                "模型调用频率受限，请稍后重试", code="LLM_RATE_LIMITED", status_code=503
            )
        return LlmError(
            f"模型请求被拒绝（{status_code}）：{detail}",
            code="LLM_REQUEST_REJECTED",
            status_code=503,
        )

    @staticmethod
    def _error_detail_from_text(text: str) -> str:
        """从错误文本中提取可读细节。"""
        try:
            payload = json.loads(text)
        except ValueError:
            return text[:200]
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str):
                    return message[:200]
            message = payload.get("message")
            if isinstance(message, str):
                return message[:200]
        return text[:200]

    @staticmethod
    def _map_client_error(response: httpx.Response, model: str) -> LlmError:
        """将网关 4xx 映射为明确错误（非流式）。"""
        if response.status_code == 401:
            detail = LlmClient._error_detail(response)
            return LlmError(
                f"模型网关鉴权失败：请检查 LITELLM_MASTER_KEY 或供应商 API Key（{detail}）",
                code="LLM_AUTH_FAILED",
                status_code=503,
            )
        if response.status_code == 404:
            return LlmError(
                f"模型不存在：{model}（请检查 LiteLLM 模型配置）",
                code="LLM_MODEL_NOT_FOUND",
                status_code=503,
            )
        if response.status_code == 429:
            return LlmError(
                "模型调用频率受限，请稍后重试", code="LLM_RATE_LIMITED", status_code=503
            )
        detail = LlmClient._error_detail(response)
        return LlmError(
            f"模型请求被拒绝（{response.status_code}）：{detail}",
            code="LLM_REQUEST_REJECTED",
            status_code=503,
        )

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        """从 Chat Completions 响应提取文本。"""
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmError(
                "模型返回结构异常", code="LLM_BAD_RESPONSE", status_code=502
            ) from exc
        if not isinstance(content, str):
            raise LlmError("模型返回内容为空", code="LLM_BAD_RESPONSE", status_code=502)
        return content

    @staticmethod
    def _extract_usage(data: dict[str, Any]) -> dict[str, int]:
        """提取 token 用量。"""
        usage = data.get("usage")
        if not isinstance(usage, dict):
            return {}
        return {
            key: int(value)
            for key, value in usage.items()
            if isinstance(value, int)
            and key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }

    def _mock_complete(
        self,
        messages: list[dict[str, str]],
        *,
        name: str,
        trace_id: str | None,
    ) -> LlmResult:
        """mock 提供商：返回确定性文本（不发起网络请求）。"""
        content = _mock_text(messages)
        result = LlmResult(content=content, model="mock", usage={}, latency_ms=0)
        self._observability.record_llm_call(
            trace_id=trace_id,
            name=name,
            model="mock",
            input_payload=_visible_messages(messages),
            output_payload=content,
            latency_ms=0,
        )
        return result

    async def _mock_stream(
        self,
        messages: list[dict[str, str]],
        *,
        name: str,
        trace_id: str | None,
    ) -> AsyncIterator[str]:
        """mock 流式：按固定步长逐段产出，模拟真实增量渲染。"""
        content = _mock_text(messages)
        step = 6
        for index in range(0, len(content), step):
            yield content[index : index + step]
            await asyncio.sleep(0.01)
        self._observability.record_llm_call(
            trace_id=trace_id,
            name=name,
            model="mock",
            input_payload=_visible_messages(messages),
            output_payload=content,
            latency_ms=0,
        )

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        trace_id: str | None = None,
        name: str = "llm.chat.stream",
    ) -> AsyncIterator[str]:
        """流式补全：逐段产出内容增量（SSE；异常映射与非流式一致）。"""
        if self._settings.llm_provider == "mock":
            async for mock_delta in self._mock_stream(messages, name=name, trace_id=trace_id):
                yield mock_delta
            return
        target_model = model or self._settings.llm_default_model
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        started = time.perf_counter()
        collected: list[str] = []
        error_text: str | None = None
        attempts = max(self._settings.llm_max_retries, self._settings.llm_rate_limit_retries) + 1
        try:
            for attempt in range(attempts):
                try:
                    async for delta in self._stream_once(payload, target_model, collected):
                        yield delta
                    return
                except (httpx.TimeoutException, httpx.TransportError, LlmError) as exc:
                    # 已经吐出过增量就不能重试，否则调用方会收到重复内容
                    if collected:
                        error_text = f"{getattr(exc, 'code', 'LLM_ERROR')}: {exc}"
                        raise
                    error_text = f"{getattr(exc, 'code', 'LLM_ERROR')}: {exc}"
                    rate_limited = isinstance(exc, LlmError) and exc.code == "LLM_RATE_LIMITED"
                    logger.warning("LLM 流式失败（第 %s 次）：%s", attempt + 1, exc)
                    if attempt < attempts - 1:
                        await self._sleep_backoff(attempt, rate_limited=rate_limited)
                        continue
                    raise
            raise LlmError(
                "模型服务暂时不可用，请稍后重试", code="LLM_UPSTREAM_ERROR", status_code=503
            )
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            self._observability.record_llm_call(
                trace_id=trace_id,
                name=name,
                model=target_model,
                input_payload=_visible_messages(messages),
                output_payload="".join(collected) if collected else None,
                latency_ms=latency_ms,
                error=error_text,
            )

    async def _stream_once(
        self,
        payload: dict[str, Any],
        target_model: str,
        collected: list[str],
    ) -> AsyncIterator[str]:
        """单次流式请求；增量写入 collected，供上层判断是否还能安全重试。"""
        try:
            async with self._client.stream(
                "POST", "/v1/chat/completions", json=payload
            ) as response:
                if response.status_code == 429:
                    raise LlmError(
                        "模型用量窗口已用尽，请稍后重试",
                        code="LLM_RATE_LIMITED",
                        status_code=429,
                    )
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", errors="ignore")
                    raise self._map_client_error_parts(response.status_code, body, target_model)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk: dict[str, Any] = json.loads(data)
                    except ValueError:
                        continue
                    choices = chunk.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    first = choices[0]
                    delta = first.get("delta") if isinstance(first, dict) else None
                    content = delta.get("content") if isinstance(delta, dict) else None
                    if isinstance(content, str) and content:
                        collected.append(content)
                        yield content
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise LlmError(
                "模型服务不可用，请稍后重试", code="LLM_UNAVAILABLE", status_code=503
            ) from exc
