"""Заявки в друзья и статус дружбы."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.user import UserPublic


class FriendRequestOut(BaseModel):
    """Одна заявка (входящая или отправленная) — с профилем другого человека."""

    id: str
    user: UserPublic
    created_at: datetime


class FriendStatusOut(BaseModel):
    """Статус отношений с конкретным пользователем — для кнопки в профиле."""

    status: str = "none"  # none | friends | pending_sent | pending_received
    friendship_id: Optional[str] = None
