"""LLM 全链路观测：Langfuse 适配层（未配置密钥时自动降级为空实现）。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger("xueban.observability")


class ObservabilityService:
    """Langfuse 封装：任何异常都不能影响主流程；未配置时为空实现。"""

    def __init__(self, settings: Settings, *, client: Any = None) -> None:
        self._settings = settings
        self._client: Any = client
        if self._client is None and settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
            except Exception:
                logger.exception("Langfuse 初始化失败，观测功能关闭")
                self._client = None

    @property
    def enabled(self) -> bool:
        """是否启用观测。"""
        return self._client is not None

    def record_llm_call(
        self,
        *,
        trace_id: str | None,
        name: str,
        model: str,
        input_payload: Any,
        output_payload: Any = None,
        usage: dict[str, int] | None = None,
        latency_ms: int | None = None,
        version: str | None = None,
        error: str | None = None,
    ) -> None:
        """记录一次 LLM 调用（generation 观测）。"""
        if self._client is None:
            return
        try:
            trace_context = {"trace_id": trace_id} if trace_id else None
            observation = self._client.start_observation(
                trace_context=trace_context,
                name=name,
                as_type="generation",
                input=input_payload,
                output=output_payload,
                model=model,
                version=version,
                usage_details=usage,
                level="ERROR" if error else "DEFAULT",
                status_message=error,
                metadata={"latency_ms": latency_ms},
            )
            observation.end()
        except Exception:
            logger.warning("Langfuse 记录 LLM 调用失败（已忽略）", exc_info=True)

    def record_event(
        self,
        *,
        trace_id: str | None,
        name: str,
        input_payload: Any = None,
        output_payload: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录业务事件（非 LLM 调用）。"""
        if self._client is None:
            return
        try:
            trace_context = {"trace_id": trace_id} if trace_id else None
            self._client.create_event(
                trace_context=trace_context,
                name=name,
                input=input_payload,
                output=output_payload,
                metadata=metadata,
            )
        except Exception:
            logger.warning("Langfuse 记录事件失败（已忽略）", exc_info=True)

    def flush(self) -> None:
        """刷新缓冲（进程退出前调用）。"""
        if self._client is None:
            return
        try:
            self._client.flush()
        except Exception:
            logger.warning("Langfuse flush 失败（已忽略）", exc_info=True)
