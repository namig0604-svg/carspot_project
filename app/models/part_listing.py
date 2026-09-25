from sqlalchemy import Column, DateTime, Float, Index, String, Text

from app.database import Base
from app.models.base import new_id, utcnow

LISTING_STATUSES = ("active", "reserved", "sold", "removed")

PART_CATEGORIES = (
    "engine",
    "suspension",
    "brakes",
    "body",
    "interior",
    "electronics",
    "wheels_tires",
    "exhaust",
    "other",
)


class PartListing(Base):
    """Объявление о продаже б/у запчасти между пользователями."""

    __tablename__ = "part_listings"

    id = Column(String(36), primary_key=True, default=new_id)
    seller_id = Column(String(36), index=True, nullable=False)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    category = Column(String(20), nullable=False, default="other")
    car_brand = Column(String(50), nullable=True)   # к какой марке подходит
    car_model = Column(String(50), nullable=True)

    photo_url = Column(String(500), nullable=True)      # главное фото
    photos = Column(Text, nullable=True)                 # доп. фото через запятую

    city = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="active")

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


Index("ix_part_listings_status_created", PartListing.status, PartListing.created_at)
Index("ix_part_listings_category", PartListing.category)
