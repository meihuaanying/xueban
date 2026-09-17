"""订阅与收银台路由（mock 支付先行）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models import User
from app.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PayCheckoutResponse,
    PlanResponse,
    SubscriptionResponse,
)
from app.services import billing_service

router = APIRouter(prefix="/v1/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanResponse], summary="订阅套餐")
async def list_plans() -> list[PlanResponse]:
    """返回可购套餐（不含免费档）。"""
    return [
        PlanResponse(
            cycle=spec.cycle, title=spec.title, price_cents=spec.price_cents, days=spec.days
        )
        for spec in billing_service.PLAN_SPECS.values()
    ]


@router.get("/subscription", response_model=SubscriptionResponse, summary="当前订阅状态")
async def get_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionResponse:
    """查询订阅（自动处理到期降级）。"""
    subscription = await billing_service.get_or_create_subscription(session, user.id)
    await billing_service.sync_subscription(session, subscription)
    await session.commit()
    return SubscriptionResponse.model_validate(subscription)


@router.post("/trial", response_model=SubscriptionResponse, summary="开启试用")
async def start_trial(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionResponse:
    """开启 7 天试用（每人一次）。"""
    subscription = await billing_service.get_or_create_subscription(session, user.id)
    await billing_service.start_trial(session, subscription)
    await session.commit()
    return SubscriptionResponse.model_validate(subscription)


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建收银台单据（mock）",
)
async def create_checkout(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CheckoutResponse:
    """创建 mock 收银台单据。"""
    checkout = await billing_service.create_checkout(session, user_id=user.id, cycle=payload.cycle)
    await session.commit()
    return CheckoutResponse.model_validate(checkout)


@router.post(
    "/checkout/{checkout_id}/mock-pay",
    response_model=PayCheckoutResponse,
    summary="mock 支付回调",
)
async def mock_pay(
    checkout_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PayCheckoutResponse:
    """模拟支付成功并开通 Pro（真实支付接入时替换为回调验签）。"""
    checkout, subscription = await billing_service.pay_checkout(
        session, user_id=user.id, checkout_id=checkout_id
    )
    request.app.state.observability.record_event(
        trace_id=getattr(request.state, "trace_id", None),
        name="billing.mock_pay",
        input_payload={"checkout_id": str(checkout_id)},
        output_payload={
            "plan": subscription.plan.value,
            "expires_at": str(subscription.expires_at),
        },
        metadata={"user_id": str(user.id), "amount_cents": checkout.amount_cents},
    )
    await session.commit()
    return PayCheckoutResponse(
        checkout=CheckoutResponse.model_validate(checkout),
        subscription=SubscriptionResponse.model_validate(subscription),
    )


@router.post("/cancel", response_model=SubscriptionResponse, summary="取消自动续费")
async def cancel_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionResponse:
    """取消 Pro 自动续费（到期降级为 free）。"""
    subscription = await billing_service.get_or_create_subscription(session, user.id)
    await billing_service.cancel_subscription(session, subscription)
    await session.commit()
    return SubscriptionResponse.model_validate(subscription)
