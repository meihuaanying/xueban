"""订阅状态机：free / trial / pro 三态 + 到期降级 + mock 收银台。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.errors import BillingError, NotFoundError
from app.models import BillingCycle, Checkout, CheckoutStatus, Subscription, SubscriptionPlan

TRIAL_DAYS = 7


@dataclass(frozen=True, slots=True)
class PlanSpec:
    """付费周期规格。"""

    cycle: BillingCycle
    price_cents: int
    days: int
    title: str


PLAN_SPECS: dict[BillingCycle, PlanSpec] = {
    BillingCycle.MONTHLY: PlanSpec(BillingCycle.MONTHLY, 3900, 30, "月度会员"),
    BillingCycle.QUARTERLY: PlanSpec(BillingCycle.QUARTERLY, 9900, 90, "季度会员"),
    BillingCycle.YEARLY: PlanSpec(BillingCycle.YEARLY, 29900, 365, "年度会员"),
}


async def get_or_create_subscription(session: AsyncSession, user_id: uuid.UUID) -> Subscription:
    """查询订阅；缺失则创建 free 订阅。"""
    result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    subscription = result.scalar_one_or_none()
    if subscription is None:
        subscription = Subscription(user_id=user_id)
        session.add(subscription)
        await session.flush()
    return subscription


def _expire_if_needed(subscription: Subscription) -> bool:
    """到期降级（惰性结算）；返回是否发生变化。"""
    if (
        subscription.plan in (SubscriptionPlan.TRIAL, SubscriptionPlan.PRO)
        and subscription.expires_at is not None
        and subscription.expires_at <= utcnow()
    ):
        subscription.plan = SubscriptionPlan.FREE
        subscription.expires_at = None
        subscription.auto_renew = False
        return True
    return False


async def sync_subscription(session: AsyncSession, subscription: Subscription) -> Subscription:
    """读取订阅前统一同步到期状态。"""
    if _expire_if_needed(subscription):
        await session.flush()
    return subscription


async def start_trial(session: AsyncSession, subscription: Subscription) -> Subscription:
    """开启试用：仅 free 且未用过试用。"""
    await sync_subscription(session, subscription)
    if subscription.plan == SubscriptionPlan.TRIAL:
        raise BillingError("试用正在进行中", code="BILLING_TRIAL_USED")
    if subscription.plan != SubscriptionPlan.FREE:
        raise BillingError("当前订阅状态不可开启试用", code="BILLING_TRIAL_UNAVAILABLE")
    if subscription.trial_used:
        raise BillingError("试用机会已使用", code="BILLING_TRIAL_USED")
    now = utcnow()
    subscription.plan = SubscriptionPlan.TRIAL
    subscription.trial_used = True
    subscription.started_at = now
    subscription.expires_at = now + timedelta(days=TRIAL_DAYS)
    await session.flush()
    return subscription


async def activate_pro(
    session: AsyncSession, subscription: Subscription, cycle: BillingCycle
) -> Subscription:
    """开通/续费 Pro：未过期则从当前到期时间顺延。"""
    await sync_subscription(session, subscription)
    spec = PLAN_SPECS.get(cycle)
    if spec is None:
        raise BillingError("不支持的付费周期", code="BILLING_INVALID_CYCLE")
    now = utcnow()
    base = (
        subscription.expires_at
        if subscription.plan == SubscriptionPlan.PRO
        and subscription.expires_at is not None
        and subscription.expires_at > now
        else now
    )
    subscription.plan = SubscriptionPlan.PRO
    subscription.started_at = subscription.started_at or now
    subscription.expires_at = base + timedelta(days=spec.days)
    subscription.auto_renew = True
    await session.flush()
    return subscription


async def cancel_subscription(session: AsyncSession, subscription: Subscription) -> Subscription:
    """取消自动续费（到期后降级为 free）。"""
    await sync_subscription(session, subscription)
    if subscription.plan != SubscriptionPlan.PRO:
        raise BillingError("当前没有可取消的 Pro 订阅", code="BILLING_CANCEL_UNAVAILABLE")
    subscription.auto_renew = False
    await session.flush()
    return subscription


async def create_checkout(
    session: AsyncSession, *, user_id: uuid.UUID, cycle: BillingCycle
) -> Checkout:
    """创建 mock 收银台单据。"""
    spec = PLAN_SPECS.get(cycle)
    if spec is None:
        raise BillingError("不支持的付费周期", code="BILLING_INVALID_CYCLE")
    checkout = Checkout(user_id=user_id, cycle=cycle, amount_cents=spec.price_cents)
    session.add(checkout)
    await session.flush()
    return checkout


async def pay_checkout(
    session: AsyncSession, *, user_id: uuid.UUID, checkout_id: uuid.UUID
) -> tuple[Checkout, Subscription]:
    """mock 支付：单据转 paid 并开通 Pro。"""
    result = await session.execute(select(Checkout).where(Checkout.id == checkout_id))
    checkout = result.scalar_one_or_none()
    if checkout is None or checkout.user_id != user_id:
        raise NotFoundError("收银台单据不存在", code="BILLING_CHECKOUT_NOT_FOUND")
    if checkout.status != CheckoutStatus.PENDING:
        raise BillingError("单据状态不可支付", code="BILLING_CHECKOUT_NOT_PENDING")
    checkout.status = CheckoutStatus.PAID
    checkout.paid_at = utcnow()
    subscription = await get_or_create_subscription(session, user_id)
    await activate_pro(session, subscription, checkout.cycle)
    await session.flush()
    return checkout, subscription
