"""告警投递服务（T7.4：webhook 可接飞书机器人；未配置时记录 skipped）。"""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import utcnow
from app.models import AlertRecord


async def send_alert(
    session: AsyncSession,
    *,
    kind: str,
    payload: dict[str, Any],
    webhook_url: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AlertRecord:
    """投递告警：POST JSON 到 webhook；失败记录错误但不影响主流程。"""
    target = webhook_url if webhook_url is not None else settings.alert_webhook_url
    record = AlertRecord(kind=kind, payload=payload, target_url=target or "")
    if not target:
        record.status = "skipped"
        session.add(record)
        await session.flush()
        return record

    body = {"kind": kind, "payload": payload, "ts": utcnow().isoformat()}
    try:
        async with httpx.AsyncClient(
            timeout=settings.alert_webhook_timeout_seconds, transport=transport
        ) as client:
            response = await client.post(target, json=body)
        record.response_code = response.status_code
        record.status = "sent" if response.status_code < 400 else "failed"
        record.sent_at = utcnow()
        if response.status_code >= 400:
            record.error = response.text[:200]
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        record.status = "failed"
        record.error = str(exc)[:200]
    session.add(record)
    await session.flush()
    return record
