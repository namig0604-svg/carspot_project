"""Комментарии — общие для сходок и фото (полиморфно, по target_type/target_id)."""
from sqlalchemy import Boolean, Column, DateTime, Index, String, Text

from app.database import Base
from app.models.base import new_id, utcnow

COMMENT_TARGET_TYPES = ("event", "photo")


class Comment(Base):
    """Один комментарий под сходкой или фотографией."""

    __tablename__ = "comments"

    id = Column(String(36), primary_key=True, default=new_id)

    target_type = Column(String(20), nullable=False, index=True)  # "event" / "photo"
    target_id = Column(String(36), nullable=False, index=True)

    user_id = Column(String(36), index=True, nullable=False)
    text = Column(Text, nullable=False)

    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)


Index("ix_comments_target_created", Comment.target_type, Comment.target_id, Comment.created_at)
