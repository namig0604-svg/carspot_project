"""
Сходки: создание, поиск, карта, участники.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app import premium_tiers
from app.api.clubs import refresh_events_count
from app.config import settings
from app.database import get_db
from app.deps import Pagination, get_current_active_user, get_optional_user
from app.models.base import utcnow
from app.models.car import Car
from app.models.chat import ChatRoom
from app.models.club import ClubMember
from app.models.event import Event, EventFavorite, EventParticipant
from app.models.rating import EventRating
from app.models.user import User
from app.services import InsufficientCoinsError, spend_coins
from app.schemas.event import (
    EventCreate,
    EventDetail,
    EventListResponse,
    EventMapMarker,
    EventOut,
    EventUpdate,
    JoinEventRequest,
    ParticipantOut,
)
from app.schemas.user import UserPublic
from app.services import (
    add_room_member,
    expire_ended_events,
    get_or_create_event_room,
    notify,
    post_system_message,
    remove_room_member,
    users_by_ids,
)
from app.utils.geo import bounding_box, haversine_km

router = APIRouter()


def _recommended_score(item, latitude: float, longitude: float) -> float:
    """Смешивает близость и рейтинг сходки в одно число (см. такую же
    функцию в app/api/businesses.py — тот же принцип)."""
    if item.latitude is None or item.longitude is None:
        proximity = 0.0
    else:
        distance = haversine_km(latitude, longitude, item.latitude, item.longitude)
        proximity = max(0.0, 1.0 - min(distance, 250.0) / 250.0)

    rating = max(0.0, min(5.0, item.average_rating or 0.0)) / 5.0
    score = 0.6 * proximity + 0.4 * rating

    if item.boosted_until and item.boosted_until > utcnow():
        score += 10.0

    return score


def _rank_by_recommended(candidates: list, latitude: float, longitude: float) -> list:
    scored = [(_recommended_score(c, latitude, longitude), c) for c in candidates]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [c for _score, c in scored]


def _is_approved_club_member(db: Session, club_id: str, user_id: str) -> bool:
    return (
        db.query(ClubMember.id)
        .filter(
            ClubMember.club_id == club_id,
            ClubMember.user_id == user_id,
            ClubMember.status == "approved",
        )
        .first()
        is not None
    )


def _favorite_ids(db: Session, user: Optional[User], event_ids: List[str]) -> set:
    if not user or not event_ids:
        return set()
    return {
        row[0]
        for row in db.query(EventFavorite.event_id)
        .filter(EventFavorite.user_id == user.id, EventFavorite.event_id.in_(event_ids))
        .all()
    }


def _can_view_private_event(db: Session, event: Event, user: Optional[User]) -> bool:
    """Приватное событие видно создателю, админу и участникам клуба (если это клубное событие)."""
    if not user:
        return False
    if event.creator_id == user.id or user.is_admin:
        return True
    if event.club_id and _is_approved_club_member(db, event.club_id, user.id):
        return True
    return False


def _apply_filters(query, event_type, country, city, club_id, search, only_upcoming):
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if country:
        query = query.filter(func.lower(Event.country) == country.lower())
    if city:
        query = query.filter(func.lower(Event.city) == city.lower())
    if club_id:
        query = query.filter(Event.club_id == club_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Event.title.ilike(pattern),
                Event.description.ilike(pattern),
                Event.location_name.ilike(pattern),
            )
        )
    if only_upcoming:
        query = query.filter(Event.event_date >= utcnow() - timedelta(hours=6))
    return query


@router.post(
    "/",
    response_model=EventDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Создать сходку",
)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Если событие от клуба — проверяем права
    if payload.club_id:
        membership = (
            db.query(ClubMember)
            .filter(
                ClubMember.club_id == payload.club_id,
                ClubMember.user_id == current_user.id,
                ClubMember.status == "approved",
            )
            .first()
        )
        if not membership or membership.role not in ("owner", "admin"):
            raise HTTPException(
                status_code=403,
                detail="Создавать события клуба могут только владелец и админы",
            )

    event = Event(creator_id=current_user.id, **payload.model_dump())
    db.add(event)
    db.flush()

    # Создатель автоматически участник
    db.add(EventParticipant(event_id=event.id, user_id=current_user.id, status="going"))
    event.participants_count = 1

    # Чат сходки
    room = get_or_create_event_room(db, event)

    current_user.events_created = (current_user.events_created or 0) + 1
    current_user.events_attended = (current_user.events_attended or 0) + 1

    if event.club_id:
        refresh_events_count(db, event.club_id)

    db.commit()
    db.refresh(event)

    detail = EventDetail.model_validate(event)
    detail.creator = UserPublic.model_validate(current_user)
    detail.chat_room_id = room.id
    detail.is_joined = True
    detail.is_creator = True
    return detail


@router.get("/", response_model=EventListResponse, summary="Список сходок")
def list_events(
    event_type: Optional[str] = Query(None, description="meetup / racing / drift ..."),
    country: Optional[str] = None,
    city: Optional[str] = None,
    club_id: Optional[str] = None,
    search: Optional[str] = Query(None, description="Поиск по названию и описанию"),
    only_upcoming: bool = Query(True, description="Только будущие события"),
    sort: str = Query("date", description="date | recommended | popular | rating | new"),
    latitude: Optional[float] = Query(None, ge=-90, le=90, description="Широта пользователя (для sort=recommended)"),
    longitude: Optional[float] = Query(None, ge=-180, le=180, description="Долгота пользователя (для sort=recommended)"),
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    expire_ended_events(db)

    query = db.query(Event).filter(
        Event.is_active.is_(True),
        Event.is_cancelled.is_(False),
        Event.is_private.is_(False),
    )
    query = _apply_filters(query, event_type, country, city, club_id, search, only_upcoming)

    total = query.count()

    # Бустнутые Premium-сходки всегда всплывают в топ ленты (на BOOST_DURATION_HOURS часов),
    # независимо от выбранной сортировки — а внутри этой группы порядок обычный.
    boosted_rank = case((Event.boosted_until > utcnow(), 0), else_=1)

    if sort == "recommended" and latitude is not None and longitude is not None:
        # "Рекомендовано": ближайшие и с лучшим рейтингом сходки — выше.
        # Считаем на ограниченном наборе кандидатов, как и в /nearby.
        candidates = query.order_by(boosted_rank, Event.event_date.asc()).limit(1000).all()
        ranked = _rank_by_recommended(candidates, latitude, longitude)
        items = ranked[page.offset : page.offset + page.limit]
    else:
        if sort == "popular":
            query = query.order_by(boosted_rank, Event.participants_count.desc(), Event.event_date.asc())
        elif sort == "rating":
            query = query.order_by(boosted_rank, Event.average_rating.desc(), Event.ratings_count.desc())
        elif sort == "new":
            query = query.order_by(boosted_rank, Event.created_at.desc())
        else:
            query = query.order_by(boosted_rank, Event.event_date.asc())
        items = query.offset(page.offset).limit(page.limit).all()

    joined_ids: set = set()
    if current_user and items:
        joined_ids = {
            row[0]
            for row in db.query(EventParticipant.event_id)
            .filter(
                EventParticipant.event_id.in_([e.id for e in items]),
                EventParticipant.user_id == current_user.id,
                EventParticipant.status.in_(("going", "maybe")),
            )
            .all()
        }
    favorite_ids = _favorite_ids(db, current_user, [e.id for e in items])

    out_items = []
    for e in items:
        item = EventOut.model_validate(e)
        item.is_joined = e.id in joined_ids
        item.is_favorite = e.id in favorite_ids
        out_items.append(item)

    return EventListResponse(
        total=total,
        limit=page.limit,
        offset=page.offset,
        items=out_items,
    )


@router.get(
    "/map",
    response_model=List[EventMapMarker],
    summary="Метки для карты в видимой области",
)
def events_for_map(
    min_lat: float = Query(..., ge=-90, le=90),
    max_lat: float = Query(..., ge=-90, le=90),
    min_lon: float = Query(..., ge=-180, le=180),
    max_lon: float = Query(..., ge=-180, le=180),
    event_type: Optional[str] = None,
    only_upcoming: bool = True,
    limit: int = Query(300, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Отдаёт лёгкие метки для отображения на карте.
    Клиент передаёт границы видимой области карты.
    """
    expire_ended_events(db)

    query = db.query(Event).filter(
        Event.is_active.is_(True),
        Event.is_cancelled.is_(False),
        Event.is_private.is_(False),
        Event.latitude.between(min(min_lat, max_lat), max(min_lat, max_lat)),
        Event.longitude.between(min(min_lon, max_lon), max(min_lon, max_lon)),
    )
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if only_upcoming:
        query = query.filter(Event.event_date >= utcnow() - timedelta(hours=6))

    events = query.order_by(Event.event_date.asc()).limit(limit).all()
    return [EventMapMarker.model_validate(e) for e in events]


