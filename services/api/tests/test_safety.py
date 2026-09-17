"""内容安全测试（T1.7）：20 条违规样本 100% 拦截（兜底模式）+ 接口与落库。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models import SafetyEvent
from app.services.safety_service import (
    LocalWordProvider,
    SafetyDecision,
    SafetyProviderError,
    SafetyService,
    load_local_words,
)
from tests.helpers import headers_of, register


def _violation_samples(limit: int = 20) -> list[str]:
    """从词表生成 20 条违规样本。"""
    samples: list[str] = []
    for words in load_local_words().values():
        for word in words:
            samples.append(f"在群里有人讨论{word}的事情，我要不要参与？")
            if len(samples) >= limit:
                return samples
    return samples


async def test_wordlist_loaded() -> None:
    categories = load_local_words()
    assert len(categories) >= 5
    assert sum(len(words) for words in categories.values()) >= 30


async def test_twenty_violation_samples_all_blocked() -> None:
    service = SafetyService(settings)
    samples = _violation_samples(20)
    assert len(samples) == 20
    blocked = 0
    for sample in samples:
        decision = await service.check(sample)
        if not decision.allowed and decision.action == "blocked":
            blocked += 1
    assert blocked == 20, f"20 条违规样本应全部拦截，实际 {blocked}"


async def test_benign_texts_pass() -> None:
    service = SafetyService(settings)
    benign = [
        "老师，这道二次函数题为什么要先配方？",
        "我想复习一下今天的英语单词。",
        "明天要考试了，我有点紧张，能给我一些建议吗？",
        "帮我生成三道一次函数的练习题。",
        "这篇文章的论点是环境保护的重要性。",
    ]
    for text in benign:
        decision = await service.check(text)
        assert decision.allowed is True


async def test_remote_provider_failure_falls_back_to_local() -> None:
    class BrokenProvider:
        name = "broken"

        async def check(self, text: str) -> SafetyDecision:
            raise SafetyProviderError("模拟远程不可用")

    service = SafetyService(settings, primary=BrokenProvider())
    decision = await service.check("哪里有赌博网站？")
    assert decision.allowed is False
    assert decision.provider == "local-fallback"


async def test_fallback_disabled_propagates_error() -> None:
    class BrokenProvider:
        name = "broken"

        async def check(self, text: str) -> SafetyDecision:
            raise SafetyProviderError("模拟远程不可用")

    strict_settings = settings.model_copy(update={"safety_fallback_local": False})
    service = SafetyService(strict_settings, primary=BrokenProvider())
    try:
        await service.check("正常文本")
        raised = False
    except SafetyProviderError:
        raised = True
    assert raised is True


async def test_local_provider_directly() -> None:
    provider = LocalWordProvider()
    decision = await provider.check("正常学习内容")
    assert decision.allowed is True
    assert decision.provider == "local"


async def test_safety_check_endpoint_blocks_and_records(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    tokens = await register(client)
    response = await client.post(
        "/v1/safety/check",
        json={"text": "求推荐一个赌博网站", "scene": "chat"},
        headers=headers_of(tokens),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["allowed"] is False
    assert body["action"] == "blocked"

    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(SafetyEvent))
    assert count == 1


async def test_safety_check_endpoint_passes_benign(client: AsyncClient) -> None:
    tokens = await register(client)
    response = await client.post(
        "/v1/safety/check",
        json={"text": "请帮我讲解这道几何题", "scene": "tutor"},
        headers=headers_of(tokens),
    )
    assert response.status_code == 200
    assert response.json()["allowed"] is True


async def test_safety_check_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/v1/safety/check", json={"text": "你好", "scene": "chat"})
    assert response.status_code == 401


# ---------- 易盾供应商骨架与词表异常 ----------


class _FakeYidunResponse:
    def __init__(self, suggest: int) -> None:
        self._suggest = suggest

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"result": {"suggest": self._suggest}}


class _FakeAsyncClient:
    suggest = 0

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def post(self, url: str, **kwargs: object) -> _FakeYidunResponse:
        return _FakeYidunResponse(_FakeAsyncClient.suggest)


async def test_yidun_provider_blocks_when_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import safety_service as module
    from app.services.safety_service import YidunProvider

    monkeypatch.setattr(module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.suggest = 2
    provider = YidunProvider(
        settings.model_copy(update={"yidun_secret_id": "id", "yidun_secret_key": "key"})
    )
    decision = await provider.check("违规内容")
    assert decision.allowed is False
    assert decision.provider == "yidun"


async def test_yidun_provider_passes_when_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import safety_service as module
    from app.services.safety_service import YidunProvider

    monkeypatch.setattr(module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.suggest = 0
    provider = YidunProvider(
        settings.model_copy(update={"yidun_secret_id": "id", "yidun_secret_key": "key"})
    )
    decision = await provider.check("正常内容")
    assert decision.allowed is True


async def test_yidun_without_keys_falls_back() -> None:
    from app.services.safety_service import YidunProvider

    provider = YidunProvider(
        settings.model_copy(update={"yidun_secret_id": "", "yidun_secret_key": ""})
    )
    service = SafetyService(settings, primary=provider)
    decision = await service.check("卖淫嫖娼是违法的")
    assert decision.allowed is False
    assert decision.provider == "local-fallback"


async def test_missing_wordlist_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    from app.services import safety_service as module

    monkeypatch.setattr(module, "WORDLIST_PATH", Path("does-not-exist.txt"))
    provider = LocalWordProvider()
    decision = await provider.check("赌博")
    assert decision.allowed is True
