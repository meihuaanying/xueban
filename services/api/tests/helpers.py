"""测试辅助函数（业务级）。"""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import auth_headers, next_phone


async def register(
    client: AsyncClient,
    *,
    role: str = "student",
    phone: str | None = None,
    password: str = "password123",
    nickname: str | None = None,
    is_k12: bool = False,
) -> dict[str, str]:
    """注册并返回令牌对（含 phone 便于后续登录）。"""
    use_phone = phone or next_phone()
    response = await client.post(
        "/v1/auth/register",
        json={
            "phone": use_phone,
            "password": password,
            "role": role,
            "nickname": nickname,
            "is_k12": is_k12,
        },
    )
    assert response.status_code == 201, f"phone={use_phone} {response.text}"
    payload = response.json()
    payload["phone"] = use_phone
    return payload


async def register_user(
    client: AsyncClient, *, role: str = "student", nickname: str | None = None
) -> dict[str, str]:
    """注册并补齐用户 id（家长/后台用例需要用户标识）。"""
    tokens = await register(client, role=role, nickname=nickname)
    profile = await client.get("/v1/auth/me", headers=auth_headers(tokens["access_token"]))
    assert profile.status_code == 200, profile.text
    tokens["id"] = str(profile.json()["id"])
    return tokens


async def sms_login(client: AsyncClient, *, phone: str | None = None) -> tuple[dict[str, str], str]:
    """验证码登录（开发环境返回 debug_code）。"""
    use_phone = phone or next_phone()
    send = await client.post("/v1/auth/sms/send", json={"phone": use_phone, "purpose": "login"})
    assert send.status_code == 200, send.text
    code = send.json()["debug_code"]
    assert code, "开发环境应返回 debug_code"
    login = await client.post("/v1/auth/sms/login", json={"phone": use_phone, "code": code})
    assert login.status_code == 200, login.text
    return login.json(), use_phone


def headers_of(payload: dict[str, str]) -> dict[str, str]:
    """从令牌对取鉴权头。"""
    return auth_headers(payload["access_token"])
