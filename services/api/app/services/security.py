"""安全原语：密码哈希与 JWT 令牌。"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import settings
from app.db import utcnow
from app.errors import AuthError

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

# bcrypt 输入上限（字节）；超限直接拒绝，避免截断风险
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """生成密码哈希。"""
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise AuthError("密码过长", code="AUTH_PASSWORD_TOO_LONG", status_code=400)
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    """校验密码。"""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def hash_token(token: str) -> str:
    """令牌摘要（入库存储用，避免明文落库）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(
    *, user_id: uuid.UUID, role: str, token_type: str, expires_delta: timedelta
) -> str:
    """签发 JWT。"""
    now = utcnow()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(*, user_id: uuid.UUID, role: str) -> str:
    """访问令牌（默认 15 分钟）。"""
    return create_token(
        user_id=user_id,
        role=role,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(*, user_id: uuid.UUID, role: str) -> tuple[str, str, datetime]:
    """刷新令牌（默认 30 天）：返回 (token, jti, expires_at)。"""
    expires_at = utcnow() + timedelta(days=settings.refresh_token_expire_days)
    token = create_token(
        user_id=user_id,
        role=role,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )
    payload = decode_token(token)
    return token, str(payload["jti"]), expires_at


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    """解析并校验 JWT；失败抛 AuthError。"""
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("登录已过期，请重新登录", code="AUTH_TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("登录状态无效，请重新登录", code="AUTH_INVALID_TOKEN") from exc
    if expected_type is not None and payload.get("type") != expected_type:
        raise AuthError("令牌类型不正确", code="AUTH_INVALID_TOKEN")
    return payload
