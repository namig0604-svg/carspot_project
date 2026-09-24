"""Онлайн-запись в автосервис/ателье — заявка клиента на конкретные дату/время."""
from sqlalchemy import Column, DateTime, Index, String, Text

from app.database import Base
from app.models.base import new_id, utcnow

BOOKING_STATUSES = ("pending", "confirmed", "declined", "cancelled", "completed")


class BusinessBooking(Base):
    """Запись клиента на услугу в конкретном автосервисе/ателье.

    Жизненный цикл статуса: pending -> confirmed/declined (решает владелец
    заведения) -> confirmed можно перевести в completed (услуга оказана) или
    отменить (cancelled — это делает клиент)."""

    __tablename__ = "business_bookings"

    id = Column(String(36), primary_key=True, default=new_id)
    business_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)

    service = Column(String(200), nullable=True)  # одна из business.services, либо своя формулировка
    requested_at = Column(DateTime, nullable=False, index=True)  # желаемые дата и время визита
    note = Column(Text, nullable=True)  # что нужно сделать / комментарий клиента

    status = Column(String(20), default="pending", nullable=False, index=True)
    decline_reason = Column(String(300), nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


Index("ix_business_bookings_business_status", BusinessBooking.business_id, BusinessBooking.status)
Index("ix_business_bookings_user_status", BusinessBooking.user_id, BusinessBooking.status)
