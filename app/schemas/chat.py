from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPublic


class MessageCreate(BaseModel):
    text: Optional[str] = Field(None, max_length=4000, examples=["Всем привет, кто едет?"])
    image_url: Optional[str] = Field(None, max_length=500)
    message_type: str = Field("text", examples=["text"])


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    room_id: str
    user_id: str
    text: Optional[str] = None
    image_url: Optional[str] = None
    message_type: str
    is_deleted: bool
    created_at: datetime
    user: Optional[UserPublic] = None


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    room_type: str
    title: Optional[str] = None
    event_id: Optional[str] = None
    club_id: Optional[str] = None
    last_message_at: Optional[datetime] = None
    last_message_text: Optional[str] = None
    messages_count: int = 0
    created_at: datetime


class RoomDetail(RoomOut):
    members: List[UserPublic] = []
    unread_count: int = 0


class DirectChatCreate(BaseModel):
    user_id: str = Field(..., description="С кем начать личный чат")


class MessageListResponse(BaseModel):
    room_id: str
    total: int
    limit: int
    offset: int
    items: List[MessageOut]
