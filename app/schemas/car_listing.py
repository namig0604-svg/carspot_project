from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.base import utcnow
from app.models.car_listing import CAR_LISTING_STATUSES
from app.schemas.user import UserPublic


class CarListingCreate(BaseModel):
    make: str = Field(..., max_length=50, examples=["Toyota"])
    model: str = Field(..., max_length=50, examples=["Camry"])
    year: int = Field(..., ge=1900, examples=[2020])
    price: float = Field(..., ge=0)
    mileage_km: Optional[float] = Field(None, ge=0, le=10_000_000)
    description: Optional[str] = Field(None, max_length=2000)
    photo_url: Optional[str] = None
    photos: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)

    @field_validator("year")
    @classmethod
    def _check_year(cls, v: int) -> int:
        max_year = utcnow().year + 1
        if v > max_year:
            raise ValueError(f"year не может быть больше {max_year}")
        return v


class CarListingStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in CAR_LISTING_STATUSES:
            raise ValueError(f"status должен быть одним из: {', '.join(CAR_LISTING_STATUSES)}")
        return v


class CarListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_id: str
    make: str
    model: str
    year: int
    price: float
    mileage_km: Optional[float] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None
    photos: Optional[str] = None
    city: Optional[str] = None
    status: str
    created_at: datetime
    seller: Optional[UserPublic] = None


class CarListingListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[CarListingOut]
