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
    """Цены и состояние бустов для экрана "Прокачка профиля". Сам уровень
    (сколько всего XP и на каком он уровне) фронтенд считает сам —
    lib/utils/gamification.dart — суммируя свою статистику с полем xp из
    UserMe/UserPublic (бонус, купленный за монеты); бэкенд его не дублирует,
    чтобы не могло разъехаться с тем, что показывает профиль."""

    bonus_xp: int
    xp_boost_cost: int
    xp_boost_grant_amount: int
    profile_boosted_until: Optional[datetime] = None
    profile_boost_cost: int
    profile_boost_is_free: bool = False  # true для CarSpot Pro
    boost_duration_hours: int
