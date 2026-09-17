"""API 依赖：数据库会话、当前用户、角色校验。"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AuthError, PermissionDeniedError
from app.models import User, UserRole
from app.services.security import ACCESS_TOKEN_TYPE, decode_token


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """请求级数据库会话。"""
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """解析 Bearer 访问令牌并加载当前用户。"""
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        raise AuthError("请先登录", code="AUTH_MISSING_TOKEN")
    token = header[7:].strip()
    payload = decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
    try:
        user_id = uuid.UUID(str(payload.get("sub", "")))
    except ValueError as exc:
        raise AuthError("登录状态无效，请重新登录", code="AUTH_INVALID_TOKEN") from exc

    from app.services.auth_service import get_user_by_id

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise AuthError("账号不存在，请重新登录", code="AUTH_USER_NOT_FOUND")
    if not user.is_active:
        raise AuthError("账号已被停用", code="AUTH_ACCOUNT_DISABLED", status_code=403)
    return user


def require_roles(*roles: UserRole) -> Callable[..., Awaitable[User]]:
    """角色校验依赖工厂。"""

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("当前账号无权访问该资源")
        return user

    return dependency
