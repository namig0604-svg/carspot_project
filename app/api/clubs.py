"""
Автоклубы: создание, вступление, участники, роли.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user, get_optional_user
from app.models.chat import ChatMember, ChatMessage, ChatRoom
from app.models.club import Club, ClubFavorite, ClubMember
from app.models.event import Event
from app.models.rating import EventRating
from app.models.user import User
from app.schemas.club import (
    ClubCreate,
    ClubDetail,
    ClubLeaderboardOut,
    ClubListResponse,
    ClubMemberOut,
    ClubOut,
    ClubRoleUpdate,
    ClubUpdate,
)
from app.schemas.event import EventOut
from app.schemas.user import UserPublic
from app.services import (
    add_room_member,
    get_or_create_club_room,
    post_system_message,
    remove_room_member,
    users_by_ids,
)

router = APIRouter()


def _get_club_or_404(db: Session, club_id: str) -> Club:
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Клуб не найден")
    return club


def _get_membership(db: Session, club_id: str, user_id: str) -> Optional[ClubMember]:
    return (
        db.query(ClubMember)
        .filter(ClubMember.club_id == club_id, ClubMember.user_id == user_id)
        .first()
    )


def _require_admin(db: Session, club: Club, user: User) -> ClubMember:
    membership = _get_membership(db, club.id, user.id)
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Недостаточно прав в клубе")
    return membership


def _refresh_members_count(db: Session, club: Club) -> None:
    club.members_count = (
        db.query(ClubMember)
        .filter(ClubMember.club_id == club.id, ClubMember.status == "approved")
        .count()
    )


def _favorite_ids(db: Session, user: Optional[User], club_ids: List[str]) -> set:
    if not user or not club_ids:
        return set()
    return {
        row[0]
        for row in db.query(ClubFavorite.club_id)
        .filter(ClubFavorite.user_id == user.id, ClubFavorite.club_id.in_(club_ids))
        .all()
    }


@router.post(
    "/",
    response_model=ClubDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Создать клуб",
)
def create_club(
    payload: ClubCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    name = payload.name.strip()
    if db.query(Club).filter(func.lower(Club.name) == name.lower()).first():
        raise HTTPException(status_code=400, detail="Клуб с таким названием уже существует")

    data = payload.model_dump()
    data["name"] = name
    club = Club(owner_id=current_user.id, **data)
    db.add(club)
    db.flush()

    db.add(
        ClubMember(
            club_id=club.id,
            user_id=current_user.id,
            role="owner",
            status="approved",
        )
    )
    club.members_count = 1

    room = get_or_create_club_room(db, club.id, club.name, current_user.id)

    db.commit()
    db.refresh(club)

    detail = ClubDetail.model_validate(club)
    detail.owner = UserPublic.model_validate(current_user)
    detail.chat_room_id = room.id
    detail.my_role = "owner"
    detail.my_status = "approved"
    return detail


@router.get("/", response_model=ClubListResponse, summary="Список клубов")
def list_clubs(
    q: Optional[str] = Query(None, description="Поиск по названию"),
    country: Optional[str] = None,
    city: Optional[str] = None,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    query = db.query(Club)

    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(Club.name.ilike(pattern), Club.description.ilike(pattern), Club.tags.ilike(pattern))
        )
    if country:
        query = query.filter(func.lower(Club.country) == country.lower())
    if city:
        query = query.filter(func.lower(Club.city) == city.lower())

    total = query.count()
    items = (
        query.order_by(Club.members_count.desc(), Club.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )

    favorite_ids = _favorite_ids(db, current_user, [c.id for c in items])
    out_items = []
    for c in items:
        item = ClubOut.model_validate(c)
        item.is_favorite = c.id in favorite_ids
        out_items.append(item)

    return ClubListResponse(
        total=total,
        limit=page.limit,
        offset=page.offset,
        items=out_items,
    )


@router.get("/my", response_model=List[ClubOut], summary="Мои клубы")
def my_clubs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club_ids = [
        row[0]
        for row in db.query(ClubMember.club_id)
        .filter(ClubMember.user_id == current_user.id, ClubMember.status == "approved")
        .all()
    ]
    if not club_ids:
        return []
    clubs = db.query(Club).filter(Club.id.in_(club_ids)).order_by(Club.name.asc()).all()
    favorite_ids = _favorite_ids(db, current_user, club_ids)
    result = []
    for c in clubs:
        item = ClubOut.model_validate(c)
        item.is_favorite = c.id in favorite_ids
        result.append(item)
    return result


@router.get(
    "/leaderboard",
    response_model=List[ClubLeaderboardOut],
    summary="Рейтинг клубов",
)
def clubs_leaderboard(
    limit: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    """
    Рейтинг автоклубов по активности: живые счётчики участников и сходок
    (а не денормализованные Club.members_count/events_count — те не всегда
    актуальны) плюс средний рейтинг сходок клуба.

    Очки клуба: события — основной вклад в активность, участники и оценки —
    вспомогательные множители. Формула специфична для этого рейтинга и не
    связана с формулой XP пользователей.
    """
    clubs = db.query(Club).all()
    if not clubs:
        return []

    club_ids = [c.id for c in clubs]

    members_map = dict(
        db.query(ClubMember.club_id, func.count(ClubMember.id))
        .filter(ClubMember.club_id.in_(club_ids), ClubMember.status == "approved")
        .group_by(ClubMember.club_id)
        .all()
    )

    events_map = dict(
        db.query(Event.club_id, func.count(Event.id))
        .filter(Event.club_id.in_(club_ids), Event.is_active.is_(True))
        .group_by(Event.club_id)
        .all()
    )

    rating_rows = (
        db.query(Event.club_id, func.avg(EventRating.rating))
        .join(EventRating, EventRating.event_id == Event.id)
        .filter(Event.club_id.in_(club_ids))
        .group_by(Event.club_id)
        .all()
    )
    rating_map = {row[0]: float(row[1]) for row in rating_rows if row[1] is not None}

    items = []
    for club in clubs:
        members = members_map.get(club.id, 0)
        events = events_map.get(club.id, 0)
        average_rating = round(rating_map.get(club.id, 0.0), 2)
        score = events * 30 + members * 4 + round(average_rating * 10)

        items.append(
            ClubLeaderboardOut(
                id=club.id,
                name=club.name,
                logo_url=club.logo_url,
                country=club.country,
                city=club.city,
                is_verified=club.is_verified,
                members_count=members,
                events_count=events,
                average_rating=average_rating,
                score=score,
            )
        )

    items.sort(key=lambda x: x.score, reverse=True)
    return items[:limit]


@router.get(
    "/my/favorites",
    response_model=List[ClubOut],
    summary="Мои избранные клубы",
)
def my_favorite_clubs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club_ids = [
        row[0]
        for row in db.query(ClubFavorite.club_id)
        .filter(ClubFavorite.user_id == current_user.id)
        .all()
    ]
    if not club_ids:
        return []

    clubs = db.query(Club).filter(Club.id.in_(club_ids)).order_by(Club.name.asc()).all()
    result = []
    for c in clubs:
        item = ClubOut.model_validate(c)
        item.is_favorite = True
        result.append(item)
    return result


@router.get("/{club_id}", response_model=ClubDetail, summary="Карточка клуба")
def get_club(
    club_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    club = _get_club_or_404(db, club_id)

    detail = ClubDetail.model_validate(club)

    owner = db.query(User).filter(User.id == club.owner_id).first()
    if owner:
        detail.owner = UserPublic.model_validate(owner)

    room = db.query(ChatRoom).filter(ChatRoom.club_id == club.id).first()
    detail.chat_room_id = room.id if room else None

    if current_user:
        membership = _get_membership(db, club.id, current_user.id)
        if membership:
            detail.my_role = membership.role
            detail.my_status = membership.status
        detail.is_favorite = (
            db.query(ClubFavorite.id)
            .filter(ClubFavorite.club_id == club.id, ClubFavorite.user_id == current_user.id)
            .first()
            is not None
        )

    return detail


@router.patch("/{club_id}", response_model=ClubOut, summary="Изменить клуб")
def update_club(
    club_id: str,
    payload: ClubUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = _get_club_or_404(db, club_id)
    _require_admin(db, club, current_user)

    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"]:
        new_name = data["name"].strip()
        conflict = (
            db.query(Club)
            .filter(func.lower(Club.name) == new_name.lower(), Club.id != club.id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=400, detail="Клуб с таким названием уже существует")
        data["name"] = new_name

    for field, value in data.items():
        setattr(club, field, value)

    db.commit()
    db.refresh(club)
    return club


@router.delete("/{club_id}", summary="Удалить клуб")
def delete_club(
    club_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = _get_club_or_404(db, club_id)

    if club.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только владелец может удалить клуб")

    # Чат клуба целиком (сообщения → участники → комната)
    room = db.query(ChatRoom).filter(ChatRoom.club_id == club_id).first()
    if room:
        db.query(ChatMessage).filter(ChatMessage.room_id == room.id).delete(synchronize_session=False)
        db.query(ChatMember).filter(ChatMember.room_id == room.id).delete(synchronize_session=False)
        db.delete(room)

    # Membership'ы клуба
    db.query(ClubMember).filter(ClubMember.club_id == club_id).delete(synchronize_session=False)

    # События клуба остаются, но перестают быть клубными
    db.query(Event).filter(Event.club_id == club_id).update(
        {Event.club_id: None}, synchronize_session=False
    )

    db.delete(club)
    db.commit()
    return {"message": "Клуб удалён", "club_id": club_id}


@router.post("/{club_id}/join", summary="Вступить в клуб")
def join_club(
    club_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = _get_club_or_404(db, club_id)

    membership = _get_membership(db, club.id, current_user.id)
    if membership:
        if membership.status == "approved":
            raise HTTPException(status_code=400, detail="Вы уже в клубе")
        raise HTTPException(status_code=400, detail="Заявка уже отправлена")

    status_value = "approved" if club.is_public else "pending"
    db.add(
        ClubMember(
            club_id=club.id,
            user_id=current_user.id,
            role="member",
            status=status_value,
        )
    )
    db.flush()

    room = get_or_create_club_room(db, club.id, club.name, club.owner_id)

    if status_value == "approved":
        add_room_member(db, room.id, current_user.id)
        post_system_message(db, room.id, f"{current_user.username} вступил в клуб", current_user.id)
        _refresh_members_count(db, club)

    db.commit()

    return {
        "message": "Вы вступили в клуб" if status_value == "approved" else "Заявка отправлена",
        "status": status_value,
        "chat_room_id": room.id if status_value == "approved" else None,
    }


@router.post("/{club_id}/leave", summary="Выйти из клуба")
def leave_club(
    club_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = _get_club_or_404(db, club_id)
    membership = _get_membership(db, club.id, current_user.id)

    if not membership:
        raise HTTPException(status_code=400, detail="Вы не состоите в клубе")
    if membership.role == "owner":
        raise HTTPException(
            status_code=400,
            detail="Владелец не может выйти. Передайте права другому участнику",
        )

    db.delete(membership)
    db.flush()

    room = db.query(ChatRoom).filter(ChatRoom.club_id == club.id).first()
    if room:
        remove_room_member(db, room.id, current_user.id)

    _refresh_members_count(db, club)
    db.commit()
    return {"message": "Вы вышли из клуба"}


@router.get(
    "/{club_id}/members",
    response_model=List[ClubMemberOut],
    summary="Участники клуба",
)
def club_members(
    club_id: str,
    member_status: str = Query("approved", description="approved | pending"),
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    _get_club_or_404(db, club_id)

    members = (
        db.query(ClubMember)
        .filter(ClubMember.club_id == club_id, ClubMember.status == member_status)
        .order_by(ClubMember.joined_at.asc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )

    user_map = users_by_ids(db, [m.user_id for m in members])

    result = []
    for m in members:
        item = ClubMemberOut.model_validate(m)
        user = user_map.get(m.user_id)
        if user:
            item.user = UserPublic.model_validate(user)
        result.append(item)
    return result


@router.post("/{club_id}/members/{user_id}/approve", summary="Одобрить заявку")
def approve_member(
    club_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = _get_club_or_404(db, club_id)
    _require_admin(db, club, current_user)

    membership = _get_membership(db, club_id, user_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    membership.status = "approved"

    room = get_or_create_club_room(db, club.id, club.name, club.owner_id)
    add_room_member(db, room.id, user_id)

    _refresh_members_count(db, club)
    db.commit()
    return {"message": "Участник одобрен", "user_id": user_id}


@router.patch("/{club_id}/members/{user_id}/role", summary="Изменить роль участника")
def change_role(
    club_id: str,
    user_id: str,
    payload: ClubRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = _get_club_or_404(db, club_id)

    if club.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только владелец может менять роли")

    if payload.role not in ("admin", "member", "owner"):
        raise HTTPException(status_code=400, detail="Роль должна быть owner, admin или member")

    membership = _get_membership(db, club_id, user_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Участник не найден")

    # Передача владения
    if payload.role == "owner":
        old_owner = _get_membership(db, club_id, current_user.id)
        if old_owner:
            old_owner.role = "admin"
        club.owner_id = user_id

    membership.role = payload.role
    db.commit()
    return {"message": "Роль обновлена", "user_id": user_id, "role": payload.role}


@router.delete("/{club_id}/members/{user_id}", summary="Исключить участника")
def kick_member(
    club_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    club = _get_club_or_404(db, club_id)
    _require_admin(db, club, current_user)

    if user_id == club.owner_id:
        raise HTTPException(status_code=400, detail="Нельзя исключить владельца")

    membership = _get_membership(db, club_id, user_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Участник не найден")

    db.delete(membership)
    db.flush()

    room = db.query(ChatRoom).filter(ChatRoom.club_id == club_id).first()
    if room:
        remove_room_member(db, room.id, user_id)

    _refresh_members_count(db, club)
    db.commit()
    return {"message": "Участник исключён", "user_id": user_id}


@router.get(
    "/{club_id}/events",
    response_model=List[EventOut],
    summary="События клуба",
)
def club_events(
    club_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    _get_club_or_404(db, club_id)

    query = db.query(Event).filter(Event.club_id == club_id, Event.is_active.is_(True))

    is_member = False
    if current_user:
        membership = _get_membership(db, club_id, current_user.id)
        is_member = bool(membership and membership.status == "approved")

    if not is_member:
        query = query.filter(Event.is_private.is_(False))

    return (
        query.order_by(Event.event_date.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )


# ─────────────────────────── ИЗБРАННОЕ ───────────────────────────

@router.post("/{club_id}/favorite", summary="Добавить клуб в избранное")
def add_club_favorite(
    club_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_club_or_404(db, club_id)

    exists = (
        db.query(ClubFavorite)
        .filter(ClubFavorite.club_id == club_id, ClubFavorite.user_id == current_user.id)
        .first()
    )
    if not exists:
        db.add(ClubFavorite(club_id=club_id, user_id=current_user.id))
        db.commit()
    return {"message": "Добавлено в избранное", "is_favorite": True}


@router.delete("/{club_id}/favorite", summary="Убрать клуб из избранного")
def remove_club_favorite(
    club_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    db.query(ClubFavorite).filter(
        ClubFavorite.club_id == club_id, ClubFavorite.user_id == current_user.id
    ).delete(synchronize_session=False)
    db.commit()
    return {"message": "Убрано из избранного", "is_favorite": False}
