"""认证相关请求/响应契约。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PHONE_PATTERN = r"^1[3-9]\d{9}$"


class RegisterRequest(BaseModel):
    """注册请求。"""

    phone: str = Field(pattern=PHONE_PATTERN, description="中国大陆手机号")
    password: str = Field(min_length=8, max_length=64, description="密码（8-64 位）")
    role: Literal["student", "parent"] = "student"
    nickname: str | None = Field(default=None, max_length=50)
    is_k12: bool = False


class LoginRequest(BaseModel):
    """密码登录请求。"""

    phone: str = Field(pattern=PHONE_PATTERN)
    password: str = Field(min_length=1, max_length=64)


class SmsSendRequest(BaseModel):
    """发送验证码请求。"""

    phone: str = Field(pattern=PHONE_PATTERN)
    purpose: Literal["login", "bind"] = "login"


class SmsSendResponse(BaseModel):
    """发送验证码响应。"""

    sent: bool = True
    expires_in: int = Field(description="有效期（秒）")
    debug_code: str | None = Field(default=None, description="仅开发环境返回，便于联调")


class SmsLoginRequest(BaseModel):
    """验证码登录请求。"""

    phone: str = Field(pattern=PHONE_PATTERN)
    code: str = Field(min_length=4, max_length=8)


class RefreshRequest(BaseModel):
    """刷新令牌请求。"""

    refresh_token: str


class LogoutRequest(BaseModel):
    """退出登录请求。"""

    refresh_token: str


class AccountDeleteRequest(BaseModel):
    """注销账号请求（有密码账号必须校验密码；短信注册账号可留空）。"""

    password: str | None = Field(default=None, max_length=64)


class TokenPairResponse(BaseModel):
    """令牌对响应。"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="访问令牌有效期（秒）")


class UserResponse(BaseModel):
    """当前用户信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    nickname: str | None = None
    role: str
    is_k12: bool
    created_at: datetime


class BindChildRequest(BaseModel):
    """家长绑定孩子请求。"""

    child_phone: str = Field(pattern=PHONE_PATTERN)


class ChildResponse(BaseModel):
    """家长可见的孩子信息（手机号脱敏）。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    nickname: str | None = None
    is_k12: bool
    created_at: datetime
