"""
Система рейтингов: события, пользователи, споты.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.models.event import Event
from app.models.rating import EventRating, SpotRating, UserRating
from app.models.user import User
from app.schemas.rating import (
    EventRatingCreate,
    EventRatingOut,
    RatingSummary,
    SpotRatingCreate,
    SpotRatingOut,
    UserRatingCreate,
    UserRatingOut,
)
from app.schemas.user import UserPublic
from app.services import award_xp, recalc_event_rating, recalc_user_rating, users_by_ids

router = APIRouter()


def _breakdown(db: Session, model, filter_column, filter_value) -> dict:
    """Разбивка оценок по звёздам: {"1": 0, "2": 1, ...}"""
    rows = (
        db.query(model.rating, func.count(model.id))
        .filter(filter_column == filter_value)
        .group_by(model.rating)
        .all()
    )
    result = {str(i): 0 for i in range(1, 6)}
    for rating_value, count in rows:
        result[str(int(rating_value))] = int(count)
    return result


# ─────────────────────── РЕЙТИНГ СОБЫТИЙ ───────────────────────

@router.post(
    "/events",
    response_model=EventRatingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Оценить сходку",
)
def rate_event(
    payload: EventRatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    event = db.query(Event).filter(Event.id == payload.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    existing = (
        db.query(EventRating)
        .filter(
            EventRating.event_id == payload.event_id,
            EventRating.user_id == current_user.id,
        )
        .first()
    )

    if existing:
        # Повторная оценка обновляет предыдущую
        for field, value in payload.model_dump(exclude={"event_id"}).items():
            setattr(existing, field, value)
        rating = existing
    else:
        rating = EventRating(user_id=current_user.id, **payload.model_dump())
        db.add(rating)

    db.flush()
    recalc_event_rating(db, payload.event_id)
    db.commit()
    db.refresh(rating)

    out = EventRatingOut.model_validate(rating)
    out.user = UserPublic.model_validate(current_user)
    return out


@router.get(
    "/events/{event_id}",
    response_model=List[EventRatingOut],
    summary="Отзывы о сходке",
)
def event_ratings(
    event_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    ratings = (
        db.query(EventRating)
        .filter(EventRating.event_id == event_id)
        .order_by(EventRating.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )

    user_map = users_by_ids(db, [r.user_id for r in ratings])
    result = []
    for r in ratings:
        item = EventRatingOut.model_validate(r)
        user = user_map.get(r.user_id)
        if user:
            item.user = UserPublic.model_validate(user)
        result.append(item)
    return result


@router.get(
    "/events/{event_id}/summary",
    response_model=RatingSummary,
    summary="Сводка рейтинга сходки",
)
def event_rating_summary(event_id: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")

    return RatingSummary(
        average_rating=event.average_rating or 0.0,
        ratings_count=event.ratings_count or 0,
        breakdown=_breakdown(db, EventRating, EventRating.event_id, event_id),
    )


# ─────────────────────── РЕЙТИНГ ПОЛЬЗОВАТЕЛЕЙ ───────────────────────

@router.post(
    "/users",
    response_model=UserRatingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Оценить пользователя",
)
def rate_user(
    payload: UserRatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.rated_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя оценить самого себя")

    rated_user = db.query(User).filter(User.id == payload.rated_user_id).first()
    if not rated_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    existing = (
        db.query(UserRating)
        .filter(
            UserRating.rated_user_id == payload.rated_user_id,
            UserRating.rater_user_id == current_user.id,
        )
        .first()
    )

    if existing:
        for field, value in payload.model_dump(exclude={"rated_user_id"}).items():
            setattr(existing, field, value)
        rating = existing
    else:
        rating = UserRating(rater_user_id=current_user.id, **payload.model_dump())
        db.add(rating)
        # XP только за первую оценку от конкретного человека — иначе можно
        # было бы фармить уровень, без конца переоценивая один и тот же профиль.
        award_xp(db, rated_user, 8, "rating_received")

    db.flush()
    recalc_user_rating(db, payload.rated_user_id)
    db.commit()
    db.refresh(rating)

    out = UserRatingOut.model_validate(rating)
    out.user = UserPublic.model_validate(current_user)
    return out


@router.get(
    "/users/{user_id}",
    response_model=List[UserRatingOut],
    summary="Отзывы о пользователе",
)
def user_ratings(
    user_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    ratings = (
        db.query(UserRating)
        .filter(UserRating.rated_user_id == user_id)
        .order_by(UserRating.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )

    user_map = users_by_ids(db, [r.rater_user_id for r in ratings])
    result = []
    for r in ratings:
        item = UserRatingOut.model_validate(r)
        rater = user_map.get(r.rater_user_id)
        if rater:
            item.user = UserPublic.model_validate(rater)
        result.append(item)
    return result


@router.get(
    "/users/{user_id}/summary",
    response_model=RatingSummary,
    summary="Сводка рейтинга пользователя",
)
def user_rating_summary(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return RatingSummary(
        average_rating=user.average_rating or 0.0,
        ratings_count=user.ratings_count or 0,
        breakdown=_breakdown(db, UserRating, UserRating.rated_user_id, user_id),
    )


# ─────────────────────── РЕЙТИНГ СПОТОВ ───────────────────────

@router.post(
    "/spots",
    response_model=SpotRatingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Оценить место (спот)",
)
def rate_spot(
    payload: SpotRatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.event_id:
        if not db.query(Event.id).filter(Event.id == payload.event_id).first():
            raise HTTPException(status_code=404, detail="Событие не найдено")

    rating = SpotRating(user_id=current_user.id, **payload.model_dump())
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


@router.get(
    "/spots",
    response_model=List[SpotRatingOut],
    summary="Оценки спотов",
)
def list_spot_ratings(
    event_id: str = None,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    query = db.query(SpotRating)
    if event_id:
        query = query.filter(SpotRating.event_id == event_id)

    return (
        query.order_by(SpotRating.rating.desc(), SpotRating.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
