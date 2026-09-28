from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ConvoyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["Ночной заезд на набережную"])
    destination_label: Optional[str] = Field(None, max_length=200)
    destination_lat: Optional[float] = None
    destination_lng: Optional[float] = None


class ConvoyJoinIn(BaseModel):
    invite_code: str = Field(..., min_length=4, max_length=8)


class ConvoyDestinationUpdate(BaseModel):
    destination_label: Optional[str] = Field(None, max_length=200)
    destination_lat: Optional[float] = None
    destination_lng: Optional[float] = None


class ConvoyMemberOut(BaseModel):
    user_id: str
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_creator: bool = False
    is_me: bool = False
    joined_at: datetime
    lat: Optional[float] = None
    lng: Optional[float] = None
    location_updated_at: Optional[datetime] = None


class ConvoyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    creator_id: str
    invite_code: str
    status: str
    destination_label: Optional[str] = None
    destination_lat: Optional[float] = None
    destination_lng: Optional[float] = None
    created_at: datetime
    ended_at: Optional[datetime] = None
    members: List[ConvoyMemberOut] = []
