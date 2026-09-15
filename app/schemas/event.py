from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class EventBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    event_type: str  # auto_meetup, racing, photo_session
    country: str
    city: Optional[str] = None
    location_name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    event_date: datetime
    event_time: str  # HH:MM format
    duration_minutes: int = 120

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    event_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    is_cancelled: Optional[bool] = None

class EventResponse(EventBase):
    id: str
    creator_id: str
    participants_count: int
    average_rating: float
    total_photos: int
    is_active: bool
    is_cancelled: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class EventDetailResponse(EventResponse):
    participants: Optional[List[str]] = []  # User IDs

class EventMapResponse(BaseModel):
    id: str
    title: str
    event_type: str
    location_name: str
    latitude: float
    longitude: float
    event_time: str
    event_date: datetime
    participants_count: int
    average_rating: float
    country: str
    city: Optional[str]
    
    class Config:
        from_attributes = True

class EventParticipantResponse(BaseModel):
    id: str
    event_id: str
    user_id: str
    is_attending: bool
    attended: bool
    joined_at: datetime
    
    class Config:
        from_attributes = True