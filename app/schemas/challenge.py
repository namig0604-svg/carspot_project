from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.challenge import GOAL_TYPES


class ChallengeCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=200, examples=["Осенний марафон"])
    goal_type: str = Field(..., examples=["attend_events"])
    target: int = Field(..., ge=1, le=100000, examples=[3])
    xp_reward: int = Field(0, ge=0, le=1000000)
    coin_reward: int = Field(0, ge=0, le=1000000)
    # id из COSMETICS_CATALOG (app/api/coins.py) — выдаётся бесплатно при
    # выполнении, как обычная покупка за монеты.
    badge_key: Optional[str] = Field(None, max_length=60)
    starts_at: datetime
    ends_at: datetime

    @field_validator("goal_type")
    @classmethod
    def validate_goal_type(cls, v: str) -> str:
        if v not in GOAL_TYPES:
            raise ValueError(f"goal_type должен быть одним из: {', '.join(GOAL_TYPES)}")
        return v

    @field_validator("badge_key")
    @classmethod
    def validate_badge_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from app.api.coins import _COSMETICS_BY_ID

        if v not in _COSMETICS_BY_ID:
            raise ValueError(f"badge_key должен быть id из каталога косметики: {v} не найден")
        return v

    @field_validator("ends_at")
    @classmethod
    def validate_dates(cls, v: datetime, info) -> datetime:
        starts_at = info.data.get("starts_at")
        if starts_at is not None and v <= starts_at:
            raise ValueError("ends_at должен быть позже starts_at")
        return v


class ChallengeUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None
    ends_at: Optional[datetime] = None


class ChallengeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: Optional[str] = None
    goal_type: str
    target: int
    xp_reward: int
    coin_reward: int
    badge_key: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    is_active: bool
    created_at: datetime

    # Прогресс текущего пользователя — подмешивается в ручке, в модели БД нет.
    progress: int = 0
    completed_at: Optional[datetime] = None
    reward_claimed_at: Optional[datetime] = None


class ChallengeListResponse(BaseModel):
    items: list[ChallengeOut]


class ChallengeClaimResponse(BaseModel):
    message: str
    xp_reward: int
    coin_reward: int
    badge_key: Optional[str] = None
    new_xp: int
    new_coin_balance: int
