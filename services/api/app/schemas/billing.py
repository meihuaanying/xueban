"""订阅/收银台契约。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import BillingCycle


class PlanResponse(BaseModel):
    """付费周期规格。"""

    cycle: BillingCycle
    title: str
    price_cents: int
    days: int


class SubscriptionResponse(BaseModel):
    """订阅状态。"""

    model_config = ConfigDict(from_attributes=True)

    plan: str
    started_at: datetime | None = None
    expires_at: datetime | None = None
    trial_used: bool
    auto_renew: bool


class CheckoutRequest(BaseModel):
    """创建收银台单据请求。"""

    cycle: BillingCycle


class CheckoutResponse(BaseModel):
    """收银台单据。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cycle: BillingCycle
    amount_cents: int
    currency: str
    status: str
    paid_at: datetime | None = None


class PayCheckoutResponse(BaseModel):
    """mock 支付结果。"""

    checkout: CheckoutResponse
    subscription: SubscriptionResponse
