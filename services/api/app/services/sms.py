"""短信服务抽象：mock 先行，真实供应商按接口替换（仅改环境变量）。"""

from __future__ import annotations

import logging
from typing import Protocol

from app.config import Settings

logger = logging.getLogger("xueban.sms")


class SmsProvider(Protocol):
    """短信供应商接口。"""

    name: str

    async def send_code(self, phone: str, code: str, purpose: str) -> None:
        """发送验证码。"""
        ...


class MockSmsProvider:
    """占位实现：不真实发送，仅记录日志（验证码落库可查）。"""

    name = "mock"

    async def send_code(self, phone: str, code: str, purpose: str) -> None:
        logger.info(
            "mock 短信验证码",
            extra={"context": {"phone": _mask_phone(phone), "purpose": purpose, "code": code}},
        )


def get_sms_provider(settings: Settings) -> SmsProvider:
    """按配置选择供应商；真实供应商接入时在此扩展。"""
    if settings.sms_provider == "mock":
        return MockSmsProvider()
    raise NotImplementedError(f"暂不支持的短信供应商：{settings.sms_provider}")


def _mask_phone(phone: str) -> str:
    """手机号脱敏（日志用）。"""
    if len(phone) >= 11:
        return f"{phone[:3]}****{phone[-4:]}"
    return "***"