@router.get(
    "/nearby",
    response_model=List[EventMapMarker],
    summary="Сходки рядом со мной",
)
def events_nearby(
    latitude: float = Query(..., ge=-90, le=90, description="Широта пользователя"),
    longitude: float = Query(..., ge=-180, le=180, description="Долгота пользователя"),
    radius_km: float = Query(None, ge=0.1, le=2000, description="Радиус поиска в км"),
    event_type: Optional[str] = None,
    only_upcoming: bool = True,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Ищет события в радиусе. Сначала быстрый отсев по прямоугольнику (по индексу),
    затем точный расчёт расстояния по формуле гаверсинуса.
    """
    expire_ended_events(db)

    radius = radius_km or settings.DEFAULT_SEARCH_RADIUS_KM
    min_lat, max_lat, min_lon, max_lon = bounding_box(latitude, longitude, radius)

    query = db.query(Event).filter(
        Event.is_active.is_(True),
        Event.is_cancelled.is_(False),
        Event.is_private.is_(False),
        Event.latitude.between(min_lat, max_lat),
        Event.longitude.between(min_lon, max_lon),
    )
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if only_upcoming:
        query = query.filter(Event.event_date >= utcnow() - timedelta(hours=6))

    candidates = query.limit(2000).all()

    result = []
    for event in candidates:
        distance = haversine_km(latitude, longitude, event.latitude, event.longitude)
        if distance <= radius:
            marker = EventMapMarker.model_validate(event)
            marker.distance_km = round(distance, 2)
            result.append(marker)

    result.sort(key=lambda m: m.distance_km or 0)
    return result[:limit]


@router.get(
    "/my/favorites",
    response_model=List[EventOut],
    summary="Мои избранные сходки",
)
def my_favorite_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    event_ids = [
        row[0]
        for row in db.query(EventFavorite.event_id)
        .filter(EventFavorite.user_id == current_user.id)
        .all()
    ]
    if not event_ids:
        return []

    events = (
        db.query(Event)
        .filter(Event.id.in_(event_ids), Event.is_active.is_(True))
        .order_by(Event.event_date.desc())
        .all()
    )

    joined_ids = {
        row[0]
        for row in db.query(EventParticipant.event_id)
        .filter(
            EventParticipant.event_id.in_(event_ids),
            EventParticipant.user_id == current_user.id,
            EventParticipant.status.in_(("going", "maybe")),
        )
        .all()
    }

    result = []
    for e in events:
        item = EventOut.model_validate(e)
        item.is_joined = e.id in joined_ids
        item.is_favorite = True
        result.append(item)
    return result


@router.get(
    "/my/created",
    response_model=List[EventOut],
    summary="Sozdannye mnoy shodki",
)
def my_created_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    events = (
        db.query(Event)
        .filter(Event.creator_id == current_user.id)
        .order_by(Event.created_at.desc())
        .all()
    )
    event_ids = [e.id for e in events]

    favorite_ids = {
        row[0]
        for row in db.query(EventFavorite.event_id)
        .filter(
            EventFavorite.event_id.in_(event_ids),
            EventFavorite.user_id == current_user.id,
        )
        .all()
    } if event_ids else set()

    joined_ids = {
        row[0]
        for row in db.query(EventParticipant.event_id)
        .filter(
            EventParticipant.event_id.in_(event_ids),
            EventParticipant.user_id == current_user.id,
            EventParticipant.status.in_(("going", "maybe")),
        )
        .all()
    } if event_ids else set()

    result = []
    for e in events:
        item = EventOut.model_validate(e)
        item.is_joined = e.id in joined_ids
        item.is_favorite = e.id in favorite_ids
        result.append(item)
    return result


@router.get("/{event_id}", response_model=EventDetail, summary="Карточка сходки")
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    expire_ended_events(db)

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    if event.is_private and not _can_view_private_event(db, event, current_user):
        raise HTTPException(status_code=404, detail="Событие не найдено")

    event.views_count = (event.views_count or 0) + 1
    db.commit()
    db.refresh(event)

    detail = EventDetail.model_validate(event)

    creator = db.query(User).filter(User.id == event.creator_id).first()
    if creator:
        detail.creator = UserPublic.model_validate(creator)

    room = db.query(ChatRoom).filter(ChatRoom.event_id == event.id).first()
    detail.chat_room_id = room.id if room else None

    if current_user:
        detail.is_creator = event.creator_id == current_user.id
        detail.is_joined = (
            db.query(EventParticipant.id)
            .filter(
                EventParticipant.event_id == event.id,
                EventParticipant.user_id == current_user.id,
                EventParticipant.status.in_(("going", "maybe")),
            )
            .first()
            is not None
        )
        detail.is_favorite = (
            db.query(EventFavorite.id)
            .filter(EventFavorite.event_id == event.id, EventFavorite.user_id == current_user.id)
            .first()
            is not None
        )
        my_rating = (
            db.query(EventRating)
            .filter(EventRating.event_id == event.id, EventRating.user_id == current_user.id)
            .first()
        )
        detail.my_rating = my_rating.rating if my_rating else None

    return detail


@router.patch("/{event_id}", response_model=EventOut, summary="Изменить сходку")
def update_event(
    event_id: str,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    if event.creator_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Только создатель может изменить событие")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)
    return event


@router.post(
    "/{event_id}/boost",
    response_model=EventOut,
    summary=f"Поднять сходку в топ ленты на {settings.BOOST_DURATION_HOURS} ч. (Premium)",
)
def boost_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    if event.creator_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Только создатель может продвигать сходку")
    if not premium_tiers.gets_free_boost(current_user) and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Бесплатно поднимать сходки в топ ленты могут только подписчики CarSpot Pro",
        )

    now = utcnow()
    if event.boosted_until and event.boosted_until > now:
        raise HTTPException(
            status_code=400,
            detail=f"Буст уже активен до {event.boosted_until.isoformat()}",
        )

    event.boosted_until = now + timedelta(hours=premium_tiers.boost_duration_hours(current_user))
    db.commit()
    db.refresh(event)
    return event


@router.post(
    "/{event_id}/boost-with-coins",
    response_model=EventOut,
    summary=f"Поднять сходку в топ ленты на {settings.BOOST_DURATION_HOURS} ч. за {settings.COIN_BOOST_COST_EVENT} монет",
)
def boost_event_with_coins(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Тот же буст, что и /boost, но платный — монетами CarSpot Coins вместо
    Premium. Так продвинуть сходку может любой пользователь, даже без
    подписки, если он готов потратить накопленные/купленные монеты."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    if event.creator_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Только создатель может продвигать сходку")

    now = utcnow()
    if event.boosted_until and event.boosted_until > now:
        raise HTTPException(
            status_code=400,
            detail=f"Буст уже активен до {event.boosted_until.isoformat()}",
        )

    try:
        spend_coins(db, current_user, settings.COIN_BOOST_COST_EVENT, "boost_event", reference_id=event.id)
    except InsufficientCoinsError as e:
        raise HTTPException(status_code=402, detail=str(e))

    event.boosted_until = now + timedelta(hours=settings.BOOST_DURATION_HOURS)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}", summary="Удалить (отменить) сходку")
def delete_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    if event.creator_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Только создатель может удалить событие")

    event.is_active = False
    event.is_cancelled = True

    # Отмена организатором — это не то же самое, что каждый участник сам
    # вышел (leave_event), но счётчик посещений на профиле не должен
    # оставаться завышенным навсегда: снимаем +1, который получил каждый
    # участник (в т.ч. сам создатель) при join_event/create_event.
    attendee_ids = [
        row[0]
        for row in db.query(EventParticipant.user_id)
        .filter(
            EventParticipant.event_id == event_id,
            EventParticipant.status.in_(("going", "maybe")),
        )
        .all()
    ]
    if attendee_ids:
        for user in db.query(User).filter(User.id.in_(attendee_ids)).all():
            user.events_attended = max(0, (user.events_attended or 1) - 1)

    if event.club_id:
        # flush обязателен: refresh_events_count пересчитывает COUNT(...) новым
        # запросом, а session здесь с autoflush=False — без явного flush он бы
        # не увидел ещё не отправленное в БД is_active=False у event.
        db.flush()
        refresh_events_count(db, event.club_id)

    db.commit()
    return {"message": "Событие отменено", "event_id": event_id}


# ─────────────────────────── УЧАСТНИКИ ───────────────────────────

@router.post("/{event_id}/join", summary="Пойду на сходку")
def join_event(
    event_id: str,
    payload: JoinEventRequest = JoinEventRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    if event.is_cancelled or not event.is_active:
        raise HTTPException(status_code=400, detail="Событие отменено или завершилось")

    if event.is_private and not _can_view_private_event(db, event, current_user):
        raise HTTPException(
            status_code=403,
            detail="Это закрытое событие — доступно только участникам клуба",
        )

    # Проверяем машину, если указана
    if payload.car_id:
        car = db.query(Car).filter(Car.id == payload.car_id).first()
        if not car or car.user_id != current_user.id:
            raise HTTPException(status_code=400, detail="Машина не найдена в вашем гараже")

    participant = (
        db.query(EventParticipant)
        .filter(
            EventParticipant.event_id == event_id,
            EventParticipant.user_id == current_user.id,
        )
        .first()
    )

    if participant and participant.status in ("going", "maybe"):
        participant.status = payload.status
        participant.car_id = payload.car_id
        db.commit()
        return {
            "message": "Статус участия обновлён",
            "status": participant.status,
            "participants_count": event.participants_count,
        }

    if event.max_participants:
        # Блокируем строку события на время проверки лимита — иначе два
        # запроса join одновременно могут оба увидеть место и оба пройти
        # (гонка), переполнив лимит участников.
        event = (
            db.query(Event)
            .filter(Event.id == event_id)
            .with_for_update()
            .first()
        )
        if event.participants_count >= event.max_participants:
            raise HTTPException(status_code=400, detail="Достигнут лимит участников")

    if participant:  # ранее вышел — возвращаем
        participant.status = payload.status
        participant.car_id = payload.car_id
        participant.joined_at = utcnow()
    else:
        db.add(
            EventParticipant(
                event_id=event_id,
                user_id=current_user.id,
                car_id=payload.car_id,
                status=payload.status,
            )
        )

    event.participants_count = (event.participants_count or 0) + 1
    current_user.events_attended = (current_user.events_attended or 0) + 1

    # Добавляем в чат сходки
    room = get_or_create_event_room(db, event)
    add_room_member(db, room.id, current_user.id)
    post_system_message(db, room.id, f"{current_user.username} присоединился к сходке", current_user.id)

    notify(
        db,
        user_id=event.creator_id,
        type="event_join",
        actor_id=current_user.id,
        target_type="event",
        target_id=event.id,
        message=f"{current_user.username} присоединился к твоей сходке «{event.title}»",
    )

    db.commit()
    db.refresh(event)

    return {
        "message": "Вы записаны на сходку",
        "status": payload.status,
        "participants_count": event.participants_count,
        "chat_room_id": room.id,
    }


@router.post("/{event_id}/leave", summary="Не пойду на сходку")
def leave_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    participant = (
        db.query(EventParticipant)
        .filter(
            EventParticipant.event_id == event_id,
            EventParticipant.user_id == current_user.id,
        )
        .first()
    )
    if not participant or participant.status == "left":
        raise HTTPException(status_code=400, detail="Вы не участвуете в этом событии")

    participant.status = "left"
    event.participants_count = max(0, (event.participants_count or 1) - 1)
    current_user.events_attended = max(0, (current_user.events_attended or 1) - 1)

    room = db.query(ChatRoom).filter(ChatRoom.event_id == event_id).first()
    if room and event.creator_id != current_user.id:
        remove_room_member(db, room.id, current_user.id)

    db.commit()
    db.refresh(event)

    return {
        "message": "Вы больше не участвуете",
        "participants_count": event.participants_count,
    }


@router.get(
    "/{event_id}/participants",
    response_model=List[ParticipantOut],
    summary="Участники сходки",
)
def list_participants(
    event_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    if not db.query(Event.id).filter(Event.id == event_id).first():
        raise HTTPException(status_code=404, detail="Событие не найдено")

    participants = (
        db.query(EventParticipant)
        .filter(
            EventParticipant.event_id == event_id,
            EventParticipant.status.in_(("going", "maybe")),
        )
        .order_by(EventParticipant.joined_at.asc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )

    user_map = users_by_ids(db, [p.user_id for p in participants])

    result = []
    for p in participants:
        item = ParticipantOut.model_validate(p)
        user = user_map.get(p.user_id)
        if user:
            item.user = UserPublic.model_validate(user)
        result.append(item)
    return result


# ─────────────────────────── ИЗБРАННОЕ ───────────────────────────

@router.post("/{event_id}/favorite", summary="Добавить сходку в избранное")
def add_event_favorite(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not db.query(Event.id).filter(Event.id == event_id).first():
        raise HTTPException(status_code=404, detail="Событие не найдено")

    exists = (
        db.query(EventFavorite)
        .filter(EventFavorite.event_id == event_id, EventFavorite.user_id == current_user.id)
        .first()
    )
    if not exists:
        db.add(EventFavorite(event_id=event_id, user_id=current_user.id))
        db.commit()
    return {"message": "Добавлено в избранное", "is_favorite": True}


@router.delete("/{event_id}/favorite", summary="Убрать сходку из избранного")
def remove_event_favorite(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    db.query(EventFavorite).filter(
        EventFavorite.event_id == event_id, EventFavorite.user_id == current_user.id
    ).delete(synchronize_session=False)
    db.commit()
    return {"message": "Убрано из избранного", "is_favorite": False}
