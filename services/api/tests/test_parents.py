"""家长端测试（M7 / T7.1~T7.2，F-40~F-43；含 RBAC 用例）。"""

from __future__ import annotations

import uuid
from datetime import time, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.models import ChatMessage, ChatRole, ChatSession, ReportShare, SafetyEvent
from tests.conftest import auth_headers
from tests.helpers import headers_of, register_user


async def _bind(client: AsyncClient, parent: dict[str, str], child: dict[str, str]) -> str:
    """绑定孩子并返回 child_id。"""
    response = await client.post(
        "/v1/auth/parents/children",
        json={"child_phone": child["phone"]},
        headers=headers_of(parent),
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def test_rbac_parent_cannot_view_other_child_data(client: AsyncClient) -> None:
    """RBAC：家长不可见他人孩子数据。"""
    parent_a = await register_user(client, role="parent")
    parent_b = await register_user(client, role="parent")
    child_a = await register_user(client)
    child_b = await register_user(client)
    await _bind(client, parent_a, child_a)
    await _bind(client, parent_b, child_b)

    # 自己的孩子可访问
    own = await client.get(
        f"/v1/parents/children/{child_a['id']}/dashboard", headers=headers_of(parent_a)
    )
    assert own.status_code == 200, own.text

    # 他人孩子：403
    other = await client.get(
        f"/v1/parents/children/{child_b['id']}/dashboard", headers=headers_of(parent_a)
    )
    assert other.status_code == 403
    assert other.json()["code"] == "PARENT_CHILD_FORBIDDEN"

    # 他人孩子的防沉迷读取同样拒绝
    controls = await client.get(
        f"/v1/parents/children/{child_b['id']}/controls", headers=headers_of(parent_a)
    )
    assert controls.status_code == 403


async def test_rbac_student_cannot_access_parent_apis(client: AsyncClient) -> None:
    """RBAC：学生账号无法访问家长端接口。"""
    student = await register_user(client)
    response = await client.get("/v1/parents/tasks", headers=headers_of(student))
    # 学生访问 /v1/parents/tasks 会落到学生视图（自身任务），不是家长视图
    assert response.status_code == 200
    assert response.json()["tasks"] == []

    controls = await client.put(
        "/v1/parents/controls",
        json={
            "child_id": student["id"],
            "parent_password": "password123",
            "is_enabled": True,
            "daily_limit_minutes": 30,
            "rest_after_minutes": 20,
        },
        headers=headers_of(student),
    )
    assert controls.status_code == 403


async def test_rbac_admin_cannot_use_parent_endpoints(
    client: AsyncClient, admin_token: str
) -> None:
    """RBAC：管理员账号不具备家长权限。"""
    response = await client.get(
        f"/v1/parents/children/{uuid.uuid4()}/dashboard",
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 403


async def test_controls_update_requires_parent_password(client: AsyncClient) -> None:
    """F-40：修改设置需家长密码。"""
    parent = await register_user(client, role="parent")
    child = await register_user(client)
    child_id = await _bind(client, parent, child)

    wrong = await client.put(
        "/v1/parents/controls",
        json={
            "child_id": child_id,
            "parent_password": "wrong-password",
            "is_enabled": True,
            "daily_limit_minutes": 30,
            "rest_after_minutes": 20,
        },
        headers=headers_of(parent),
    )
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "PARENT_PASSWORD_INVALID"

    ok = await client.put(
        "/v1/parents/controls",
        json={
            "child_id": child_id,
            "parent_password": "password123",
            "is_enabled": True,
            "daily_limit_minutes": 30,
            "rest_after_minutes": 20,
        },
        headers=headers_of(parent),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["daily_limit_minutes"] == 30


async def test_guardian_status_locks_after_daily_limit(client: AsyncClient) -> None:
    """F-40/T7.2：服务端按当日学习时长判定锁屏（模拟超限）。"""
    parent = await register_user(client, role="parent")
    child = await register_user(client)
    child_id = await _bind(client, parent, child)
    await client.put(
        "/v1/parents/controls",
        json={
            "child_id": child_id,
            "parent_password": "password123",
            "is_enabled": True,
            "daily_limit_minutes": 30,
            "rest_after_minutes": 20,
        },
        headers=headers_of(parent),
    )

    before = await client.get("/v1/guardian/status", headers=headers_of(child))
    assert before.status_code == 200
    assert before.json()["locked"] is False

    # 模拟 30 分钟学习时长（study.time 埋点，30*60 秒）
    recorded = await client.post(
        "/v1/analytics/events",
        json={"events": [{"name": "study.time", "payload": {"seconds": 1800}}]},
        headers=headers_of(child),
    )
    assert recorded.status_code == 200

    after = await client.get("/v1/guardian/status", headers=headers_of(child))
    body = after.json()
    assert body["locked"] is True
    assert body["reasons"] == ["daily_limit"]
    assert body["used_minutes"] >= 30
    assert body["limit_minutes"] == 30


async def test_guardian_status_curfew_blocks_access(client: AsyncClient) -> None:
    """F-40：时段限制生效（当前时间不在允许时段内则锁屏）。"""
    parent = await register_user(client, role="parent")
    child = await register_user(client)
    child_id = await _bind(client, parent, child)

    now = utcnow()
    # 选择必定不包含“当前时刻”的固定时段，避免跨午夜导致窗口反转
    if now.hour >= 12:
        start, end = time(0, 0), time(6, 0)
    else:
        start, end = time(12, 0), time(18, 0)
    response = await client.put(
        "/v1/parents/controls",
        json={
            "child_id": child_id,
            "parent_password": "password123",
            "is_enabled": True,
            "daily_limit_minutes": 120,
            "allowed_start": start.isoformat(),
            "allowed_end": end.isoformat(),
            "rest_after_minutes": 40,
        },
        headers=headers_of(parent),
    )
    assert response.status_code == 200, response.text

    status = await client.get("/v1/guardian/status", headers=headers_of(child))
    body = status.json()
    assert body["locked"] is True
    assert "curfew" in body["reasons"]


async def test_dashboard_share_link_sign_and_revoke(client: AsyncClient) -> None:
    """F-41：免登录链接签名 + 吊销。"""
    parent = await register_user(client, role="parent")
    child = await register_user(client)
    child_id = await _bind(client, parent, child)

    created = await client.post(
        f"/v1/parents/dashboard/links?child_id={child_id}", headers=headers_of(parent)
    )
    assert created.status_code == 200, created.text
    token = created.json()["token"]
    assert created.json()["url_path"].endswith(token)

    # 免登录只读
    shared = await client.get(f"/v1/parents/dashboard/{token}")
    assert shared.status_code == 200
    assert shared.json()["child_id"] == child_id

    # 吊销后失效
    revoked = await client.delete(
        f"/v1/parents/dashboard/links/{token}", headers=headers_of(parent)
    )
    assert revoked.status_code == 204
    gone = await client.get(f"/v1/parents/dashboard/{token}")
    assert gone.status_code == 404
    assert gone.json()["code"] == "PARENT_SHARE_NOT_FOUND"


async def test_dashboard_share_expired_token_rejected(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """F-41：过期 token 拒绝访问。"""
    parent = await register_user(client, role="parent")
    child = await register_user(client)
    child_id = await _bind(client, parent, child)
    created = await client.post(
        f"/v1/parents/dashboard/links?child_id={child_id}", headers=headers_of(parent)
    )
    token = created.json()["token"]

    async with sessionmaker() as session:
        share = (
            await session.execute(select(ReportShare).where(ReportShare.token == token))
        ).scalar_one()
        share.expires_at = utcnow() - timedelta(minutes=1)
        await session.commit()

    response = await client.get(f"/v1/parents/dashboard/{token}")
    assert response.status_code == 404
    assert response.json()["code"] == "PARENT_SHARE_EXPIRED"


async def test_safety_report_events_and_traces(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """F-42：拦截事件落库可查 + 对话留痕抽查按周分页。"""
    parent = await register_user(client, role="parent")
    child = await register_user(client)
    child_id = await _bind(client, parent, child)

    async with sessionmaker() as session:
        session.add(
            SafetyEvent(
                user_id=child["id"],
                scene="tutor",
                provider="local",
                action="blocked",
                categories={"violence": 0.9},
                snippet="……不适宜内容……",
            )
        )
        chat = ChatSession(user_id=child["id"], title="讲解会话")
        session.add(chat)
        await session.flush()
        session.add(
            ChatMessage(
                session_id=chat.id,
                role=ChatRole.ASSISTANT,
                content="我们先看思路：这道题的关键是移项……",
                hint_level=1,
            )
        )
        await session.commit()

    response = await client.get(
        f"/v1/parents/children/{child_id}/safety?page=1&page_size=10",
        headers=headers_of(parent),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["blocked_count"] == 1
    assert body["total_events"] == 1
    assert body["events"][0]["snippet"].startswith("……")
    assert body["trace_total"] == 1
    assert body["traces"][0]["hint_level"] == 1
    assert "移项" in body["traces"][0]["excerpt"]


async def test_parent_task_loop_child_done_parent_confirm(client: AsyncClient) -> None:
    """F-43：系统布置 → 孩子完成 → 家长确认闭环。"""
    parent = await register_user(client, role="parent")
    child = await register_user(client)
    child_id = await _bind(client, parent, child)

    listed = await client.get(f"/v1/parents/tasks?child_id={child_id}", headers=headers_of(parent))
    assert listed.status_code == 200
    tasks = listed.json()["tasks"]
    assert len(tasks) >= 2  # 系统默认任务
    task_id = tasks[0]["id"]

    # 家长重复查看不重复生成
    again = await client.get(f"/v1/parents/tasks?child_id={child_id}", headers=headers_of(parent))
    assert len(again.json()["tasks"]) == len(tasks)

    # 孩子未完成时家长不能确认
    pending_confirm = await client.post(
        f"/v1/parents/tasks/{task_id}/confirm", headers=headers_of(parent)
    )
    assert pending_confirm.status_code == 403

    # 孩子完成 → 家长确认
    done = await client.post(f"/v1/parents/tasks/{task_id}/done", headers=headers_of(child))
    assert done.status_code == 200
    assert done.json()["status"] == "child_done"

    confirmed = await client.post(
        f"/v1/parents/tasks/{task_id}/confirm", headers=headers_of(parent)
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"

    # 孩子端能看到自己的任务
    child_tasks = await client.get("/v1/parents/tasks", headers=headers_of(child))
    assert any(item["id"] == task_id for item in child_tasks.json()["tasks"])


async def test_rbac_parent_cannot_confirm_other_parent_task(client: AsyncClient) -> None:
    """RBAC：家长不能确认他人布置的任务。"""
    parent_a = await register_user(client, role="parent")
    parent_b = await register_user(client, role="parent")
    child = await register_user(client)
    child_id = await _bind(client, parent_a, child)
    listed = await client.get(
        f"/v1/parents/tasks?child_id={child_id}", headers=headers_of(parent_a)
    )
    task_id = listed.json()["tasks"][0]["id"]
    await client.post(f"/v1/parents/tasks/{task_id}/done", headers=headers_of(child))

    response = await client.post(
        f"/v1/parents/tasks/{task_id}/confirm", headers=headers_of(parent_b)
    )
    assert response.status_code == 404

async def test_parent_weekly_report_with_suggestions(client: AsyncClient) -> None:
    """F-31：家长端周报含时长/进度/薄弱点与 ≥2 条亲子建议。"""
    parent = await register_user(client, role="parent")
    child = await register_user(client)
    child_id = await _bind(client, parent, child)

    # 产生一些学习行为（study.time 埋点）
    await client.post(
        "/v1/analytics/events",
        json={"events": [{"name": "study.time", "payload": {"seconds": 1800}}]},
        headers=headers_of(child),
    )

    response = await client.get(
        f"/v1/parents/weekly?child_id={child_id}", headers=headers_of(parent)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["child_id"] == child_id
    assert body["study_minutes"] >= 30
    assert body["week_start"] <= body["week_end"]
    assert len(body["suggestions"]) >= 2
    assert all(len(item) >= 8 for item in body["suggestions"])


async def test_rbac_other_parent_cannot_read_weekly(client: AsyncClient) -> None:
    """RBAC：家长不能读取他人孩子的周报。"""
    parent_a = await register_user(client, role="parent")
    parent_b = await register_user(client, role="parent")
    child = await register_user(client)
    child_id = await _bind(client, parent_b, child)
    response = await client.get(
        f"/v1/parents/weekly?child_id={child_id}", headers=headers_of(parent_a)
    )
    assert response.status_code == 403
