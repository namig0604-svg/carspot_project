from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DailyLoginStatusResponse(BaseModel):
    current_streak: int  # сколько дней подряд уже забрано (0, если стрика ещё нет)
    can_claim: bool
    next_day: int  # какой день (1..7) будет засчитан при следующем claim
    last_claim_at: Optional[datetime] = None


class DailyLoginClaimResponse(BaseModel):
    message: str
    day: int  # какой день стрика засчитан этим claim'ом (1..7)
    xp_reward: int
    coin_reward: int
    bonus_premium_days: Optional[int] = None
    bonus_premium_tier: Optional[str] = None
    new_xp: int
    new_coin_balance: int
    next_streak_day: int  # какой день будет следующим (для UI)
