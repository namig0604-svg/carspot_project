"""
Профили пользователей.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import premium_tiers
from app.config import settings
from app.api.events import _can_view_private_event
from app.database import get_db
from app.deps import Pagination, get_current_active_user, get_optional_user
from app.models.base import utcnow
from app.models.car import Car
from app.models.club import Club, ClubMember
from app.models.event import Event, EventParticipant
from app.models.user import ProfileView, User, UserLike
from app.schemas.car import CarOut
from app.schemas.event import EventOut
from app.schemas.user import ProfileViewOut, ReferralInfo, UserMe, UserPublic, UserUpdate
from app.services import extend_premium, notify

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

    # Профили с активным бустом за монеты (см. /api/coins/profile/boost)
    # поднимаются в топ поиска — тот же принцип, что и у бустов сходок/автосервисов.
    boosted_rank = case((User.profile_boosted_until > utcnow(), 0), else_=1)
    return (
        query.order_by(boosted_rank, User.average_rating.desc(), User.created_at.desc())
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

    if "username" in data and data["username"]:
        new_username = data["username"].strip()
        conflict = (
            db.query(User)
            .filter(func.lower(User.username) == new_username.lower(), User.id != current_user.id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=400, detail="Такой юзернейм уже занят")
        data["username"] = new_username

    for field, value in data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/referral", response_model=ReferralInfo, summary="Свой реферальный код и число приглашённых")
def get_my_referral(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    referrals_count = (
        db.query(User).filter(User.referred_by_id == current_user.id).count()
    )
    per_month = settings.REFERRALS_PER_PREMIUM_MONTH
    return ReferralInfo(
        code=current_user.referral_code,
        referrals_count=referrals_count,
        referrals_per_premium_month=per_month,
        referrals_until_next_reward=per_month - (referrals_count % per_month),
        premium_months_earned=current_user.referral_premium_claimed_count or 0,
    )


@router.post("/me/premium-trial", response_model=UserMe, summary="Активировать пробный Premium (14 дней)")
def start_premium_trial(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.premium_trial_used:
        raise HTTPException(status_code=400, detail="Пробный период уже был использован")

    extend_premium(current_user, settings.PREMIUM_TRIAL_DAYS)
    current_user.premium_trial_used = True
    db.commit()
    db.refresh(current_user)
    return current_user


def _record_profile_view(db: Session, viewer: Optional[User], viewed_user: User) -> None:
    """Отмечает, что viewer зашёл в профиль viewed_user — не чаще одной строки на пару,
    чтобы список 'кто смотрел профиль' (Premium) не раздувался повторными визитами."""
    if not viewer or viewer.id == viewed_user.id:
        return

    existing = (
        db.query(ProfileView)
        .filter(ProfileView.viewed_user_id == viewed_user.id, ProfileView.viewer_id == viewer.id)
        .first()
    )
    if existing:
        existing.updated_at = utcnow()
    else:
        db.add(ProfileView(viewed_user_id=viewed_user.id, viewer_id=viewer.id))
        viewed_user.profile_views_count = (viewed_user.profile_views_count or 0) + 1
    db.commit()


# ВАЖНО: эти /me/... роуты обязаны быть объявлены ДО "/{user_id}" ниже —
# иначе FastAPI примет "me" за user_id и они никогда не сработают.


@router.get(
    "/me/likers",
    response_model=List[UserPublic],
    summary="Кто лайкнул мой профиль (Premium)",
)
def my_likers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not premium_tiers.can_view_insights(current_user) and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Список тех, кто лайкнул профиль, доступен только с CarSpot Premium",
        )

    liker_ids = [
        row[0]
        for row in db.query(UserLike.liker_user_id)
        .filter(UserLike.target_user_id == current_user.id)
        .order_by(UserLike.created_at.desc())
        .limit(premium_tiers.insights_limit(current_user) if not current_user.is_admin else settings.PREMIUM_INSIGHTS_LIMIT)
        .all()
    ]
    if not liker_ids:
        return []

    users_by_id = {u.id: u for u in db.query(User).filter(User.id.in_(liker_ids)).all()}
    return [UserPublic.model_validate(users_by_id[uid]) for uid in liker_ids if uid in users_by_id]


@router.get(
    "/me/profile-views",
    response_model=List[ProfileViewOut],
    summary="Кто смотрел мой профиль (Premium)",
)
def my_profile_views(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not premium_tiers.can_view_insights(current_user) and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Список просмотров профиля доступен только с CarSpot Premium",
        )

    rows = (
        db.query(ProfileView)
        .filter(ProfileView.viewed_user_id == current_user.id)
        .order_by(ProfileView.updated_at.desc())
        .limit(premium_tiers.insights_limit(current_user) if not current_user.is_admin else settings.PREMIUM_INSIGHTS_LIMIT)
        .all()
    )
    if not rows:
        return []

    viewer_ids = [r.viewer_id for r in rows]
    users_by_id = {u.id: u for u in db.query(User).filter(User.id.in_(viewer_ids)).all()}

    out = []
    for r in rows:
        viewer = users_by_id.get(r.viewer_id)
        if not viewer:
            continue
        out.append(ProfileViewOut(user=UserPublic.model_validate(viewer), viewed_at=r.updated_at))
    return out


@router.get("/{user_id}", response_model=UserPublic, summary="Профиль пользователя")
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    out = UserPublic.model_validate(user)
    if current_user:
        out.is_liked = (
            db.query(UserLike.id)
            .filter(UserLike.target_user_id == user_id, UserLike.liker_user_id == current_user.id)
            .first()
            is not None
        )
        _record_profile_view(db, current_user, user)
    return out


@router.post("/{user_id}/like", summary="Лайк / снять лайк профиля")
def toggle_user_like(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя лайкнуть свой профиль")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    existing = (
        db.query(UserLike)
        .filter(UserLike.target_user_id == user_id, UserLike.liker_user_id == current_user.id)
        .first()
    )

    if existing:
        db.delete(existing)
        target.likes_count = max(0, (target.likes_count or 1) - 1)
        liked = False
    else:
        db.add(UserLike(target_user_id=user_id, liker_user_id=current_user.id))
        target.likes_count = (target.likes_count or 0) + 1
        liked = True
        notify(
            db,
            user_id=user_id,
            type="profile_like",
            actor_id=current_user.id,
            target_type="user",
            target_id=user_id,
            message=f"{current_user.username} лайкнул(а) твой профиль",
        )

    try:
        db.commit()
    except IntegrityError:
        # Двойной тап по кнопке лайка: два запроса одновременно не увидели
        # существующую запись, оба попытались вставить — уникальный индекс
        # не даёт задублировать. Это не ошибка сервера, а "уже лайкнуто".
        db.rollback()
        target = db.query(User).filter(User.id == user_id).first()
        return {"liked": True, "likes_count": target.likes_count if target else 0}

    db.refresh(target)
    return {"liked": liked, "likes_count": target.likes_count}


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
    current_user: Optional[User] = Depends(get_optional_user),
):
    events = (
        db.query(Event)
        .filter(Event.creator_id == user_id, Event.is_active.is_(True))
        .order_by(Event.event_date.desc())
        .all()
    )
    visible = [
        e for e in events
        if not e.is_private or _can_view_private_event(db, e, current_user)
    ]
    return visible[page.offset : page.offset + page.limit]


@router.get(
    "/{user_id}/attending",
    response_model=List[EventOut],
    summary="События, куда пользователь идёт",
)
def get_user_attending(
    user_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
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

    events = (
        db.query(Event)
        .filter(Event.id.in_(event_ids), Event.is_active.is_(True))
        .order_by(Event.event_date.desc())
        .all()
    )
    visible = [
        e for e in events
        if not e.is_private or _can_view_private_event(db, e, current_user)
    ]
    return visible[page.offset : page.offset + page.limit]
