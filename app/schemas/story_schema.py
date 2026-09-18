"""Истории 24ч."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserPublic


class StoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    image_url: str
    caption: Optional[str] = None
    event_id: Optional[str] = None
    car_id: Optional[str] = None
    views_count: int = 0
    created_at: datetime
    # Всегда выставляется вручную в _story_to_out() (created_at + 24ч) — модель
    # Story не хранит эту колонку, поэтому нужен default для model_validate().
    expires_at: Optional[datetime] = None
    is_mine: bool = False
    is_viewed: bool = False


class StoryRingOut(BaseModel):
    """Одна «карточка» в ленте историй — аватар с кольцом + метаданные,
    без самих историй (их подгружает GET /api/stories/user/{user_id})."""

    user: UserPublic
    stories_count: int
    has_unseen: bool
    latest_created_at: datetime


class StoryFeedResponse(BaseModel):
    items: List[StoryRingOut]
