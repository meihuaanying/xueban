"""订阅状态机测试（T1.6）：单元迁移矩阵 + API 全流程。"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.errors import BillingError, NotFoundError
from app.models import BillingCycle, CheckoutStatus, SubscriptionPlan, User
from app.services import billing_service
from tests.factories import UserFactory
from tests.helpers import headers_of, register


async def _make_user(sessionmaker: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    """直建用户并返回 ID。"""
    user: User = UserFactory()
    async with sessionmaker() as session:
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
    return user_id


# ---------- 单元：状态迁移 ----------


async def test_new_subscription_defaults_to_free(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        subscription = await billing_service.get_or_create_subscription(session, user_id)
        assert subscription.plan == SubscriptionPlan.FREE
        assert subscription.trial_used is False


async def test_start_trial_sets_window(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        subscription = await billing_service.get_or_create_subscription(session, user_id)
        await billing_service.start_trial(session, subscription)
        assert subscription.plan == SubscriptionPlan.TRIAL
        assert subscription.trial_used is True
        assert subscription.expires_at is not None
        delta = subscription.expires_at - utcnow()
        assert timedelta(days=6) < delta <= timedelta(days=7)


async def test_trial_twice_rejected(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        subscription = await billing_service.get_or_create_subscription(session, user_id)
        await billing_service.start_trial(session, subscription)
        with pytest.raises(BillingError) as excinfo:
            await billing_service.start_trial(session, subscription)
        assert excinfo.value.code == "BILLING_TRIAL_USED"


async def test_trial_unavailable_after_pro(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        subscription = await billing_service.get_or_create_subscription(session, user_id)
        await billing_service.activate_pro(session, subscription, BillingCycle.MONTHLY)
        with pytest.raises(BillingError) as excinfo:
            await billing_service.start_trial(session, subscription)
        assert excinfo.value.code == "BILLING_TRIAL_UNAVAILABLE"


async def test_activate_pro_sets_expiry(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        subscription = await billing_service.get_or_create_subscription(session, user_id)
        await billing_service.activate_pro(session, subscription, BillingCycle.MONTHLY)
        assert subscription.plan == SubscriptionPlan.PRO
        assert subscription.expires_at is not None
        delta = subscription.expires_at - utcnow()
        assert timedelta(days=29) < delta <= timedelta(days=30)


async def test_renewal_extends_from_current_expiry(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        subscription = await billing_service.get_or_create_subscription(session, user_id)
        await billing_service.activate_pro(session, subscription, BillingCycle.MONTHLY)
        first_expiry = subscription.expires_at
        assert first_expiry is not None
        await billing_service.activate_pro(session, subscription, BillingCycle.MONTHLY)
        assert subscription.expires_at is not None
        assert subscription.expires_at > first_expiry
        assert subscription.expires_at - first_expiry == timedelta(days=30)


async def test_expiry_downgrades_to_free(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        subscription = await billing_service.get_or_create_subscription(session, user_id)
        await billing_service.activate_pro(session, subscription, BillingCycle.MONTHLY)
        subscription.expires_at = utcnow() - timedelta(seconds=1)
        await billing_service.sync_subscription(session, subscription)
        assert subscription.plan == SubscriptionPlan.FREE
        assert subscription.expires_at is None
        assert subscription.auto_renew is False


async def test_cancel_requires_pro(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        subscription = await billing_service.get_or_create_subscription(session, user_id)
        with pytest.raises(BillingError) as excinfo:
            await billing_service.cancel_subscription(session, subscription)
        assert excinfo.value.code == "BILLING_CANCEL_UNAVAILABLE"


async def test_cancel_sets_auto_renew_false(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        subscription = await billing_service.get_or_create_subscription(session, user_id)
        await billing_service.activate_pro(session, subscription, BillingCycle.YEARLY)
        await billing_service.cancel_subscription(session, subscription)
        assert subscription.auto_renew is False
        assert subscription.plan == SubscriptionPlan.PRO


async def test_checkout_invalid_cycle_rejected(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        with pytest.raises(BillingError) as excinfo:
            await billing_service.create_checkout(
                session, user_id=user_id, cycle="weekly"  # type: ignore[arg-type]
            )
        assert excinfo.value.code == "BILLING_INVALID_CYCLE"


async def test_pay_checkout_not_pending(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        checkout = await billing_service.create_checkout(
            session, user_id=user_id, cycle=BillingCycle.MONTHLY
        )
        checkout_id = checkout.id
        await billing_service.pay_checkout(session, user_id=user_id, checkout_id=checkout_id)
        with pytest.raises(BillingError) as excinfo:
            await billing_service.pay_checkout(session, user_id=user_id, checkout_id=checkout_id)
        assert excinfo.value.code == "BILLING_CHECKOUT_NOT_PENDING"
        checkout_check = await session.get(type(checkout), checkout_id)
        assert checkout_check is not None
        assert checkout_check.status == CheckoutStatus.PAID


async def test_pay_checkout_not_found(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    user_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        with pytest.raises(NotFoundError):
            await billing_service.pay_checkout(
                session, user_id=user_id, checkout_id=uuid.uuid4()
            )


async def test_pay_checkout_belongs_to_other_user(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    owner_id = await _make_user(sessionmaker)
    other_id = await _make_user(sessionmaker)
    async with sessionmaker() as session:
        checkout = await billing_service.create_checkout(
            session, user_id=owner_id, cycle=BillingCycle.MONTHLY
        )
        with pytest.raises(NotFoundError):
            await billing_service.pay_checkout(
                session, user_id=other_id, checkout_id=checkout.id
            )


# ---------- API 全流程 ----------


async def test_plans_endpoint(client: AsyncClient) -> None:
    response = await client.get("/v1/billing/plans")
    assert response.status_code == 200
    cycles = {item["cycle"] for item in response.json()}
    assert cycles == {"monthly", "quarterly", "yearly"}


async def test_subscription_default_free(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.get("/v1/billing/subscription", headers=headers_of(payload))
    assert response.status_code == 200
    assert response.json()["plan"] == "free"


async def test_full_purchase_flow(client: AsyncClient) -> None:
    payload = await register(client)
    headers = headers_of(payload)

    checkout = await client.post(
        "/v1/billing/checkout", json={"cycle": "quarterly"}, headers=headers
    )
    assert checkout.status_code == 201
    checkout_body = checkout.json()
    assert checkout_body["amount_cents"] == 9900
    assert checkout_body["status"] == "pending"

    paid = await client.post(
        f"/v1/billing/checkout/{checkout_body['id']}/mock-pay", headers=headers
    )
    assert paid.status_code == 200
    body = paid.json()
    assert body["checkout"]["status"] == "paid"
    assert body["subscription"]["plan"] == "pro"

    canceled = await client.post("/v1/billing/cancel", headers=headers)
    assert canceled.status_code == 200
    assert canceled.json()["auto_renew"] is False


async def test_trial_endpoint(client: AsyncClient) -> None:
    payload = await register(client)
    response = await client.post("/v1/billing/trial", headers=headers_of(payload))
    assert response.status_code == 200
    assert response.json()["plan"] == "trial"


async def test_trial_twice_returns_400(client: AsyncClient) -> None:
    payload = await register(client)
    headers = headers_of(payload)
    first = await client.post("/v1/billing/trial", headers=headers)
    assert first.status_code == 200
    second = await client.post("/v1/billing/trial", headers=headers)
    assert second.status_code == 400
    assert second.json()["code"] == "BILLING_TRIAL_USED"


async def test_checkout_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/v1/billing/checkout", json={"cycle": "monthly"})
    assert response.status_code == 401
