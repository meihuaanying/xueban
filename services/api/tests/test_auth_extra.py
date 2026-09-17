"""认证服务补充分支测试：过期刷新令牌、账号状态、异常路径。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import utcnow
from app.errors import AuthError
from app.models import RefreshToken, User
from app.services import auth_service
from app.services.security import hash_password, hash_token, verify_password
from tests.conftest import auth_headers, next_phone
from tests.helpers import headers_of, register


async def test_refresh_record_expired_in_db(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    async with sessionmaker() as session:
        record = (
            await session.execute(
                select(RefreshToken)
                .join(User, User.id == RefreshToken.user_id)
                .where(User.phone == payload["phone"])
            )
        ).scalar_one()
        record.expires_at = utcnow() - timedelta(seconds=1)
        await session.commit()

    response = await client.post(
        "/v1/auth/refresh", json={"refresh_token": payload["refresh_token"]}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_EXPIRED"


async def test_refresh_for_disabled_user_rejected(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    async with sessionmaker() as session:
        await session.execute(
            update(User).where(User.phone == payload["phone"]).values(is_active=False)
        )
        await session.commit()
    response = await client.post(
        "/v1/auth/refresh", json={"refresh_token": payload["refresh_token"]}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_ACCOUNT_DISABLED"


async def test_access_token_with_bad_subject_rejected(client: AsyncClient) -> None:
    from app.services.security import create_token

    token = create_token(
        user_id="not-a-uuid",  # type: ignore[arg-type]
        role="student",
        token_type="access",
        expires_delta=timedelta(minutes=5),
    )
    response = await client.get("/v1/auth/me", headers=auth_headers(token))
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_TOKEN"


async def test_access_token_for_deleted_user_rejected(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    async with sessionmaker() as session:
        user = (
            await session.execute(select(User).where(User.phone == payload["phone"]))
        ).scalar_one()
        await session.delete(user)
        await session.commit()
    response = await client.get("/v1/auth/me", headers=headers_of(payload))
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_USER_NOT_FOUND"


async def test_access_token_for_disabled_user_rejected(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    payload = await register(client)
    async with sessionmaker() as session:
        await session.execute(
            update(User).where(User.phone == payload["phone"]).values(is_active=False)
        )
        await session.commit()
    response = await client.get("/v1/auth/me", headers=headers_of(payload))
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH_ACCOUNT_DISABLED"


async def test_unbind_without_bound_relation(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    import uuid as _uuid

    from app.errors import NotFoundError

    parent_payload = await register(client, role="parent")
    async with sessionmaker() as session:
        parent = (
            await session.execute(select(User).where(User.phone == parent_payload["phone"]))
        ).scalar_one()
        with pytest.raises(NotFoundError):
            await auth_service.unbind_child(session, parent=parent, child_id=_uuid.uuid4())


async def test_verify_password_with_invalid_hash() -> None:
    assert verify_password("whatever", "not-a-bcrypt-hash") is False
    assert verify_password("whatever", None) is False


async def test_hash_password_too_long_rejected() -> None:
    with pytest.raises(AuthError) as excinfo:
        hash_password("x" * 100)
    assert excinfo.value.code == "AUTH_PASSWORD_TOO_LONG"


async def test_sms_send_with_bind_purpose(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    from app.models import SmsCode

    phone = next_phone()
    response = await client.post("/v1/auth/sms/send", json={"phone": phone, "purpose": "bind"})
    assert response.status_code == 200
    async with sessionmaker() as session:
        record = (
            await session.execute(select(SmsCode).where(SmsCode.phone == phone))
        ).scalar_one()
    assert record.purpose == "bind"


async def test_sms_verify_without_record(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/sms/login", json={"phone": next_phone(), "code": "123456"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "SMS_CODE_NOT_FOUND"


def test_sms_provider_unsupported() -> None:
    from app.services.sms import get_sms_provider

    settings = Settings(sms_provider="unknown-vendor")
    with pytest.raises(NotImplementedError):
        get_sms_provider(settings)


async def test_issue_and_rotate_token_pair_roundtrip(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    async with sessionmaker() as session:
        user = User(phone=next_phone(), password_hash=hash_password("password123"))
        session.add(user)
        await session.flush()
        pair = await auth_service.issue_token_pair(session, user)
        await session.commit()
        assert pair.token_type == "Bearer"

        rotated = await auth_service.rotate_refresh_token(
            session, refresh_token=pair.refresh_token
        )
        await session.commit()
        assert rotated.refresh_token != pair.refresh_token
        record = (
            await session.execute(
                select(RefreshToken).where(RefreshToken.user_id == user.id)
            )
        ).scalars().all()
        assert len(record) == 2
        assert sum(1 for item in record if item.revoked_at is not None) == 1


async def test_revoke_with_invalid_token_is_noop(client: AsyncClient) -> None:
    response = await client.post("/v1/auth/logout", json={"refresh_token": "broken-token"})
    assert response.status_code == 204


async def test_hash_token_is_stable() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
