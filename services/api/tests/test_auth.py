"""认证体系测试（T1.2：注册/登录/刷新/过期/越权/家长绑定）。"""

from __future__ import annotations

import secrets
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import SmsCode, User
from app.services.security import create_token, decode_token, hash_token
from tests.conftest import auth_headers, next_phone
from tests.helpers import TEST_PASSWORD, WRONG_PASSWORD, headers_of, register, sms_login

# ---------- 注册 ----------


async def test_register_returns_tokens_and_me(client: AsyncClient) -> None:
    payload = await register(client)
    me = await client.get("/v1/auth/me", headers=headers_of(payload))
    assert me.status_code == 200
    body = me.json()
    assert body["phone"] == payload["phone"]
    assert body["role"] == "student"


async def test_register_duplicate_phone_conflict(client: AsyncClient) -> None:
    payload = await register(client)
    again = await client.post(
        "/v1/auth/register",
        json={"phone": payload["phone"], "password": TEST_PASSWORD},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "AUTH_PHONE_EXISTS"


async def test_register_invalid_phone_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/register", json={"phone": "123456", "password": TEST_PASSWORD}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_register_short_password_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/register", json={"phone": next_phone(), "password": "123"}
    )
    assert response.status_code == 422


async def test_register_parent_role(client: AsyncClient) -> None:
    payload = await register(client, role="parent")
    me = await client.get("/v1/auth/me", headers=headers_of(payload))
    assert me.json()["role"] == "parent"


async def test_register_invalid_role_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/register",
        json={"phone": next_phone(), "password": TEST_PASSWORD, "role": "admin"},
    )
    assert response.status_code == 422


# ---------- 密码登录 ----------


