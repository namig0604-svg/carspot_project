from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPublic


class EventRatingCreate(BaseModel):
    event_id: str
    rating: int = Field(..., ge=1, le=5, examples=[5])
    review: Optional[str] = Field(None, examples=["Отличная сходка, много машин"])
    atmosphere_rating: Optional[int] = Field(None, ge=1, le=5)
    organization_rating: Optional[int] = Field(None, ge=1, le=5)
    location_rating: Optional[int] = Field(None, ge=1, le=5)


class EventRatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    user_id: str
    rating: int
    review: Optional[str] = None
    atmosphere_rating: Optional[int] = None
    organization_rating: Optional[int] = None
    location_rating: Optional[int] = None
    created_at: datetime
    user: Optional[UserPublic] = None


class UserRatingCreate(BaseModel):
    rated_user_id: str
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None
    punctuality_rating: Optional[int] = Field(None, ge=1, le=5)
    behavior_rating: Optional[int] = Field(None, ge=1, le=5)


class UserRatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rated_user_id: str
    rater_user_id: str
    rating: int
    review: Optional[str] = None
    punctuality_rating: Optional[int] = None
    behavior_rating: Optional[int] = None
    created_at: datetime
    user: Optional[UserPublic] = None


class SpotRatingCreate(BaseModel):
    spot_name: str = Field(..., max_length=200, examples=["Парковка у Вейк-парка"])
    event_id: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None
    accessibility_rating: Optional[int] = Field(None, ge=1, le=5)
    parking_rating: Optional[int] = Field(None, ge=1, le=5)
    safety_rating: Optional[int] = Field(None, ge=1, le=5)


class SpotRatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: Optional[str] = None
    user_id: str
    spot_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: int
    review: Optional[str] = None
    accessibility_rating: Optional[int] = None
    parking_rating: Optional[int] = None
    safety_rating: Optional[int] = None
    created_at: datetime


class RatingSummary(BaseModel):
    average_rating: float
    ratings_count: int
    breakdown: dict


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: Optional[str] = None
    car_id: Optional[str] = None
    user_id: str
    photo_url: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    caption: Optional[str] = None
    likes_count: int
    is_liked: bool = False
    is_featured: bool
    created_at: datetime


class PhotoListResponse(BaseModel):
    total: int
    items: List[PhotoOut]
