"""Схемы для чувствительных админ-ручек: ручная выдача монет, ранги администрации."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AdminGrantCoinsRequest(BaseModel):
    amount: int = Field(..., gt=0, le=1_000_000)
    reason: Optional[str] = Field(None, max_length=200)


class AdminGrantCoinsOut(BaseModel):
    user_id: str
    balance: int
    granted: int


class AdminSetRankRequest(BaseModel):
    rank: Optional[str] = Field(
        None, description="moderator | administrator | tech_admin | developer, либо null — снять ранг"
    )


class AdminRankOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    admin_rank: Optional[str] = None
