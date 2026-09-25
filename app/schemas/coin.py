"""CarSpot Coins — внутренняя валюта: баланс, пакеты покупки, история."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CoinBalanceOut(BaseModel):
    balance: int
    boost_cost_event: int
    boost_cost_business: int


class CoinPackageOut(BaseModel):
    product_id: str
    coins: int
    bonus_coins: int
    total_coins: int
    price_usd: float
    title: str


class CoinPurchaseVerifyRequest(BaseModel):
    product_id: str  # id товара в Play Console, напр. "carspot_coins_550"
    purchase_token: str  # PurchaseDetails.verificationData.serverVerificationData


class CoinPurchaseOut(BaseModel):
    balance: int
    credited: int


class CoinTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    amount: int
    balance_after: int
    type: str
    reference_id: Optional[str] = None
    created_at: datetime


class CosmeticOut(BaseModel):
    id: str
    type: str  # "frame" | "badge" | "name_color"
    title: str
    cost: int
    owned: bool = False
    equipped: bool = False


class CosmeticActionRequest(BaseModel):
    cosmetic_id: str


class CosmeticUnequipRequest(BaseModel):
    slot: str  # "frame" | "badge" | "name_color"


class ProfileStatusOut(BaseModel):
    """Всё, что нужно экрану "Прокачка профиля": уровень/XP с порогами для
    прогресс-бара и состояние обоих временных бустов — чтобы фронтенду не
    дублировать формулу уровня из app.services.level_for_xp у себя в Dart."""

    level: int
    xp: int
    xp_for_current_level: int
    xp_for_next_level: int
    profile_boosted_until: Optional[datetime] = None
    xp_boost_until: Optional[datetime] = None
    profile_boost_cost: int
    xp_boost_cost: int
    xp_boost_hours: int
    xp_boost_multiplier: int
    boost_duration_hours: int
