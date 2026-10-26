"""防沉迷闸门依赖测试（T-003：require_not_locked 服务端强制）。"""

from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI
from httpx import AsyncClient

from app.api.deps import require_not_locked
from app.models import User
from tests.helpers import headers_of, register


async def test_require_not_locked_blocks_over_limit_child(
    app: FastAPI, client: AsyncClient
) -> None:
    """超过当日时长后，挂载 require_not_locked 的路由返回 423。"""

    @app.get("/v1/test-guardian/probe")
    async def probe(user: User = Depends(require_not_locked)) -> dict[str, str]:
        return {"user_id": str(user.id)}

    # 家长口令逐次随机生成，避免在源码中出现凭据字面量
    parent_password = "pw-" + uuid.uuid4().hex
    parent = await register(client, role="parent", password=parent_password)
    child = await register(client)

    send = await client.post(
        "/v1/auth/sms/send", json={"phone": child["phone"], "purpose": "bind"}
    )
    assert send.status_code == 200, send.text
    bound = await client.post(
        "/v1/auth/parents/children",
        json={"child_phone": child["phone"], "sms_code": send.json()["debug_code"]},
        headers=headers_of(parent),
    )
    assert bound.status_code == 201, bound.text
    child_id = str(bound.json()["id"])

    enabled = await client.put(
        "/v1/parents/controls",
        json={
            "child_id": child_id,
            "parent_password": parent_password,
            "is_enabled": True,
            "daily_limit_minutes": 30,
            "rest_after_minutes": 20,
        },
        headers=headers_of(parent),
    )
    assert enabled.status_code == 200, enabled.text

    recorded = await client.post(
        "/v1/analytics/events",
        json={"events": [{"name": "study.time", "payload": {"seconds": 1800}}]},
        headers=headers_of(child),
    )
    assert recorded.status_code == 200, recorded.text

    response = await client.get("/v1/test-guardian/probe", headers=headers_of(child))
    assert response.status_code == 423, response.text
    assert response.json()["code"] == "GUARDIAN_LOCKED"
