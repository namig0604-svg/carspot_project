from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPublic


class RideOfferCreate(BaseModel):
    event_id: str
    departure_point: Optional[str] = Field(None, max_length=200)
    departure_time: Optional[datetime] = None
    seats_total: int = Field(1, ge=1, le=8)
    note: Optional[str] = Field(None, max_length=500)


class RideOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    driver_id: str
    departure_point: Optional[str] = None
    departure_time: Optional[datetime] = None
    seats_total: int
    seats_taken: int = 0
    note: Optional[str] = None
    created_at: datetime
    driver: Optional[UserPublic] = None
    passengers: List[UserPublic] = []
    i_booked: bool = False


class RideOfferListResponse(BaseModel):
    items: List[RideOfferOut]
