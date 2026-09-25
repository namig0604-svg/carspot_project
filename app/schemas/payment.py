"""Платежи Premium (Trybit)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PremiumPlanOut(BaseModel):
    id: str
    title: str
    tier: str  # "basic" | "pro"
    days: int
    amount_usd: float


class CheckoutRequest(BaseModel):
    plan: str  # "month" | "year"


class GooglePlayVerifyRequest(BaseModel):
    product_id: str  # id товара в Play Console, напр. "carspot_premium_month"
    purchase_token: str  # PurchaseDetails.verificationData.serverVerificationData из in_app_purchase


class CheckoutOut(BaseModel):
    payment_id: str
    pay_url: str
    status: str
    amount_usd: float
    plan: str
    tier: str


class PaymentStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan: str
    tier: str = "pro"
    amount_usd: float
    days: int
    status: str
    provider: str = "trybit"
    created_at: datetime
    paid_at: Optional[datetime] = None
