"""
Профили пользователей.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.models.car import Car
from app.models.club import Club, ClubMember
from app.models.event import Event, EventParticipant
from app.models.user import User
from app.schemas.car import CarOut
from app.schemas.event import EventOut
from app.schemas.user import UserMe, UserPublic, UserUpdate

router = APIRouter()


@router.get("/", response_model=List[UserPublic], summary="Поиск пользователей")
def search_users(
    q: Optional[str] = Query(None, description="Поиск по имени/логину"),
    country: Optional[str] = None,
    city: Optional[str] = None,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    query = db.query(User).filter(User.is_active.is_(True))

    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(User.username.ilike(pattern), User.full_name.ilike(pattern))
        )
    if country:
        query = query.filter(func.lower(User.country) == country.lower())
    if city:
        query = query.filter(func.lower(User.city) == city.lower())

    return (
        query.order_by(User.average_rating.desc(), User.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )


@router.patch("/me", response_model=UserMe, summary="Обновить свой профиль")
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=UserPublic, summary="Профиль пользователя")
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


@router.get(
    "/{user_id}/cars",
    response_model=List[CarOut],
    summary="Гараж пользователя",
)
def get_user_cars(user_id: str, db: Session = Depends(get_db)):
    if not db.query(User.id).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return (
        db.query(Car)
        .filter(Car.user_id == user_id)
        .order_by(Car.is_primary.desc(), Car.created_at.desc())
        .all()
    )


@router.get(
    "/{user_id}/clubs",
    summary="Клубы пользователя и его роль в каждом",
)
def get_user_clubs(user_id: str, db: Session = Depends(get_db)):
    if not db.query(User.id).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    memberships = (
        db.query(ClubMember)
        .filter(ClubMember.user_id == user_id, ClubMember.status == "approved")
        .all()
    )
    if not memberships:
        return []

    clubs = {
        c.id: c
        for c in db.query(Club).filter(Club.id.in_([m.club_id for m in memberships])).all()
    }

    result = []
    for m in memberships:
        club = clubs.get(m.club_id)
        if not club:
            continue
        result.append(
            {
                "club_id": club.id,
                "name": club.name,
                "logo_url": club.logo_url,
                "role": m.role,
            }
        )
    return result


@router.get(
    "/{user_id}/events",
    response_model=List[EventOut],
    summary="События, созданные пользователем",
)
def get_user_events(
    user_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    return (
        db.query(Event)
        .filter(Event.creator_id == user_id, Event.is_active.is_(True))
        .order_by(Event.event_date.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )


@router.get(
    "/{user_id}/attending",
    response_model=List[EventOut],
    summary="События, куда пользователь идёт",
)
def get_user_attending(
    user_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    event_ids = [
        row[0]
        for row in db.query(EventParticipant.event_id)
        .filter(
            EventParticipant.user_id == user_id,
            EventParticipant.status.in_(("going", "maybe")),
        )
        .all()
    ]
    if not event_ids:
        return []

    return (
        db.query(Event)
        .filter(Event.id.in_(event_ids), Event.is_active.is_(True))
        .order_by(Event.event_date.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
