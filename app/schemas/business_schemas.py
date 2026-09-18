from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.business import BUSINESS_CATEGORIES
from app.schemas.user import UserPublic


class BusinessCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150, examples=["Tbilisi Tuning Garage"])
    category: str = Field("service", examples=["tuning"])
    description: Optional[str] = Field(None, examples=["Чип-тюнинг, установка выхлопных систем"])
    services: Optional[str] = Field(None, max_length=500, examples=["Чип-тюнинг,Выхлопные системы,Подвеска"])
    logo_url: Optional[str] = Field(None, max_length=500)
    cover_url: Optional[str] = Field(None, max_length=500)

    country: Optional[str] = Field(None, max_length=50, examples=["Georgia"])
    city: Optional[str] = Field(None, max_length=100, examples=["Tbilisi"])
    address: Optional[str] = Field(None, max_length=300)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    phone: Optional[str] = Field(None, max_length=30)
    website: Optional[str] = Field(None, max_length=300)
    instagram: Optional[str] = Field(None, max_length=100)
    work_hours: Optional[str] = Field(None, max_length=200, examples=["Пн-Сб 09:00-19:00"])

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in BUSINESS_CATEGORIES:
            raise ValueError(f"category должен быть одним из: {', '.join(BUSINESS_CATEGORIES)}")
        return v


class BusinessUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    category: Optional[str] = None
    description: Optional[str] = None
    services: Optional[str] = Field(None, max_length=500)
    logo_url: Optional[str] = Field(None, max_length=500)
    cover_url: Optional[str] = Field(None, max_length=500)

    country: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=300)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    phone: Optional[str] = Field(None, max_length=30)
    website: Optional[str] = Field(None, max_length=300)
    instagram: Optional[str] = Field(None, max_length=100)
    work_hours: Optional[str] = Field(None, max_length=200)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in BUSINESS_CATEGORIES:
            raise ValueError(f"category должен быть одним из: {', '.join(BUSINESS_CATEGORIES)}")
        return v


class BusinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: Optional[str] = None
    name: str
    category: str
    description: Optional[str] = None
    services: Optional[str] = None
    logo_url: Optional[str] = None
    cover_url: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    work_hours: Optional[str] = None
    is_verified: bool
    average_rating: float
    reviews_count: int
    views_count: int
    created_at: datetime

    is_favorite: bool = False


class BusinessDetail(BusinessOut):
    owner: Optional[UserPublic] = None
    my_rating: Optional[int] = None


class BusinessListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[BusinessOut]


class BusinessMapMarker(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    average_rating: float
    distance_km: Optional[float] = None


class BusinessReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, examples=[5])
    text: Optional[str] = Field(None, examples=["Быстро и качественно сделали развал-схождение"])
    quality_rating: Optional[int] = Field(None, ge=1, le=5)
    price_rating: Optional[int] = Field(None, ge=1, le=5)
    speed_rating: Optional[int] = Field(None, ge=1, le=5)


class BusinessReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    user_id: str
    rating: int
    text: Optional[str] = None
    quality_rating: Optional[int] = None
    price_rating: Optional[int] = None
    speed_rating: Optional[int] = None
    created_at: datetime
    user: Optional[UserPublic] = None


class BusinessReviewListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[BusinessReviewOut]
