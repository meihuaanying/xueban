"""认证服务：注册/登录/令牌轮换/短信验证码/家长绑定。"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import utcnow
from app.errors import AuthError, ConflictError, NotFoundError
from app.models import ParentChild, RefreshToken, SmsCode, Subscription, User, UserRole
from app.services.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.services.sms import get_sms_provider

MAX_SMS_CODE_ATTEMPTS = 5


@dataclass(slots=True)
class TokenPair:
    """令牌对（登录/刷新响应）。"""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


async def get_user_by_phone(session: AsyncSession, phone: str) -> User | None:
    """按手机号查询用户。"""
    result = await session.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """按 ID 查询用户。"""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    phone: str,
    password: str | None,
    role: UserRole = UserRole.STUDENT,
    nickname: str | None = None,
    is_k12: bool = False,
) -> User:
    """创建用户并初始化订阅（免费档）。"""
    user = User(
        phone=phone,
        password_hash=hash_password(password) if password else None,
        role=role,
        nickname=nickname,
        is_k12=is_k12,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("该手机号已注册", code="AUTH_PHONE_EXISTS") from exc
    session.add(Subscription(user_id=user.id))
    await session.flush()
    return user


async def register(
    session: AsyncSession,
    *,
    phone: str,
    password: str,
    role: UserRole,
    nickname: str | None = None,
    is_k12: bool = False,
) -> User:
    """注册（手机号唯一）。"""
    if await get_user_by_phone(session, phone) is not None:
        raise ConflictError("该手机号已注册", code="AUTH_PHONE_EXISTS")
    return await create_user(
        session, phone=phone, password=password, role=role, nickname=nickname, is_k12=is_k12
    )


async def authenticate(session: AsyncSession, *, phone: str, password: str) -> User:
    """密码登录。"""
    user = await get_user_by_phone(session, phone)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("手机号或密码错误", code="AUTH_INVALID_CREDENTIALS")
    if not user.is_active:
        raise AuthError("账号已被停用", code="AUTH_ACCOUNT_DISABLED", status_code=403)
    user.last_login_at = utcnow()
    await session.flush()
    return user


async def issue_token_pair(session: AsyncSession, user: User) -> TokenPair:
    """签发访问令牌 + 刷新令牌（刷新令牌入库存摘要）。"""
    access_token = create_access_token(user_id=user.id, role=user.role.value)
    refresh_token, jti, expires_at = create_refresh_token(user_id=user.id, role=user.role.value)
    session.add(
        RefreshToken(
            user_id=user.id,
            jti=jti,
            token_hash=hash_token(refresh_token),
            expires_at=expires_at,
        )
    )
    await session.flush()
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


async def rotate_refresh_token(session: AsyncSession, *, refresh_token: str) -> TokenPair:
    """刷新令牌轮换：旧令牌立即吊销，签发新令牌对。"""
    payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    jti = str(payload.get("jti", ""))
    result = await session.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    record = result.scalar_one_or_none()
    if record is None or record.token_hash != hash_token(refresh_token):
        raise AuthError("登录状态无效，请重新登录", code="AUTH_INVALID_TOKEN")
    if record.revoked_at is not None:
        raise AuthError("登录状态已失效，请重新登录", code="AUTH_TOKEN_REVOKED")
    if record.expires_at <= utcnow():
        raise AuthError("登录已过期，请重新登录", code="AUTH_TOKEN_EXPIRED")
    user = await get_user_by_id(session, record.user_id)
    if user is None or not user.is_active:
        raise AuthError("账号不可用", code="AUTH_ACCOUNT_DISABLED", status_code=403)
    record.revoked_at = utcnow()
    await session.flush()
    return await issue_token_pair(session, user)


async def revoke_refresh_token(session: AsyncSession, *, refresh_token: str) -> None:
    """退出登录：吊销刷新令牌（幂等）。"""
    try:
        payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    except AuthError:
        return
    jti = str(payload.get("jti", ""))
    result = await session.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    record = result.scalar_one_or_none()
    if record is not None and record.revoked_at is None:
        record.revoked_at = utcnow()
        await session.flush()


# ---------- 短信验证码 ----------


def _generate_code() -> str:
    """生成 6 位数字验证码。"""
    return f"{secrets.randbelow(1_000_000):06d}"


async def send_sms_code(session: AsyncSession, *, phone: str, purpose: str = "login") -> str:
    """生成并「发送」验证码（mock 提供商仅落库+日志）。"""
    code = _generate_code()
    record = SmsCode(
        phone=phone,
        purpose=purpose,
        code_hash=hash_token(code),
        expires_at=utcnow() + timedelta(seconds=settings.sms_code_ttl_seconds),
    )
    session.add(record)
    await session.flush()
    provider = get_sms_provider(settings)
    await provider.send_code(phone, code, purpose)
    return code


async def verify_sms_code(
    session: AsyncSession, *, phone: str, code: str, purpose: str = "login"
) -> None:
    """校验验证码：过期/次数超限/错误分别给出明确错误码。"""
    result = await session.execute(
        select(SmsCode)
        .where(SmsCode.phone == phone, SmsCode.purpose == purpose, SmsCode.consumed_at.is_(None))
        .order_by(SmsCode.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise AuthError("请先获取验证码", code="SMS_CODE_NOT_FOUND", status_code=400)
    if record.expires_at <= utcnow():
        raise AuthError("验证码已过期，请重新获取", code="SMS_CODE_EXPIRED", status_code=400)
    if record.attempts >= MAX_SMS_CODE_ATTEMPTS:
        raise AuthError(
            "验证码尝试次数过多，请重新获取", code="SMS_CODE_MAX_ATTEMPTS", status_code=429
        )
    record.attempts += 1
    if record.code_hash != hash_token(code):
        # 失败计数必须持久化（请求以异常结束，依赖注入的会话不会提交）
        await session.commit()
        raise AuthError("验证码错误", code="SMS_CODE_INVALID", status_code=400)
    record.consumed_at = utcnow()
    await session.flush()


async def sms_login(session: AsyncSession, *, phone: str, code: str) -> User:
    """验证码登录：不存在则自动注册为学生账号。"""
    await verify_sms_code(session, phone=phone, code=code)
    user = await get_user_by_phone(session, phone)
    if user is None:
        user = await create_user(session, phone=phone, password=None)
    if not user.is_active:
        raise AuthError("账号已被停用", code="AUTH_ACCOUNT_DISABLED", status_code=403)
    user.last_login_at = utcnow()
    await session.flush()
    return user


# ---------- 家长-孩子绑定 ----------


async def bind_child(session: AsyncSession, *, parent: User, child_phone: str) -> User:
    """家长绑定孩子账号（孩子须为学生）。"""
    child = await get_user_by_phone(session, child_phone)
    if child is None:
        raise NotFoundError("未找到该手机号对应的学生账号", code="BIND_CHILD_NOT_FOUND")
    if child.role != UserRole.STUDENT:
        raise ConflictError("只能绑定学生账号", code="BIND_TARGET_NOT_STUDENT")
    existing = await session.execute(
        select(ParentChild).where(
            ParentChild.parent_id == parent.id, ParentChild.child_id == child.id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("已绑定该孩子", code="BIND_ALREADY_EXISTS")
    session.add(ParentChild(parent_id=parent.id, child_id=child.id))
    await session.flush()
    return child


async def ensure_dev_admin(session: AsyncSession, *, phone: str, password: str) -> User | None:
    """开发/CI 环境按配置创建管理员账号（幂等；生产不调用）。"""
    if not phone or not password:
        return None
    existing = await get_user_by_phone(session, phone)
    if existing is not None:
        return existing
    admin = User(
        phone=phone,
        role=UserRole.ADMIN,
        password_hash=hash_password(password),
        nickname="开发管理员",
    )
    session.add(admin)
    await session.flush()
    return admin


async def list_children(session: AsyncSession, *, parent: User) -> list[User]:
    """家长可见的孩子列表。"""
    result = await session.execute(
        select(User)
        .join(ParentChild, ParentChild.child_id == User.id)
        .where(ParentChild.parent_id == parent.id, ParentChild.status == "active")
        .order_by(User.created_at)
    )
    return list(result.scalars().all())


async def unbind_child(session: AsyncSession, *, parent: User, child_id: uuid.UUID) -> None:
    """解绑孩子。"""
    result = await session.execute(
        select(ParentChild).where(
            ParentChild.parent_id == parent.id, ParentChild.child_id == child_id
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise NotFoundError("绑定关系不存在", code="BIND_NOT_FOUND")
    await session.delete(record)


async def delete_account(session: AsyncSession, *, user: User, password: str | None) -> None:
    """注销账号：校验密码 → 匿名化 + 停用 + 吊销全部刷新令牌（30 天后物理删除）。"""
    if user.password_hash and not verify_password(password or "", user.password_hash):
        raise AuthError(
            "密码错误，无法注销账号", code="AUTH_PASSWORD_INVALID", status_code=400
        )
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    # 匿名化（保留唯一占位手机号以便审计关联，30 天后随账号物理删除）
    user.phone = f"deleted:{user.id.hex[:12]}"
    user.nickname = None
    user.password_hash = None
    user.is_active = False
    user.deleted_at = utcnow()
    await session.flush()


async def purge_deleted_accounts(
    session: AsyncSession, *, retention_days: int = 30, dry_run: bool = False
) -> list[uuid.UUID]:
    """物理删除超过保留期的注销账号（子表数据按外键级联清理）。"""
    cutoff = utcnow() - timedelta(days=retention_days)
    result = await session.execute(
        select(User.id).where(User.deleted_at.isnot(None), User.deleted_at < cutoff)
    )
    user_ids = list(result.scalars().all())
    if user_ids and not dry_run:
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.flush()
    return user_ids
    await session.flush()
