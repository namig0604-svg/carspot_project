"""
Автоклубы: создание, вступление, участники, роли.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user, get_optional_user
from app.models.chat import ChatRoom
from app.models.club import Club, ClubMember
from app.models.event import Event
from app.models.user import User
from app.schemas.club import (
    ClubCreate,
    ClubDetail,
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

    return ClubListResponse(
        total=total,
        limit=page.limit,
        offset=page.offset,
        items=[ClubOut.model_validate(c) for c in items],
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
    return db.query(Club).filter(Club.id.in_(club_ids)).order_by(Club.name.asc()).all()


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
):
    _get_club_or_404(db, club_id)
    return (
        db.query(Event)
        .filter(Event.club_id == club_id, Event.is_active.is_(True))
        .order_by(Event.event_date.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
