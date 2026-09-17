from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base
from app.models.base import new_id, utcnow


class Photo(Base):
    """Фотография, привязанная к событию (и опционально к машине)."""

    __tablename__ = "photos"

    id = Column(String(36), primary_key=True, default=new_id)
    event_id = Column(String(36), index=True, nullable=True)
    car_id = Column(String(36), index=True, nullable=True)
    user_id = Column(String(36), index=True, nullable=False)

    photo_url = Column(String(500), nullable=False)
    photo_key = Column(String(200), nullable=True)   # имя файла на диске
    mime_type = Column(String(50), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    caption = Column(Text, nullable=True)

    likes_count = Column(Integer, default=0, nullable=False)
    is_approved = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)


class PhotoLike(Base):
    """Лайк фотографии — один пользователь может лайкнуть фото один раз."""

    __tablename__ = "photo_likes"
    __table_args__ = (
        UniqueConstraint("photo_id", "user_id", name="uq_photo_like"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    photo_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
