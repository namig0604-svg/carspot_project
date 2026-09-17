from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.event import EVENT_TYPES
from app.schemas.user import UserPublic


class EventBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=200, examples=["Ночная сходка на Ваке"])
    description: Optional[str] = Field(None, examples=["Собираемся, общаемся, катаемся"])
    event_type: str = Field("meetup", examples=["meetup"])
    cover_url: Optional[str] = Field(None, max_length=500)

    country: Optional[str] = Field(None, max_length=50, examples=["Georgia"])
    city: Optional[str] = Field(None, max_length=100, examples=["Tbilisi"])
    location_name: Optional[str] = Field(None, max_length=200, examples=["Vake Park"])
    address: Optional[str] = Field(None, max_length=300)
    latitude: float = Field(..., ge=-90, le=90, examples=[41.7151])
    longitude: float = Field(..., ge=-180, le=180, examples=[44.7671])

    event_date: datetime = Field(..., examples=["2026-10-01T20:00:00"])
    event_time: Optional[str] = Field(None, max_length=10, examples=["20:00"])
    duration_minutes: int = Field(120, ge=15, le=10080)

    max_participants: Optional[int] = Field(None, ge=2, le=100000)
    is_private: bool = False
    entry_fee: Optional[str] = Field(None, max_length=50)
    requirements: Optional[str] = None
    club_id: Optional[str] = None

    @field_validator("event_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in EVENT_TYPES:
            raise ValueError(f"event_type должен быть одним из: {', '.join(EVENT_TYPES)}")
        return v


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = None
    event_type: Optional[str] = None
    cover_url: Optional[str] = Field(None, max_length=500)
    country: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=100)
    location_name: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=300)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    event_date: Optional[datetime] = None
    event_time: Optional[str] = Field(None, max_length=10)
    duration_minutes: Optional[int] = Field(None, ge=15, le=10080)
    max_participants: Optional[int] = Field(None, ge=2, le=100000)
    is_private: Optional[bool] = None
    entry_fee: Optional[str] = Field(None, max_length=50)
    requirements: Optional[str] = None
    is_cancelled: Optional[bool] = None

    @field_validator("event_type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in EVENT_TYPES:
            raise ValueError(f"event_type должен быть одним из: {', '.join(EVENT_TYPES)}")
        return v


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    creator_id: str
    club_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    event_type: str
    cover_url: Optional[str] = None

    country: Optional[str] = None
    city: Optional[str] = None
    location_name: Optional[str] = None
    address: Optional[str] = None
    latitude: float
    longitude: float

    event_date: datetime
    event_time: Optional[str] = None
    duration_minutes: int

    max_participants: Optional[int] = None
    is_private: bool
    entry_fee: Optional[str] = None
    requirements: Optional[str] = None

    participants_count: int
    photos_count: int
    average_rating: float
    ratings_count: int
    views_count: int

    is_active: bool
    is_cancelled: bool
    created_at: datetime


class EventDetail(EventOut):
    """Детальная карточка события."""

    creator: Optional[UserPublic] = None
    chat_room_id: Optional[str] = None
    is_joined: bool = False
    is_creator: bool = False
    my_rating: Optional[int] = None


class EventMapMarker(BaseModel):
    """Облегчённая метка для карты — чтобы не грузить лишнее на клиент."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    event_type: str
    latitude: float
    longitude: float
    event_date: datetime
    city: Optional[str] = None
    participants_count: int = 0
    average_rating: float = 0.0
    distance_km: Optional[float] = None


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    user_id: str
    car_id: Optional[str] = None
    status: str
    joined_at: datetime
    user: Optional[UserPublic] = None


class JoinEventRequest(BaseModel):
    car_id: Optional[str] = Field(None, description="На какой машине приедешь")
    status: str = Field("going", examples=["going"])

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("going", "maybe"):
            raise ValueError("status должен быть 'going' или 'maybe'")
        return v


class EventListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[EventOut]
