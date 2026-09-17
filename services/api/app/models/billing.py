"""订阅与收银台模型（free/trial/pro 三态状态机）。"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class SubscriptionPlan(enum.StrEnum):
    """订阅档位。"""

    FREE = "free"
    TRIAL = "trial"
    PRO = "pro"


class BillingCycle(enum.StrEnum):
    """付费周期。"""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class CheckoutStatus(enum.StrEnum):
    """收银台单据状态。"""

    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class Subscription(Base, TimestampMixin):
    """用户订阅状态（每用户一条）。"""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(
        SAEnum(
            SubscriptionPlan,
            name="subscription_plan",
            native_enum=False,
            length=20,
            create_constraint=True,
        ),
        default=SubscriptionPlan.FREE,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_used: Mapped[bool] = mapped_column(default=False, nullable=False)
    auto_renew: Mapped[bool] = mapped_column(default=True, nullable=False)


class Checkout(Base, TimestampMixin):
    """mock 收银台单据（真实支付接入时保留接口）。"""

    __tablename__ = "checkouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    cycle: Mapped[BillingCycle] = mapped_column(
        SAEnum(
            BillingCycle, name="billing_cycle", native_enum=False, length=20, create_constraint=True
        ),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="CNY", nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="mock", nullable=False)
    status: Mapped[CheckoutStatus] = mapped_column(
        SAEnum(
            CheckoutStatus,
            name="checkout_status",
            native_enum=False,
            length=20,
            create_constraint=True,
        ),
        default=CheckoutStatus.PENDING,
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