async def test_login_success(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/auth/login", json={"phone": payload["phone"], "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_wrong_password(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post(
        "/v1/auth/login", json={"phone": payload["phone"], "password": WRONG_PASSWORD}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_login_unknown_phone(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/login", json={"phone": next_phone(), "password": TEST_PASSWORD}
    )
    assert response.status_code == 401


async def test_login_disabled_account(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    async with sessionmaker() as session:
        await session.execute(
            update(User).where(User.phone == payload["phone"]).values(is_active=False)
        )
        await session.commit()
    response = await client.post(
        "/v1/auth/login", json={"phone": payload["phone"], "password": TEST_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_ACCOUNT_DISABLED"


# ---------- 令牌刷新与吊销 ----------


async def test_refresh_rotates_and_invalidates_old_token(client: AsyncClient) -> None:
    payload = await register(client)
    refreshed = await client.post(
        "/v1/auth/refresh", json={"refresh_token": payload["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != payload["refresh_token"]

    reused = await client.post("/v1/auth/refresh", json={"refresh_token": payload["refresh_token"]})
    assert reused.status_code == 401
    assert reused.json()["code"] == "AUTH_TOKEN_REVOKED"


async def test_refresh_with_garbage_token(client: AsyncClient) -> None:
    response = await client.post("/v1/auth/refresh", json={"refresh_token": "garbage"})
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_TOKEN"


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    payload = await register(client)
    logout = await client.post("/v1/auth/logout", json={"refresh_token": payload["refresh_token"]})
    assert logout.status_code == 204
    rejected = await client.post(
        "/v1/auth/refresh", json={"refresh_token": payload["refresh_token"]}
    )
    assert rejected.status_code == 401
    assert rejected.json()["code"] == "AUTH_TOKEN_REVOKED"


async def test_logout_is_idempotent(client: AsyncClient) -> None:
    invalid = "inv-" + secrets.token_urlsafe(12)
    response = await client.post("/v1/auth/logout", json={"refresh_token": invalid})
    assert response.status_code == 204


async def test_expired_access_token_rejected(client: AsyncClient) -> None:
    payload = await register(client)
    user_id = decode_token(payload["access_token"])["sub"]
    expired = create_token(
        user_id=user_id,
        role="student",
        token_type="access",
        expires_delta=timedelta(seconds=-30),
    )
    response = await client.get("/v1/auth/me", headers=auth_headers(expired))
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_EXPIRED"


async def test_refresh_token_cannot_access_me(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.get("/v1/auth/me", headers=auth_headers(payload["refresh_token"]))
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_TOKEN"


# ---------- 短信验证码 ----------


async def test_sms_send_returns_debug_code_in_development(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/sms/send", json={"phone": next_phone(), "purpose": "login"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sent"] is True
    assert body["debug_code"] and len(body["debug_code"]) == 6


async def test_sms_send_rate_limited(client: AsyncClient) -> None:
    """同一手机号 60 秒内第二次发送返回 429。"""
    phone = next_phone()
    first = await client.post("/v1/auth/sms/send", json={"phone": phone, "purpose": "login"})
    assert first.status_code == 200
    second = await client.post("/v1/auth/sms/send", json={"phone": phone, "purpose": "login"})
    assert second.status_code == 429
    assert second.json()["code"] == "SMS_SEND_TOO_FREQUENT"


async def test_sms_login_auto_registers_student(client: AsyncClient) -> None:
    payload, phone = await sms_login(client)
    me = await client.get("/v1/auth/me", headers=auth_headers(payload["access_token"]))
    assert me.status_code == 200
    assert me.json()["phone"] == phone
    assert me.json()["role"] == "student"


async def test_sms_login_wrong_code(client: AsyncClient) -> None:
    phone = next_phone()
    await client.post("/v1/auth/sms/send", json={"phone": phone, "purpose": "login"})
    response = await client.post("/v1/auth/sms/login", json={"phone": phone, "code": "000000"})
    assert response.status_code == 400
    assert response.json()["code"] == "SMS_CODE_INVALID"


async def test_sms_code_consumed_once(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload, phone = await sms_login(client)
    assert payload["access_token"]
    # 再次发送受频控限制（见 test_sms_send_rate_limited）；改为直插一条新验证码验证一次性
    from app.db import utcnow

    async with sessionmaker() as session:
        session.add(
            SmsCode(
                phone=phone,
                purpose="login",
                code_hash=hash_token("654321"),
                expires_at=utcnow() + timedelta(seconds=300),
            )
        )
        await session.commit()
    first = await client.post("/v1/auth/sms/login", json={"phone": phone, "code": "654321"})
    assert first.status_code == 200
    second = await client.post("/v1/auth/sms/login", json={"phone": phone, "code": "654321"})
    assert second.status_code == 400
    assert second.json()["code"] in {"SMS_CODE_NOT_FOUND", "SMS_CODE_INVALID"}


async def test_sms_code_max_attempts(client: AsyncClient) -> None:
    phone = next_phone()
    await client.post("/v1/auth/sms/send", json={"phone": phone, "purpose": "login"})
    for _ in range(5):
        await client.post("/v1/auth/sms/login", json={"phone": phone, "code": "000000"})
    blocked = await client.post("/v1/auth/sms/login", json={"phone": phone, "code": "000000"})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "SMS_CODE_MAX_ATTEMPTS"


async def test_sms_code_expired(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    phone = next_phone()
    from app.db import utcnow

    async with sessionmaker() as session:
        session.add(
            SmsCode(
                phone=phone,
                purpose="login",
                code_hash=hash_token("123456"),
                expires_at=utcnow() - timedelta(seconds=1),
            )
        )
        await session.commit()
    response = await client.post("/v1/auth/sms/login", json={"phone": phone, "code": "123456"})
    assert response.status_code == 400
    assert response.json()["code"] == "SMS_CODE_EXPIRED"


# ---------- 越权访问 ----------


async def test_student_cannot_access_parent_endpoints(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.get("/v1/auth/parents/children", headers=headers_of(payload))
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_admin_ping_requires_admin(client: AsyncClient, admin_token: str) -> None:
    allowed = await client.get("/v1/admin/ping", headers=auth_headers(admin_token))
    assert allowed.status_code == 200

    student = await register(client)
    denied = await client.get("/v1/admin/ping", headers=headers_of(student))
    assert denied.status_code == 403


# ---------- 家长-孩子绑定 ----------


async def test_parent_binds_and_lists_child_with_masked_phone(client: AsyncClient) -> None:
    child = await register(client)
    parent = await register(client, role="parent")
    send = await client.post("/v1/auth/sms/send", json={"phone": child["phone"], "purpose": "bind"})
    assert send.status_code == 200, send.text
    response = await client.post(
        "/v1/auth/parents/children",
        json={"child_phone": child["phone"], "sms_code": send.json()["debug_code"]},
        headers=headers_of(parent),
    )
    assert response.status_code == 201
    body = response.json()
    assert "****" in body["phone"]

    listing = await client.get("/v1/auth/parents/children", headers=headers_of(parent))
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_parent_bind_unknown_child(client: AsyncClient) -> None:
    parent = await register(client, role="parent")
    response = await client.post(
        "/v1/auth/parents/children",
        json={"child_phone": next_phone(), "sms_code": "123456"},
        headers=headers_of(parent),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "BIND_CHILD_NOT_FOUND"


async def test_parent_bind_non_student_rejected(client: AsyncClient) -> None:
    other_parent = await register(client, role="parent")
    parent = await register(client, role="parent")
    response = await client.post(
        "/v1/auth/parents/children",
        json={"child_phone": other_parent["phone"], "sms_code": "123456"},
        headers=headers_of(parent),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "BIND_TARGET_NOT_STUDENT"


async def test_parent_bind_duplicate_rejected(client: AsyncClient) -> None:
    child = await register(client)
    parent = await register(client, role="parent")
    send = await client.post("/v1/auth/sms/send", json={"phone": child["phone"], "purpose": "bind"})
    assert send.status_code == 200, send.text
    body = {"child_phone": child["phone"], "sms_code": send.json()["debug_code"]}
    first = await client.post("/v1/auth/parents/children", json=body, headers=headers_of(parent))
    assert first.status_code == 201
    second = await client.post("/v1/auth/parents/children", json=body, headers=headers_of(parent))
    assert second.status_code == 409
    assert second.json()["code"] == "BIND_ALREADY_EXISTS"


async def test_parent_unbind_child(client: AsyncClient) -> None:
    child = await register(client)
    parent = await register(client, role="parent")
    send = await client.post("/v1/auth/sms/send", json={"phone": child["phone"], "purpose": "bind"})
    assert send.status_code == 200, send.text
    bound = await client.post(
        "/v1/auth/parents/children",
        json={"child_phone": child["phone"], "sms_code": send.json()["debug_code"]},
        headers=headers_of(parent),
    )
    child_id = bound.json()["id"]
    removed = await client.delete(
        f"/v1/auth/parents/children/{child_id}", headers=headers_of(parent)
    )
    assert removed.status_code == 204
    listing = await client.get("/v1/auth/parents/children", headers=headers_of(parent))
    assert listing.json() == []


async def test_parent_unbind_not_bound(client: AsyncClient) -> None:
    parent = await register(client, role="parent")
    import uuid

    response = await client.delete(
        f"/v1/auth/parents/children/{uuid.uuid4()}", headers=headers_of(parent)
    )
    assert response.status_code == 404
    assert response.json()["code"] == "BIND_NOT_FOUND"


async def test_parent_cannot_see_other_parents_children(client: AsyncClient) -> None:
    child = await register(client)
    parent_a = await register(client, role="parent")
    parent_b = await register(client, role="parent")
    send = await client.post("/v1/auth/sms/send", json={"phone": child["phone"], "purpose": "bind"})
    assert send.status_code == 200, send.text
    await client.post(
        "/v1/auth/parents/children",
        json={"child_phone": child["phone"], "sms_code": send.json()["debug_code"]},
        headers=headers_of(parent_a),
    )
    listing = await client.get("/v1/auth/parents/children", headers=headers_of(parent_b))
    assert listing.json() == []
