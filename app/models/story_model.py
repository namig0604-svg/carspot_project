"""Истории — фото, которое видно 24 часа с момента публикации."""
from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from app.database import Base
from app.models.base import new_id, utcnow

STORY_LIFETIME_HOURS = 24


class Story(Base):
    """Одна история пользователя. Живёт STORY_LIFETIME_HOURS часов — фильтр
    по created_at на выборке, отдельного фонового удаления не требуется."""

    __tablename__ = "stories"

    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), index=True, nullable=False)

    image_url = Column(String(500), nullable=False)
    image_key = Column(String(255), nullable=False)
    caption = Column(String(300), nullable=True)

    # Необязательная привязка — «история со сходки» / «история про машину»
    event_id = Column(String(36), nullable=True, index=True)
    car_id = Column(String(36), nullable=True, index=True)

    views_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)


class StoryView(Base):
    """Кто уже посмотрел историю — чтобы не засчитывать просмотр дважды
    и показывать автору счётчик уникальных зрителей."""

    __tablename__ = "story_views"
    __table_args__ = (
        UniqueConstraint("story_id", "viewer_id", name="uq_story_view"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    story_id = Column(String(36), index=True, nullable=False)
    viewer_id = Column(String(36), index=True, nullable=False)
    viewed_at = Column(DateTime, default=utcnow, nullable=False)
