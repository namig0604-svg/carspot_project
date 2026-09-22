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

# Категории заведений — используются и на клиенте для фильтров/иконок
BUSINESS_CATEGORIES = (
    "service",     # автосервис (ремонт, ТО)
    "tuning",      # тюнинг-ателье
    "detailing",   # детейлинг / полировка / керамика
    "body_shop",   # кузовной ремонт и покраска
    "tire",        # шиномонтаж
    "car_wash",    # автомойка
    "electric",    # автоэлектрик
    "parts",       # магазин запчастей
    "other",
)


class Business(Base):
    """Автосервис / тюнинг-ателье / другое авто-заведение — каталог с картой и отзывами."""

    __tablename__ = "businesses"

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(36), index=True, nullable=True)  # добавивший пользователь

    name = Column(String(150), nullable=False, index=True)
    category = Column(String(30), default="service", nullable=False, index=True)
    description = Column(Text, nullable=True)
    services = Column(String(500), nullable=True)   # "Развал-схождение,Чип-тюнинг,Покраска"
    logo_url = Column(String(500), nullable=True)
    cover_url = Column(String(500), nullable=True)

    # --- География (для карты, по аналогии со сходками) ---
    country = Column(String(50), nullable=True, index=True)
    city = Column(String(100), nullable=True, index=True)
    address = Column(String(300), nullable=True)
    latitude = Column(Float, nullable=True, index=True)
    longitude = Column(Float, nullable=True, index=True)

    # --- Контакты ---
    phone = Column(String(30), nullable=True)
    website = Column(String(300), nullable=True)
    instagram = Column(String(100), nullable=True)
    work_hours = Column(String(200), nullable=True)   # "Пн-Сб 09:00-19:00"

    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    average_rating = Column(Float, default=0.0, nullable=False)
    reviews_count = Column(Integer, default=0, nullable=False)
    views_count = Column(Integer, default=0, nullable=False)

    # --- CarSpot Premium ---
    boosted_until = Column(DateTime, nullable=True)  # буст поднимает заведение в топ каталога

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class BusinessReview(Base):
    """Отзыв на автосервис/ателье. Один пользователь — один отзыв на заведение."""

    __tablename__ = "business_reviews"
    __table_args__ = (
        UniqueConstraint("business_id", "user_id", name="uq_business_review"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    business_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)

    rating = Column(Integer, nullable=False)   # 1..5
    text = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=True)  # фото к отзыву (необязательно)

    quality_rating = Column(Integer, nullable=True)     # качество работы
    price_rating = Column(Integer, nullable=True)       # цена/качество
    speed_rating = Column(Integer, nullable=True)       # скорость выполнения

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class BusinessFavorite(Base):
    """Избранные заведения пользователя."""

    __tablename__ = "business_favorites"
    __table_args__ = (
        UniqueConstraint("business_id", "user_id", name="uq_business_favorite"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    business_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


Index("ix_businesses_geo", Business.latitude, Business.longitude)
