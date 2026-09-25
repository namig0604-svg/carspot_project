from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ParkingSpotSave(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    note: Optional[str] = Field(None, max_length=300)
    photo_url: Optional[str] = None


class ParkingSpotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    latitude: float
    longitude: float
    note: Optional[str] = None
    photo_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
