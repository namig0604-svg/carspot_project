from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from app.database import Base
from app.models.base import new_id, utcnow


class RideOffer(Base):
    """Предложение места в машине до мероприятия (карпулинг)."""

    __tablename__ = "ride_offers"

    id = Column(String(36), primary_key=True, default=new_id)
    event_id = Column(String(36), index=True, nullable=False)
    driver_id = Column(String(36), index=True, nullable=False)

    departure_point = Column(String(200), nullable=True)
    departure_time = Column(DateTime, nullable=True)
    seats_total = Column(Integer, nullable=False, default=1)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


Index("ix_ride_offers_event", RideOffer.event_id)


class RideBooking(Base):
    """Бронирование места у водителя — один пассажир забронировать место один раз на предложение."""

    __tablename__ = "ride_bookings"
    __table_args__ = (
        UniqueConstraint("offer_id", "passenger_id", name="uq_ride_booking"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    offer_id = Column(String(36), index=True, nullable=False)
    passenger_id = Column(String(36), index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
