from sqlalchemy import Column, DateTime, Index, String, Text

from app.database import Base
from app.models.base import new_id, utcnow

DOCUMENT_TYPES = (
    "registration",   # СТС
    "insurance_osago",
    "insurance_kasko",
    "inspection",     # диагностическая карта / техосмотр
    "license",        # водительское удостоверение
    "other",
)


class CarDocument(Base):
    """Документ в электронном бардачке: фото + срок действия для напоминаний."""

    __tablename__ = "car_documents"

    id = Column(String(36), primary_key=True, default=new_id)
    car_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)

    type = Column(String(30), nullable=False, default="other")
    title = Column(String(200), nullable=False)
    photo_url = Column(String(500), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    reminder_sent = Column(String(5), nullable=False, default="no")

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


Index("ix_car_documents_expiry", CarDocument.expires_at, CarDocument.reminder_sent)
