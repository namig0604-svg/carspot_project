from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base
from app.models.base import new_id, utcnow

# Типы сходок — используются и на клиенте для фильтров/иконок
EVENT_TYPES = (
    "meetup",     # обычная сходка
    "racing",     # заезды
    "drift",      # дрифт
    "drag",       # драг
    "offroad",    # офф-роуд
    "show",       # автовыставка
    "cruise",     # покатушки
    "track_day",  # трек-день
    "charity",    # благотворительность
    "other",
)


class Event(Base):
    """Сходка / мероприятие на карте."""

    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=new_id)
    creator_id = Column(String(36), index=True, nullable=False)
    club_id = Column(String(36), index=True, nullable=True)  # событие клуба

    # --- Описание ---
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(30), default="meetup", nullable=False, index=True)
    cover_url = Column(String(500), nullable=True)

    # --- География (для карты) ---
    country = Column(String(50), nullable=True, index=True)
    city = Column(String(100), nullable=True, index=True)
    location_name = Column(String(200), nullable=True)
    address = Column(String(300), nullable=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)

    # --- Время ---
    event_date = Column(DateTime, nullable=False, index=True)
    event_time = Column(String(10), nullable=True)   # "20:00" для отображения
    duration_minutes = Column(Integer, default=120, nullable=False)

    # --- Правила ---
    max_participants = Column(Integer, nullable=True)   # None = без лимита
    is_private = Column(Boolean, default=False, nullable=False)
    entry_fee = Column(String(50), nullable=True)       # "бесплатно" / "20 GEL"
    requirements = Column(Text, nullable=True)

    # --- Статистика ---
    participants_count = Column(Integer, default=0, nullable=False)
    photos_count = Column(Integer, default=0, nullable=False)
    average_rating = Column(Float, default=0.0, nullable=False)
    ratings_count = Column(Integer, default=0, nullable=False)
    views_count = Column(Integer, default=0, nullable=False)

    # --- Статусы ---
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_cancelled = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class EventParticipant(Base):
    """Участие пользователя в событии."""

    __tablename__ = "event_participants"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_participant"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    event_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)
    car_id = Column(String(36), nullable=True)          # на какой машине приедет
    status = Column(String(20), default="going", nullable=False)  # going / maybe / left
    joined_at = Column(DateTime, default=utcnow, nullable=False)


Index("ix_events_geo", Event.latitude, Event.longitude)
Index("ix_events_date_active", Event.event_date, Event.is_active)
