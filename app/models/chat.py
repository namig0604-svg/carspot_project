from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base
from app.models.base import new_id, utcnow

ROOM_TYPES = ("direct", "event", "club")


class ChatRoom(Base):
    """
    Комната чата.
    - direct: личная переписка двух пользователей
    - event:  чат участников сходки (создаётся вместе с событием)
    - club:   чат клуба (создаётся вместе с клубом)
    """

    __tablename__ = "chat_rooms"

    id = Column(String(36), primary_key=True, default=new_id)
    room_type = Column(String(20), default="direct", nullable=False, index=True)

    title = Column(String(200), nullable=True)
    event_id = Column(String(36), index=True, nullable=True)
    club_id = Column(String(36), index=True, nullable=True)

    # Для direct-чатов: отсортированная пара "id1:id2" — гарантирует уникальность
    direct_key = Column(String(80), unique=True, index=True, nullable=True)

    created_by = Column(String(36), nullable=True)
    last_message_at = Column(DateTime, default=utcnow, nullable=True, index=True)
    last_message_text = Column(String(300), nullable=True)
    messages_count = Column(Integer, default=0, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ChatMember(Base):
    """Участник комнаты."""

    __tablename__ = "chat_members"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_chat_member"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    room_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)
    last_read_at = Column(DateTime, default=utcnow, nullable=True)
    is_muted = Column(Boolean, default=False, nullable=False)
    joined_at = Column(DateTime, default=utcnow, nullable=False)


class ChatMessage(Base):
    """Сообщение в комнате."""

    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=new_id)
    room_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)

    text = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    message_type = Column(String(20), default="text", nullable=False)  # text / image / system

    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)


Index("ix_chat_messages_room_created", ChatMessage.room_id, ChatMessage.created_at)
