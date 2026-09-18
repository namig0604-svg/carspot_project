"""Лента уведомлений."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserPublic


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    message: str
    is_read: bool
    created_at: datetime
    actor: Optional[UserPublic] = None


class NotificationListResponse(BaseModel):
    total: int
    unread_count: int
    limit: int
    offset: int
    items: List[NotificationOut]


class UnreadCountOut(BaseModel):
    unread_count: int
