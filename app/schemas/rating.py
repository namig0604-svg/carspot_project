from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class EventRatingBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None
    atmosphere_rating: Optional[int] = Field(None, ge=1, le=5)
    organization_rating: Optional[int] = Field(None, ge=1, le=5)
    location_rating: Optional[int] = Field(None, ge=1, le=5)

class EventRatingCreate(EventRatingBase):
    event_id: str

class EventRatingResponse(EventRatingBase):
    id: str
    event_id: str
    user_id: str
    is_helpful: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserRatingBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None
    punctuality_rating: Optional[int] = Field(None, ge=1, le=5)
    behavior_rating: Optional[int] = Field(None, ge=1, le=5)

class UserRatingCreate(UserRatingBase):
    rated_user_id: str

class UserRatingResponse(UserRatingBase):
    id: str
    rated_user_id: str
    rater_user_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class SpotRatingBase(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = None
    accessibility_rating: Optional[int] = Field(None, ge=1, le=5)
    parking_rating: Optional[int] = Field(None, ge=1, le=5)
    safety_rating: Optional[int] = Field(None, ge=1, le=5)

class SpotRatingCreate(SpotRatingBase):
    event_id: str
    spot_name: str
    latitude: str
    longitude: str

class SpotRatingResponse(SpotRatingBase):
    id: str
    event_id: str
    user_id: str
    spot_name: str
    latitude: str
    longitude: str
    created_at: datetime
    
    class Config:
        from_attributes = True
