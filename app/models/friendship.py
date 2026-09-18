"""Заявки в друзья и сама дружба между пользователями."""
from sqlalchemy import Column, DateTime, Index, String, UniqueConstraint

from app.database import Base
from app.models.base import new_id, utcnow

FRIENDSHIP_STATUSES = ("pending", "accepted", "declined")


class Friendship(Base):
    """
    Одна строка на пару пользователей (независимо от того, кто кому писал).
    - requester_id — кто отправил заявку, addressee_id — кому.
    - status: pending -> accepted (принял) / declined (отклонил).
    - pair_key — отсортированная пара "id1:id2", гарантирует, что между
      двумя людьми есть максимум одна запись (как direct_key у чатов).
    """

    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("pair_key", name="uq_friendship_pair"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    pair_key = Column(String(80), unique=True, index=True, nullable=False)

    requester_id = Column(String(36), index=True, nullable=False)
    addressee_id = Column(String(36), index=True, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)


Index("ix_friendships_addressee_status", Friendship.addressee_id, Friendship.status)
Index("ix_friendships_requester_status", Friendship.requester_id, Friendship.status)
