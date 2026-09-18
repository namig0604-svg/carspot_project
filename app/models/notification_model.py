"""Лента уведомлений: заявки в друзья, лайки, участие в сходках, комментарии."""
from sqlalchemy import Boolean, Column, DateTime, Index, String

from app.database import Base
from app.models.base import new_id, utcnow

# friend_request / friend_accepted / profile_like / event_join / comment_event / comment_photo
NOTIFICATION_TYPES = (
    "friend_request",
    "friend_accepted",
    "profile_like",
    "event_join",
    "comment_event",
    "comment_photo",
)


class Notification(Base):
    """Одна запись в ленте уведомлений конкретного пользователя."""

    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), index=True, nullable=False)  # кому показываем

    type = Column(String(30), nullable=False, index=True)
    actor_id = Column(String(36), nullable=True)  # кто вызвал событие (лайкнул/присоединился/...)

    target_type = Column(String(30), nullable=True)  # event / club / photo / car / friendship / user
    target_id = Column(String(36), nullable=True)

    message = Column(String(300), nullable=False)  # готовый текст на русском

    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)


Index("ix_notifications_user_read", Notification.user_id, Notification.is_read)
Index("ix_notifications_user_created", Notification.user_id, Notification.created_at)
