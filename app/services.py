"""
Общая бизнес-логика, которую используют несколько роутеров.
Здесь нет HTTP — только работа с БД.
"""
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.chat import ChatMember, ChatMessage, ChatRoom
from app.models.event import Event
from app.models.rating import EventRating, UserRating
from app.models.user import User


# ─────────────────────────── ЧАТЫ ───────────────────────────

def direct_key_for(user_a: str, user_b: str) -> str:
    """Уникальный ключ личного чата — пара id в отсортированном виде."""
    return ":".join(sorted([str(user_a), str(user_b)]))


def get_or_create_event_room(db: Session, event: Event) -> ChatRoom:
    """Чат сходки. Создаётся автоматически вместе с событием."""
    room = db.query(ChatRoom).filter(ChatRoom.event_id == event.id).first()
    if room:
        return room

    room = ChatRoom(
        room_type="event",
        title=event.title,
        event_id=event.id,
        created_by=event.creator_id,
        last_message_at=utcnow(),
    )
    db.add(room)
    db.flush()
    add_room_member(db, room.id, event.creator_id)
    return room


def get_or_create_club_room(db: Session, club_id: str, title: str, owner_id: str) -> ChatRoom:
    """Чат клуба."""
    room = db.query(ChatRoom).filter(ChatRoom.club_id == club_id).first()
    if room:
        return room

    room = ChatRoom(
        room_type="club",
        title=title,
        club_id=club_id,
        created_by=owner_id,
        last_message_at=utcnow(),
    )
    db.add(room)
    db.flush()
    add_room_member(db, room.id, owner_id)
    return room


def get_or_create_direct_room(db: Session, user_a: str, user_b: str) -> ChatRoom:
    """Личный чат между двумя пользователями."""
    key = direct_key_for(user_a, user_b)
    room = db.query(ChatRoom).filter(ChatRoom.direct_key == key).first()
    if room:
        return room

    room = ChatRoom(
        room_type="direct",
        direct_key=key,
        created_by=user_a,
        last_message_at=utcnow(),
    )
    db.add(room)
    db.flush()
    add_room_member(db, room.id, user_a)
    add_room_member(db, room.id, user_b)
    return room


def add_room_member(db: Session, room_id: str, user_id: str) -> ChatMember:
    """Добавляет пользователя в комнату, если его там ещё нет."""
    member = (
        db.query(ChatMember)
        .filter(ChatMember.room_id == room_id, ChatMember.user_id == user_id)
        .first()
    )
    if member:
        return member

    member = ChatMember(room_id=room_id, user_id=user_id)
    db.add(member)
    db.flush()
    return member


def remove_room_member(db: Session, room_id: str, user_id: str) -> None:
    db.query(ChatMember).filter(
        ChatMember.room_id == room_id, ChatMember.user_id == user_id
    ).delete(synchronize_session=False)


def post_system_message(db: Session, room_id: str, text: str, user_id: str) -> ChatMessage:
    """Служебное сообщение в чат («X присоединился к сходке»)."""
    msg = ChatMessage(
        room_id=room_id,
        user_id=user_id,
        text=text,
        message_type="system",
    )
    db.add(msg)
    touch_room(db, room_id, text)
    return msg


def touch_room(db: Session, room_id: str, last_text: Optional[str]) -> None:
    """Обновляет превью последнего сообщения и счётчик."""
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        return
    room.last_message_at = utcnow()
    room.last_message_text = (last_text or "")[:300]
    room.messages_count = (room.messages_count or 0) + 1


def is_room_member(db: Session, room_id: str, user_id: str) -> bool:
    return (
        db.query(ChatMember.id)
        .filter(ChatMember.room_id == room_id, ChatMember.user_id == user_id)
        .first()
        is not None
    )


# ─────────────────────── ПЕРЕСЧЁТ РЕЙТИНГОВ ───────────────────────

def recalc_event_rating(db: Session, event_id: str) -> None:
    """Пересчитывает средний рейтинг события."""
    avg, count = (
        db.query(func.avg(EventRating.rating), func.count(EventRating.id))
        .filter(EventRating.event_id == event_id)
        .one()
    )
    event = db.query(Event).filter(Event.id == event_id).first()
    if event:
        event.average_rating = round(float(avg or 0), 2)
        event.ratings_count = int(count or 0)


def recalc_user_rating(db: Session, user_id: str) -> None:
    """Пересчитывает средний рейтинг пользователя."""
    avg, count = (
        db.query(func.avg(UserRating.rating), func.count(UserRating.id))
        .filter(UserRating.rated_user_id == user_id)
        .one()
    )
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.average_rating = round(float(avg or 0), 2)
        user.ratings_count = int(count or 0)


# ─────────────────────── ХЕЛПЕРЫ ОТВЕТОВ ───────────────────────

def users_by_ids(db: Session, ids) -> dict:
    """Возвращает словарь {user_id: User} одним запросом — против N+1."""
    unique = [i for i in {str(i) for i in ids if i}]
    if not unique:
        return {}
    rows = db.query(User).filter(User.id.in_(unique)).all()
    return {u.id: u for u in rows}
