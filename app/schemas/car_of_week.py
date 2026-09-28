from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.car import CarOut
from app.schemas.user import UserPublic


class CarOfWeekEntryCreate(BaseModel):
    car_id: str = Field(..., examples=["a1b2c3d4-..."])


class CarOfWeekEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    week_key: str
    user_id: str
    car_id: str
    votes_count: int
    created_at: datetime
    car: Optional[CarOut] = None
    owner: Optional[UserPublic] = None
    my_voted: bool = False
    is_mine: bool = False


class CarOfWeekEntryListResponse(BaseModel):
    week_key: str
    items: List[CarOfWeekEntryOut]
