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

CLUB_ROLES = ("owner", "admin", "member")


class Club(Base):
    """Автоклуб."""

    __tablename__ = "clubs"

    id = Column(String(36), primary_key=True, default=new_id)
    owner_id = Column(String(36), index=True, nullable=False)

    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)
    cover_url = Column(String(500), nullable=True)

    country = Column(String(50), nullable=True, index=True)
    city = Column(String(100), nullable=True, index=True)

    # Тематика: "JDM", "Stance", "Offroad", "Classic" и т.д.
    tags = Column(String(300), nullable=True)

    is_public = Column(Boolean, default=True, nullable=False)   # False = вступление по заявке
    is_verified = Column(Boolean, default=False, nullable=False)

    members_count = Column(Integer, default=0, nullable=False)
    events_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class ClubMember(Base):
    """Членство в клубе."""

    __tablename__ = "club_members"
    __table_args__ = (
        UniqueConstraint("club_id", "user_id", name="uq_club_member"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    club_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)
    role = Column(String(20), default="member", nullable=False)   # owner / admin / member
    status = Column(String(20), default="approved", nullable=False)  # approved / pending
    joined_at = Column(DateTime, default=utcnow, nullable=False)


class ClubFavorite(Base):
    """Избранные клубы пользователя (по аналогии с BusinessFavorite)."""

    __tablename__ = "club_favorites"
    __table_args__ = (
        UniqueConstraint("club_id", "user_id", name="uq_club_favorite"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    club_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
