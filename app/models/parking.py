from sqlalchemy import Column, DateTime, Float, String, Text, UniqueConstraint

from app.database import Base
from app.models.base import new_id, utcnow


class ParkingSpot(Base):
    """Место, где пользователь оставил машину — одна активная метка на пользователя."""

    __tablename__ = "parking_spots"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_parking_spot_user"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), index=True, nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    note = Column(Text, nullable=True)          # "3 этаж, синий сектор"
    photo_url = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
