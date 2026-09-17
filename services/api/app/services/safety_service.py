"""内容安全服务：供应商抽象 + 本地敏感词兜底。"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import SafetyEvent

logger = logging.getLogger("xueban.safety")

WORDLIST_PATH = Path(__file__).resolve().parent.parent / "data" / "sensitive_words.txt"

ACTION_PASSED = "passed"
ACTION_BLOCKED = "blocked"


@dataclass(slots=True)
class SafetyDecision:
    """安全检查结果。"""

    allowed: bool
    action: str
    provider: str
    categories: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)


class SafetyProvider(Protocol):
    """内容安全供应商接口。"""

    name: str

    async def check(self, text: str) -> SafetyDecision:
        """检查一段文本。"""
        ...


class SafetyProviderError(Exception):
    """供应商不可用（触发本地兜底）。"""


def load_local_words() -> dict[str, list[str]]:
    """加载本地敏感词表：返回 {分类: [词...]}。"""
    categories: dict[str, list[str]] = {}
    if not WORDLIST_PATH.exists():
        return categories
    current = "general"
    for raw_line in WORDLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            categories.setdefault(current, [])
            continue
        categories.setdefault(current, []).append(line)
    return categories


class LocalWordProvider:
    """本地敏感词兜底（永远可用，不与外部网络耦合）。"""

    name = "local"

    def __init__(self) -> None:
        self._categories = load_local_words()

    async def check(self, text: str) -> SafetyDecision:
        """基于词表的命中检查。"""
        lowered = text.lower()
        matched: list[str] = []
        hit_categories: set[str] = set()
        for category, words in self._categories.items():
            for word in words:
                if word.lower() in lowered:
                    matched.append(word)
                    hit_categories.add(category)
        if matched:
            return SafetyDecision(
                allowed=False,
                action=ACTION_BLOCKED,
                provider=self.name,
                categories=sorted(hit_categories),
                matched=matched,
            )
        return SafetyDecision(allowed=True, action=ACTION_PASSED, provider=self.name)


class YidunProvider:
    """网易易盾对接骨架（M1 仅提供请求封装与配置校验，签名按官方文档补齐）。

    未配置密钥时抛 SafetyProviderError，由 SafetyService 触发本地兜底。
    """

    name = "yidun"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def check(self, text: str) -> SafetyDecision:
        """调用易盾文本检测接口。"""
        if not self._settings.yidun_secret_id or not self._settings.yidun_secret_key:
            raise SafetyProviderError("易盾密钥未配置")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    "https://as.dun.163.com/v5/text/check",
                    data={"secretId": self._settings.yidun_secret_id, "content": text},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise SafetyProviderError(f"易盾接口异常：{exc}") from exc
        # 响应结构按易盾 v5：result.suggest(0 通过 / 1 嫌疑 / 2 不通过)
        suggest = int(payload.get("result", {}).get("suggest", 0))
        allowed = suggest == 0
        return SafetyDecision(
            allowed=allowed,
            action=ACTION_PASSED if allowed else ACTION_BLOCKED,
            provider=self.name,
            categories=[] if allowed else ["remote_flagged"],
        )


class SafetyService:
    """统一内容安全入口：远程供应商优先，失败时按配置回退本地词表。"""

    def __init__(
        self,
        settings: Settings,
        *,
        primary: SafetyProvider | None = None,
        fallback: SafetyProvider | None = None,
    ) -> None:
        self._settings = settings
        self._fallback = fallback or LocalWordProvider()
        if primary is not None:
            self._primary = primary
        elif settings.safety_provider == "yidun":
            self._primary = YidunProvider(settings)
        else:
            self._primary = self._fallback

    @property
    def fallback_provider(self) -> SafetyProvider:
        """兜底供应商（测试/维护使用）。"""
        return self._fallback

    async def check(self, text: str) -> SafetyDecision:
        """执行检查（含兜底）。"""
        try:
            return await self._primary.check(text)
        except SafetyProviderError as exc:
            logger.warning("内容安全主供应商不可用，回退本地词表：%s", exc)
            if not self._settings.safety_fallback_local:
                raise
            decision = await self._fallback.check(text)
            decision.provider = f"{decision.provider}-fallback"
            return decision
        except Exception:
            logger.exception("内容安全检查异常，回退本地词表")
            if not self._settings.safety_fallback_local:
                raise
            decision = await self._fallback.check(text)
            decision.provider = f"{decision.provider}-fallback"
            return decision

    async def check_and_record(
        self,
        session: AsyncSession,
        *,
        text: str,
        scene: str,
        user_id: uuid.UUID | None,
    ) -> SafetyDecision:
        """检查并把阻断事件落库（F-42 数据源）。"""
        decision = await self.check(text)
        if not decision.allowed:
            session.add(
                SafetyEvent(
                    user_id=user_id,
                    scene=scene,
                    provider=decision.provider,
                    action=decision.action,
                    categories={"categories": decision.categories, "matched": decision.matched},
                    snippet=text[:200],
                )
            )
            await session.flush()
        return decision
