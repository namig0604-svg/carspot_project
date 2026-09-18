"""
Общая бизнес-логика, которую используют несколько роутеров.
Здесь нет HTTP — только работа с БД.
"""
from datetime import timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.business import Business, BusinessReview
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


# ─────────────────────── ЖИЗНЕННЫЙ ЦИКЛ СХОДОК ───────────────────────

def expire_ended_events(db: Session) -> None:
    """
    Сходка автоматически перестаёт быть активной, когда истекает её
    продолжительность (event_date + duration_minutes). Никакого отдельного
    воркера/крона в проекте нет, поэтому проверка лёгкая и вызывается прямо
    в местах, где сходки читаются (список, карта, рядом, карточка) — так
    устаревшие сходки исчезают из выдачи практически сразу после того, как
    закончились, без нагрузки на каждый запрос (сначала быстрый отсев по
    event_date, потом точный расчёт в Python).
    """
    now = utcnow()
    candidates = (
        db.query(Event)
        .filter(Event.is_active.is_(True), Event.event_date <= now)
        .all()
    )
    if not candidates:
        return

    changed = False
    for event in candidates:
        ends_at = event.event_date + timedelta(minutes=event.duration_minutes or 0)
        if ends_at < now:
            event.is_active = False
            changed = True

    if changed:
        db.commit()


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


def recalc_business_rating(db: Session, business_id: str) -> None:
    """Пересчитывает средний рейтинг автосервиса/ателье по его отзывам."""
    avg, count = (
        db.query(func.avg(BusinessReview.rating), func.count(BusinessReview.id))
        .filter(BusinessReview.business_id == business_id)
        .one()
    )
    business = db.query(Business).filter(Business.id == business_id).first()
    if business:
        business.average_rating = round(float(avg or 0), 2)
        business.reviews_count = int(count or 0)


# ─────────────────────── ХЕЛПЕРЫ ОТВЕТОВ ───────────────────────

def users_by_ids(db: Session, ids) -> dict:
    """Возвращает словарь {user_id: User} одним запросом — против N+1."""
    unique = [i for i in {str(i) for i in ids if i}]
    if not unique:
        return {}
    rows = db.query(User).filter(User.id.in_(unique)).all()
    return {u.id: u for u in rows}
