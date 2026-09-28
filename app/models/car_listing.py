from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from app.database import Base
from app.models.base import new_id, utcnow

CAR_LISTING_STATUSES = ("active", "reserved", "sold", "removed")


class CarListing(Base):
    """Объявление о продаже машины — витрина «Машина на продажу»."""

    __tablename__ = "car_listings"

    id = Column(String(36), primary_key=True, default=new_id)
    seller_id = Column(String(36), index=True, nullable=False)

    make = Column(String(50), nullable=False)
    model = Column(String(50), nullable=False)
    year = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    mileage_km = Column(Float, nullable=True)
    description = Column(Text, nullable=True)

    photo_url = Column(String(500), nullable=True)  # главное фото
    photos = Column(Text, nullable=True)  # доп. фото через запятую

    city = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="active")

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


Index("ix_car_listings_status_created", CarListing.status, CarListing.created_at)
Index("ix_car_listings_make", CarListing.make)
