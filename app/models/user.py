from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.database import Base
from app.models.base import new_id, utcnow


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_id)

    # --- Учётные данные ---
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # --- Профиль ---
    full_name = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    phone = Column(String(30), nullable=True)
    country = Column(String(50), nullable=True, index=True)
    city = Column(String(100), nullable=True, index=True)
    instagram = Column(String(100), nullable=True)

    # --- Статусы ---
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_premium = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    # --- Статистика (денормализована для скорости) ---
    average_rating = Column(Float, default=0.0, nullable=False)
    ratings_count = Column(Integer, default=0, nullable=False)
    events_created = Column(Integer, default=0, nullable=False)
    events_attended = Column(Integer, default=0, nullable=False)
    cars_count = Column(Integer, default=0, nullable=False)

    # --- Служебное ---
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=True)
