from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.booking import BOOKING_STATUSES
from app.schemas.user import UserPublic


class BookingCreate(BaseModel):
    service: Optional[str] = Field(None, max_length=200, examples=["Развал-схождение"])
    requested_at: datetime = Field(..., description="Желаемые дата и время визита")
    note: Optional[str] = Field(None, max_length=1000, examples=["Стук в передней подвеске"])


class BookingStatusUpdate(BaseModel):
    status: str = Field(..., examples=["confirmed"])
    decline_reason: Optional[str] = Field(None, max_length=300)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in BOOKING_STATUSES:
            raise ValueError(f"status должен быть одним из: {', '.join(BOOKING_STATUSES)}")
        return v


class BusinessBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    logo_url: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    user_id: str
    service: Optional[str] = None
    requested_at: datetime
    note: Optional[str] = None
    status: str
    decline_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    user: Optional[UserPublic] = None
    business: Optional[BusinessBrief] = None


class BookingListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[BookingOut]
