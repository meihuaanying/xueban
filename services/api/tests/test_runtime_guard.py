"""生产启动校验：学生可见的生成/评测服务不得静默走 mock。"""

from __future__ import annotations

import pytest

from app.config import Settings, validate_runtime


def _production(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "environment": "production",
        "llm_provider": "litellm",
        "safety_provider": "yidun",
        "embedding_provider": "siliconflow",
        "rerank_provider": "siliconflow",
        "tts_provider": "azure",
        "speaking_provider": "azure",
        "jwt_secret": "prod-secret-not-the-dev-default",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_production_rejects_mock_providers() -> None:
    settings = _production(llm_provider="mock", speaking_provider="mock")
    with pytest.raises(RuntimeError) as caught:
        validate_runtime(settings)
    message = str(caught.value)
    assert "LLM_PROVIDER" in message
    assert "SPEAKING_PROVIDER" in message


def test_production_rejects_default_jwt_secret() -> None:
    settings = _production(jwt_secret="dev-only-jwt-secret-please-change-0123456789abcdef")
    with pytest.raises(RuntimeError, match="JWT"):
        validate_runtime(settings)


def test_production_rejects_unknown_provider_values() -> None:
    """拼写错误/未知值在工厂里会静默回退 mock，启动校验必须拦截。"""
    settings = _production(embedding_provider="SiliconFlow")
    with pytest.raises(RuntimeError) as caught:
        validate_runtime(settings)
    assert "EMBEDDING_PROVIDER" in str(caught.value)


def test_production_with_real_providers_passes() -> None:
    validate_runtime(_production())


def test_development_allows_mock() -> None:
    validate_runtime(Settings(environment="development", llm_provider="mock"))
