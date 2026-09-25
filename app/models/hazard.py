from sqlalchemy import Column, DateTime, Float, Index, Integer, String

from app.database import Base
from app.models.base import new_id, utcnow

HAZARD_TYPES = (
    "camera",     # камера контроля скорости
    "pothole",    # яма
    "ice",        # гололёд
    "accident",   # ДТП
    "police",     # пост/засада ДПС
    "other",
)


class RoadHazard(Base):
    """Метка дорожной опасности от сообщества (камера/яма/гололёд/ДТП/ДПС)."""

    __tablename__ = "road_hazards"

    id = Column(String(36), primary_key=True, default=new_id)
    created_by = Column(String(36), index=True, nullable=False)

    type = Column(String(20), nullable=False, default="other")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    note = Column(String(300), nullable=True)

    confirms_count = Column(Integer, default=1, nullable=False)
    denies_count = Column(Integer, default=0, nullable=False)

    # Постоянные (яма/камера) не истекают сами; временные (гололёд/ДТП/ДПС) — по expires_at.
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


Index("ix_road_hazards_location", RoadHazard.latitude, RoadHazard.longitude)


class RoadHazardVote(Base):
    """Голос пользователя за метку — 'confirm' или 'deny', один голос на пользователя."""

    __tablename__ = "road_hazard_votes"

    id = Column(String(36), primary_key=True, default=new_id)
    hazard_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)
    vote = Column(String(10), nullable=False)  # "confirm" | "deny"
    created_at = Column(DateTime, default=utcnow, nullable=False)


Index("ix_road_hazard_votes_unique", RoadHazardVote.hazard_id, RoadHazardVote.user_id, unique=True)
