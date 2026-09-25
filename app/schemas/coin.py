"""CarSpot Coins — внутренняя валюта: баланс, пакеты покупки, история."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CoinBalanceOut(BaseModel):
    balance: int


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
