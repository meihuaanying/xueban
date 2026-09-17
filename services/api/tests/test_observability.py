"""LLM 观测适配层测试（T1.5）：注入假客户端验证记录行为与容错。"""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.services.observability import ObservabilityService


class FakeObservation:
    """假观测对象。"""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.ended = False

    def end(self) -> None:
        self.ended = True


class FakeLangfuse:
    """假 Langfuse 客户端。"""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.observations: list[FakeObservation] = []
        self.events: list[dict[str, Any]] = []
        self.flushed = 0

    def start_observation(self, **kwargs: Any) -> FakeObservation:
        if self.fail:
            raise RuntimeError("langfuse down")
        observation = FakeObservation(**kwargs)
        self.observations.append(observation)
        return observation

    def create_event(self, **kwargs: Any) -> None:
        if self.fail:
            raise RuntimeError("langfuse down")
        self.events.append(kwargs)

    def flush(self) -> None:
        self.flushed += 1


def make_settings(**overrides: Any) -> Settings:
    """测试配置。"""
    base: dict[str, Any] = {"langfuse_public_key": "", "langfuse_secret_key": ""}
    base.update(overrides)
    return Settings(**base)


def test_disabled_without_keys() -> None:
    service = ObservabilityService(make_settings())
    assert service.enabled is False
    # 空实现：调用不抛异常
    service.record_llm_call(
        trace_id="t" * 32, name="x", model="m", input_payload=[], output_payload=None
    )
    service.record_event(trace_id=None, name="e")
    service.flush()


def test_record_llm_call_fields() -> None:
    fake = FakeLangfuse()
    service = ObservabilityService(make_settings(), client=fake)
    assert service.enabled is True
    service.record_llm_call(
        trace_id="a" * 32,
        name="tutor.hint",
        model="deepseek-chat",
        input_payload=[{"role": "user", "content": "x"}],
        output_payload="提示内容",
        usage={"total_tokens": 10},
        latency_ms=321,
    )
    assert len(fake.observations) == 1
    observation = fake.observations[0]
    assert observation.ended is True
    assert observation.kwargs["trace_context"] == {"trace_id": "a" * 32}
    assert observation.kwargs["as_type"] == "generation"
    assert observation.kwargs["output"] == "提示内容"
    assert observation.kwargs["metadata"] == {"latency_ms": 321}
    assert observation.kwargs["level"] == "DEFAULT"


def test_record_llm_call_error_level() -> None:
    fake = FakeLangfuse()
    service = ObservabilityService(make_settings(), client=fake)
    service.record_llm_call(
        trace_id=None,
        name="llm.chat",
        model="deepseek-chat",
        input_payload=[],
        output_payload=None,
        error="LLM_UNAVAILABLE: 模型服务不可用",
    )
    observation = fake.observations[0]
    assert observation.kwargs["level"] == "ERROR"
    assert observation.kwargs["status_message"].startswith("LLM_UNAVAILABLE")
    assert observation.kwargs["trace_context"] is None


def test_record_event_fields() -> None:
    fake = FakeLangfuse()
    service = ObservabilityService(make_settings(), client=fake)
    service.record_event(
        trace_id="b" * 32,
        name="billing.mock_pay",
        input_payload={"checkout_id": "x"},
        output_payload={"plan": "pro"},
        metadata={"amount_cents": 3900},
    )
    assert len(fake.events) == 1
    event = fake.events[0]
    assert event["name"] == "billing.mock_pay"
    assert event["trace_context"] == {"trace_id": "b" * 32}


def test_langfuse_failure_does_not_propagate() -> None:
    service = ObservabilityService(make_settings(), client=FakeLangfuse(fail=True))
    service.record_llm_call(
        trace_id=None, name="x", model="m", input_payload=[], output_payload=None
    )
    service.record_event(trace_id=None, name="e")
    service.flush()


def test_flush_delegates() -> None:
    fake = FakeLangfuse()
    service = ObservabilityService(make_settings(), client=fake)
    service.flush()
    assert fake.flushed == 1


def test_real_client_init_with_keys(monkeypatch: object) -> None:
    """配置了密钥时尝试真实初始化（此处以假构造器替换 SDK）。"""

    class FakeLangfuseClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    monkeypatch.setattr("langfuse.Langfuse", FakeLangfuseClient)  # type: ignore[attr-defined]
    service = ObservabilityService(
        make_settings(langfuse_public_key="pk-test", langfuse_secret_key="sk-test")
    )
    assert service.enabled is True


def test_real_client_init_failure_degrades(monkeypatch: object) -> None:
    """SDK 初始化失败时降级为空实现，不影响主流程。"""

    class BrokenLangfuse:
        def __init__(self, **kwargs: Any) -> None:
            raise RuntimeError("初始化失败")

    monkeypatch.setattr("langfuse.Langfuse", BrokenLangfuse)  # type: ignore[attr-defined]
    service = ObservabilityService(
        make_settings(langfuse_public_key="pk-test", langfuse_secret_key="sk-test")
    )
    assert service.enabled is False
    service.record_llm_call(trace_id=None, name="x", model="m", input_payload=[])
