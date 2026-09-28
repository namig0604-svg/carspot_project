import secrets
import string

from sqlalchemy import Column, DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Session

from app.database import Base
from app.models.base import new_id, utcnow

CONVOY_STATUSES = ("active", "ended")

# Без 0/O и 1/I/L — легко читать и диктовать вслух, когда собираетесь в колонну.
_INVITE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_INVITE_CODE_LENGTH = 6


def _generate_invite_code() -> str:
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(_INVITE_CODE_LENGTH))


def generate_unique_invite_code(db: Session) -> str:
    """Генерирует код приглашения, гарантированно не занятый ни одним конвоем."""
    for _ in range(20):
        code = _generate_invite_code()
        exists = db.query(Convoy.id).filter(Convoy.invite_code == code).first()
        if not exists:
            return code
    # Астрономически маловероятно, но на всякий случай не зацикливаемся навечно.
    raise RuntimeError("Не удалось сгенерировать уникальный код приглашения")


class Convoy(Base):
    """
    Конвой — временная группа для совместной поездки с live-локацией всех
    участников на карте, независимо от их обычных настроек приватности
    геолокации (see app/api/location.py:_visible_to — состоящим в одном
    активном конвое метки видны друг другу всегда).
    """

    __tablename__ = "convoys"

    id = Column(String(36), primary_key=True, default=new_id)
    name = Column(String(100), nullable=False)
    creator_id = Column(String(36), index=True, nullable=False)
    invite_code = Column(String(8), unique=True, index=True, nullable=False)
    status = Column(String(10), default="active", nullable=False, index=True)

    destination_label = Column(String(200), nullable=True)
    destination_lat = Column(Float, nullable=True)
    destination_lng = Column(Float, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)


class ConvoyMember(Base):
    """
    Участник конвоя. При выходе строка не удаляется, а помечается left_at —
    это и история участия, и защита от повторной вставки той же пары
    (convoy_id, user_id) при повторном присоединении (см. join_convoy в
    app/api/convoy.py — left_at просто обнуляется).
    """

    __tablename__ = "convoy_members"
    __table_args__ = (
        UniqueConstraint("convoy_id", "user_id", name="uq_convoy_member"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    convoy_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)
    joined_at = Column(DateTime, default=utcnow, nullable=False)
    left_at = Column(DateTime, nullable=True)


Index("ix_convoy_members_convoy_active", ConvoyMember.convoy_id, ConvoyMember.left_at)
Index("ix_convoy_members_user_active", ConvoyMember.user_id, ConvoyMember.left_at)


def shares_active_convoy(db: Session, a: str, b: str) -> bool:
    """Состоят ли a и b прямо сейчас в одном и том же активном конвое."""
    a_convoys = {
        row[0]
        for row in db.query(ConvoyMember.convoy_id)
        .join(Convoy, Convoy.id == ConvoyMember.convoy_id)
        .filter(ConvoyMember.user_id == a, ConvoyMember.left_at.is_(None), Convoy.status == "active")
        .all()
    }
    if not a_convoys:
        return False
    exists = (
        db.query(ConvoyMember.id)
        .join(Convoy, Convoy.id == ConvoyMember.convoy_id)
        .filter(
            ConvoyMember.user_id == b,
            ConvoyMember.left_at.is_(None),
            Convoy.status == "active",
            ConvoyMember.convoy_id.in_(a_convoys),
        )
        .first()
    )
    return exists is not None
