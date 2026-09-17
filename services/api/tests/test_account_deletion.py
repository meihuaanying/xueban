"""账号注销与物理删除（规格书 §10：注销后 30 天内物理删除）。

覆盖：
1. 注销需校验密码（错误密码 400）；
2. 注销即匿名化 + 停用 + 吊销刷新令牌，旧访问令牌失效；
3. purge 逻辑：保留期内的账号不删除、超期账号物理删除（子表级联清理）。
"""

from __future__ import annotations

from datetime import timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.models import RefreshToken, User
from app.services import auth_service
from tests.helpers import auth_headers, register


async def test_delete_account_requires_correct_password(client: AsyncClient) -> None:
    tokens = await register(client)
    response = await client.post(
        "/v1/auth/account/delete",
        json={"password": "wrong-password"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "AUTH_PASSWORD_INVALID"


async def test_delete_account_anonymizes_and_revokes(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    tokens = await register(client, nickname="待注销")
    phone = tokens["phone"]
    headers = auth_headers(tokens["access_token"])
    me = await client.get("/v1/auth/me", headers=headers)
    user_id = me.json()["id"]

    response = await client.post(
        "/v1/auth/account/delete", json={"password": "password123"}, headers=headers
    )
    assert response.status_code == 204

    # 旧访问令牌失效（账号已停用 → 403）
    assert (await client.get("/v1/auth/me", headers=headers)).status_code == 403
    # 原手机号无法登录；刷新令牌已吊销
    login = await client.post("/v1/auth/login", json={"phone": phone, "password": "password123"})
    assert login.status_code == 401
    refreshed = await client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 401

    async with sessionmaker() as session:
        user = await session.get(User, user_id)
        assert user is not None
        assert user.is_active is False
        assert user.deleted_at is not None
        assert user.phone.startswith("deleted:")
        assert user.password_hash is None
        assert user.nickname is None
        active_tokens = await session.scalar(
            select(func.count())
            .select_from(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        )
        assert active_tokens == 0


@pytest_asyncio.fixture()
async def deleted_user_id(
    client: AsyncClient, sessionmaker: async_sessionmaker[AsyncSession]
) -> str:
    """注销一个账号并返回其 user_id。"""
    tokens = await register(client)
    headers = auth_headers(tokens["access_token"])
    me = await client.get("/v1/auth/me", headers=headers)
    user_id: str = me.json()["id"]
    deleted = await client.post(
        "/v1/auth/account/delete", json={"password": "password123"}, headers=headers
    )
    assert deleted.status_code == 204
    return user_id


async def test_purge_respects_retention_window(
    deleted_user_id: str, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    import uuid as uuid_lib

    user_uuid = uuid_lib.UUID(deleted_user_id)
    async with sessionmaker() as session:
        purged = await auth_service.purge_deleted_accounts(session, retention_days=30, dry_run=True)
        assert user_uuid not in purged


async def test_purge_deletes_expired_accounts_with_cascade(
    deleted_user_id: str, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    import uuid as uuid_lib

    user_uuid = uuid_lib.UUID(deleted_user_id)
    async with sessionmaker() as session:
        await session.execute(
            update(User)
            .where(User.id == user_uuid)
            .values(deleted_at=utcnow() - timedelta(days=31))
        )
        await session.commit()

    async with sessionmaker() as session:
        purged = await auth_service.purge_deleted_accounts(session, retention_days=30)
        await session.commit()
        assert user_uuid in purged

    async with sessionmaker() as session:
        assert await session.get(User, user_uuid) is None
        tokens_left = await session.scalar(
            select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == user_uuid)
        )
        assert tokens_left == 0
