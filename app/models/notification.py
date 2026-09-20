"""Лента уведомлений: заявки в друзья, лайки, участие в сходках, комментарии."""
from sqlalchemy import Boolean, Column, DateTime, Index, String, UniqueConstraint

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


class DeviceToken(Base):
    """FCM-токен устройства для push-уведомлений. Один токен — одно
    устройство; при повторной регистрации токена от другого пользователя
    переприсылаем владельца (аккаунт вошёл под другим пользователем на
    аккаунтом на одном телефоне)."""

    __tablename__ = "device_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_device_token"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), index=True, nullable=False)
    token = Column(String(500), nullable=False, index=True)
    platform = Column(String(20), default="android", nullable=False)  # android / ios / web
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
