"""
Общая бизнес-логика, которую используют несколько роутеров.
Здесь нет HTTP — только работа с БД.
"""
from datetime import timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.base import utcnow
from app.models.business import Business, BusinessReview
from app.models.chat import ChatMember, ChatMessage, ChatRoom
from app.models.event import Event
from app.models.notification import Notification
from app.models.rating import EventRating, UserRating
from app.models.user import User


# ─────────────────────────── ЧАТЫ ───────────────────────────

def direct_key_for(user_a: str, user_b: str) -> str:
    """Уникальный ключ личного чата — пара id в отсортированном виде."""
    return ":".join(sorted([str(user_a), str(user_b)]))


# ─────────────────────────── ДРУЗЬЯ ───────────────────────────

def pair_key_for(user_a: str, user_b: str) -> str:
    """Уникальный ключ пары для дружбы — как direct_key_for, но для friendships."""
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


# ─────────────────────── CARSPOT PREMIUM ───────────────────────

def extend_premium(user: User, days: int) -> None:
    """Продлевает Premium на `days` от текущего срока (или от сейчас, если уже истёк)."""
    base = user.premium_until if user.premium_until and user.premium_until > utcnow() else utcnow()
    user.premium_until = base + timedelta(days=days)


def grant_referral_premium_if_earned(db: Session, referrer_id: Optional[str]) -> None:
    """
    Каждые settings.REFERRALS_PER_PREMIUM_MONTH приглашённых друзей дают
    settings.PREMIUM_MONTH_DAYS дней Premium. referral_premium_claimed_count
    хранит, сколько таких «порций» уже начислено, чтобы не начислять повторно
    при каждом пересчёте — начисляется только разница новых порций.
    Вызывается сразу после регистрации нового пользователя по реферальному коду.
    """
    if not referrer_id:
        return
    referrer = db.query(User).filter(User.id == referrer_id).first()
    if not referrer:
        return

    referrals_count = db.query(User).filter(User.referred_by_id == referrer_id).count()
    milestones_earned = referrals_count // settings.REFERRALS_PER_PREMIUM_MONTH
    new_milestones = milestones_earned - (referrer.referral_premium_claimed_count or 0)
    if new_milestones > 0:
        extend_premium(referrer, settings.PREMIUM_MONTH_DAYS * new_milestones)
        referrer.referral_premium_claimed_count = milestones_earned


# ─────────────────────── CARSPOT COINS (внутренняя валюта) ───────────────────────

class InsufficientCoinsError(Exception):
    """Не хватает монет на балансе для операции."""


def spend_coins(db: Session, user: User, amount: int, tx_type: str, reference_id: Optional[str] = None):
    """
    Списывает `amount` монет с баланса пользователя и пишет транзакцию.
    Бросает InsufficientCoinsError, если монет не хватает — коммит делает
    вызывающий код (после того как выполнит саму операцию, например буст).
    """
    if amount <= 0:
        raise ValueError("amount должен быть положительным")
    if (user.coin_balance or 0) < amount:
        raise InsufficientCoinsError(f"Недостаточно монет: нужно {amount}, на балансе {user.coin_balance or 0}")

    user.coin_balance = (user.coin_balance or 0) - amount
    from app.models.coin_transaction import CoinTransaction  # локальный импорт — без цикла

    tx = CoinTransaction(
        user_id=user.id,
        amount=-amount,
        balance_after=user.coin_balance,
        type=tx_type,
        reference_id=reference_id,
    )
    db.add(tx)
    return tx


def grant_coins(
    db: Session,
    user: User,
    amount: int,
    tx_type: str,
    reference_id: Optional[str] = None,
    purchase_token: Optional[str] = None,
):
    """Начисляет `amount` монет пользователю и пишет транзакцию."""
    if amount <= 0:
        raise ValueError("amount должен быть положительным")

    user.coin_balance = (user.coin_balance or 0) + amount
    from app.models.coin_transaction import CoinTransaction  # локальный импорт — без цикла

    tx = CoinTransaction(
        user_id=user.id,
        amount=amount,
        balance_after=user.coin_balance,
        type=tx_type,
        reference_id=reference_id,
        purchase_token=purchase_token,
    )
    db.add(tx)
    return tx


# ─────────────────────────── УВЕДОМЛЕНИЯ ───────────────────────────

_PUSH_TITLES = {
    "friend_request": "🤝 Заявка в друзья",
    "friend_accepted": "🤝 Новый друг",
    "profile_like": "❤️ Новый лайк",
    "event_join": "🏁 Новый участник",
    "comment_event": "💬 Новый комментарий",
    "comment_photo": "💬 Новый комментарий",
}


def _send_push_to_user(
    db: Session,
    user_id: str,
    type_: str,
    message: str,
    target_type: Optional[str],
    target_id: Optional[str],
) -> None:
    """Best-effort рассылка push на все устройства пользователя. Никогда не
    бросает исключение наружу — push вторичен по отношению к самому
    уведомлению, отсутствие настроенного Firebase не должно ронять запрос."""
    from app.models.notification import DeviceToken
    from app.push_client import PushError, PushNotConfiguredError, send_push

    tokens = db.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
    if not tokens:
        return

    title = _PUSH_TITLES.get(type_, "CarSpot")
    data = {"type": type_}
    if target_type:
        data["target_type"] = target_type
    if target_id:
        data["target_id"] = target_id

    for dt in tokens:
        try:
            send_push(dt.token, title, message, data=data)
        except PushNotConfiguredError:
            # Firebase ещё не подключён — не мучаем попробовать остальные токены.
            return
        except PushError as e:
            text = str(e)
            if "UNREGISTERED" in text or "NOT_FOUND" in text or "INVALID_ARGUMENT" in text:
                # Токен отозван/устарел (переустановка приложения, сменил
                # устройство) — чистим, чтобы не долбиться в пустоту.
                db.query(DeviceToken).filter(DeviceToken.id == dt.id).delete(synchronize_session=False)
            print(f"[PUSH] Ошибка отправки: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"[PUSH] Неожиданная ошибка: {e}")


def notify(
    db: Session,
    *,
    user_id: str,
    type: str,
    message: str,
    actor_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
) -> Optional[Notification]:
    """
    Кладёт запись в ленту уведомлений. Не уведомляем человека о его же
    действии (actor_id == user_id) — незачем говорить самому себе, что ты
    сам что-то лайкнул. Ошибки здесь не должны ронять основной запрос —
    уведомление вторично по отношению к самому действию.
    """
    if actor_id and actor_id == user_id:
        return None
    try:
        n = Notification(
            user_id=user_id,
            type=type,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            message=message,
        )
        db.add(n)
    except Exception:  # noqa: BLE001
        return None

    try:
        _send_push_to_user(db, user_id, type, message, target_type, target_id)
    except Exception as e:  # noqa: BLE001
        print(f"[PUSH] Ошибка рассылки: {e}")

    return n


# ─────────────────────── ХЕЛПЕРЫ ОТВЕТОВ ───────────────────────

def users_by_ids(db: Session, ids) -> dict:
    """Возвращает словарь {user_id: User} одним запросом — против N+1."""
    unique = [i for i in {str(i) for i in ids if i}]
    if not unique:
        return {}
    rows = db.query(User).filter(User.id.in_(unique)).all()
    return {u.id: u for u in rows}
