"""认证路由：注册/登录/短信/令牌轮换/家长绑定。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, require_roles
from app.config import settings
from app.models import User, UserRole
from app.schemas import (
    AccountDeleteRequest,
    BindChildRequest,
    ChildResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    SmsLoginRequest,
    SmsSendRequest,
    SmsSendResponse,
    TokenPairResponse,
    UserResponse,
)
from app.services import auth_service
from app.services.auth_service import TokenPair

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _token_response(pair: TokenPair) -> TokenPairResponse:
    """统一令牌响应。"""
    return TokenPairResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        token_type=pair.token_type,
        expires_in=pair.expires_in,
    )


@router.post(
    "/register",
    response_model=TokenPairResponse,
    status_code=status.HTTP_201_CREATED,
    summary="注册（返回令牌）",
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPairResponse:
    """手机号注册并自动登录。"""
    user = await auth_service.register(
        session,
        phone=payload.phone,
        password=payload.password,
        role=UserRole(payload.role),
        nickname=payload.nickname,
        is_k12=payload.is_k12,
    )
    pair = await auth_service.issue_token_pair(session, user)
    await session.commit()
    return _token_response(pair)


@router.post("/login", response_model=TokenPairResponse, summary="密码登录")
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPairResponse:
    """手机号 + 密码登录。"""
    user = await auth_service.authenticate(session, phone=payload.phone, password=payload.password)
    pair = await auth_service.issue_token_pair(session, user)
    await session.commit()
    return _token_response(pair)


@router.post("/sms/send", response_model=SmsSendResponse, summary="发送短信验证码")
async def send_sms_code(
    payload: SmsSendRequest,
    session: AsyncSession = Depends(get_session),
) -> SmsSendResponse:
    """发送验证码（mock 提供商；开发环境返回 debug_code）。"""
    code = await auth_service.send_sms_code(session, phone=payload.phone, purpose=payload.purpose)
    await session.commit()
    return SmsSendResponse(
        sent=True,
        expires_in=settings.sms_code_ttl_seconds,
        debug_code=code if settings.is_development else None,
    )


@router.post("/sms/login", response_model=TokenPairResponse, summary="验证码登录")
async def sms_login(
    payload: SmsLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPairResponse:
    """验证码登录（新用户自动注册为学生）。"""
    user = await auth_service.sms_login(session, phone=payload.phone, code=payload.code)
    pair = await auth_service.issue_token_pair(session, user)
    await session.commit()
    return _token_response(pair)


@router.post("/refresh", response_model=TokenPairResponse, summary="刷新令牌")
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPairResponse:
    """刷新令牌（旧令牌立即失效）。"""
    pair = await auth_service.rotate_refresh_token(session, refresh_token=payload.refresh_token)
    await session.commit()
    return _token_response(pair)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="退出登录")
async def logout(
    payload: LogoutRequest,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """退出登录：吊销刷新令牌。"""
    await auth_service.revoke_refresh_token(session, refresh_token=payload.refresh_token)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse, summary="当前用户信息")
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    """获取当前登录用户。"""
    return UserResponse.model_validate(user)


@router.post(
    "/account/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="注销账号（匿名化 + 停用；30 天后物理删除）",
)
async def delete_account(
    payload: AccountDeleteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """注销当前账号：校验密码 → 匿名化并停用 → 吊销全部刷新令牌。"""
    await auth_service.delete_account(session, user=user, password=payload.password)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- 家长-孩子绑定 ----------


@router.post(
    "/parents/children",
    response_model=ChildResponse,
    status_code=status.HTTP_201_CREATED,
    summary="家长绑定孩子",
)
async def bind_child(
    payload: BindChildRequest,
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> ChildResponse:
    """绑定孩子账号（须为学生）。"""
    child = await auth_service.bind_child(session, parent=parent, child_phone=payload.child_phone)
    await session.commit()
    return _to_child_response(child)


@router.get("/parents/children", response_model=list[ChildResponse], summary="孩子列表")
async def list_children(
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> list[ChildResponse]:
    """家长可见的孩子列表。"""
    children = await auth_service.list_children(session, parent=parent)
    return [_to_child_response(child) for child in children]


@router.delete(
    "/parents/children/{child_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="解绑孩子",
)
async def unbind_child(
    child_id: uuid.UUID,
    parent: User = Depends(require_roles(UserRole.PARENT)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """解除绑定。"""
    await auth_service.unbind_child(session, parent=parent, child_id=child_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_child_response(child: User) -> ChildResponse:
    """孩子信息（手机号脱敏）。"""
    phone = child.phone
    masked = f"{phone[:3]}****{phone[-4:]}" if len(phone) >= 11 else phone
    return ChildResponse(
        id=child.id,
        phone=masked,
        nickname=child.nickname,
        is_k12=child.is_k12,
        created_at=child.created_at,
    )
