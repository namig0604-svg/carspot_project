from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.part_listing import LISTING_STATUSES, PART_CATEGORIES
from app.schemas.user import UserPublic


class PartListingCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    price: float = Field(..., ge=0)
    category: str = Field("other")
    car_brand: Optional[str] = Field(None, max_length=50)
    car_model: Optional[str] = Field(None, max_length=50)
    photo_url: Optional[str] = None
    photos: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str) -> str:
        if v not in PART_CATEGORIES:
            raise ValueError(f"category должен быть одним из: {', '.join(PART_CATEGORIES)}")
        return v


class PartListingStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in LISTING_STATUSES:
            raise ValueError(f"status должен быть одним из: {', '.join(LISTING_STATUSES)}")
        return v


class PartListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_id: str
    title: str
    description: Optional[str] = None
    price: float
    category: str
    car_brand: Optional[str] = None
    car_model: Optional[str] = None
    photo_url: Optional[str] = None
    photos: Optional[str] = None
    city: Optional[str] = None
    status: str
    created_at: datetime
    seller: Optional[UserPublic] = None


class PartListingListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[PartListingOut]
