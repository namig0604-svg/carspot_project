"""Платежи за Premium через Trybit (крипто-эквайринг, работает в странах СНГ)."""
from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database import Base
from app.models.base import new_id, utcnow


class PremiumPayment(Base):
    """Один платёж за подписку Premium."""

    __tablename__ = "premium_payments"

    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), index=True, nullable=False)

    plan = Column(String(20), nullable=False)          # "month" / "year"
    tier = Column(String(10), nullable=False, default="pro")  # "basic" / "pro"
    amount_usd = Column(Float, nullable=False)
    days = Column(Integer, nullable=False)

    provider = Column(String(20), default="trybit", nullable=False)  # "trybit" | "google_play"
    provider_invoice_id = Column(String(100), nullable=True)
    order_id = Column(String(64), unique=True, index=True, nullable=False)
    pay_url = Column(String(500), nullable=True)

    # Только для provider="google_play" — purchaseToken из Google Play
    # Billing. Уникален, чтобы один и тот же токен нельзя было прислать
    # повторно и получить Premium второй раз.
    purchase_token = Column(String(300), unique=True, index=True, nullable=True)

    # pending -> paid (или overpaid) / expired
    status = Column(String(20), default="pending", nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    paid_at = Column(DateTime, nullable=True)
