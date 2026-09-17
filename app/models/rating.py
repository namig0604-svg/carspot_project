from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base
from app.models.base import new_id, utcnow


class EventRating(Base):
    """Оценка сходки. Один пользователь — одна оценка на событие."""

    __tablename__ = "event_ratings"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_rating"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    event_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)

    rating = Column(Integer, nullable=False)          # 1..5
    review = Column(Text, nullable=True)

    atmosphere_rating = Column(Integer, nullable=True)
    organization_rating = Column(Integer, nullable=True)
    location_rating = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)


class UserRating(Base):
    """Оценка пользователя другим пользователем."""

    __tablename__ = "user_ratings"
    __table_args__ = (
        UniqueConstraint("rated_user_id", "rater_user_id", name="uq_user_rating"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    rated_user_id = Column(String(36), index=True, nullable=False)
    rater_user_id = Column(String(36), index=True, nullable=False)

    rating = Column(Integer, nullable=False)          # 1..5
    review = Column(Text, nullable=True)

    punctuality_rating = Column(Integer, nullable=True)
    behavior_rating = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)


class SpotRating(Base):
    """Оценка места (спота) — парковка, трасса, площадка."""

    __tablename__ = "spot_ratings"

    id = Column(String(36), primary_key=True, default=new_id)
    event_id = Column(String(36), index=True, nullable=True)
    user_id = Column(String(36), index=True, nullable=False)

    spot_name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    rating = Column(Integer, nullable=False)          # 1..5
    review = Column(Text, nullable=True)

    accessibility_rating = Column(Integer, nullable=True)
    parking_rating = Column(Integer, nullable=True)
    safety_rating = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
