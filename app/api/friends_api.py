"""
Друзья: заявки в друзья, список друзей, статус отношений.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.base import utcnow
from app.models.friendship import Friendship
from app.models.user import User
from app.schemas.friend import FriendRequestOut, FriendStatusOut
from app.schemas.user import UserPublic
from app.services import pair_key_for, users_by_ids

router = APIRouter()


def _get_friendship_or_404(db: Session, friendship_id: str) -> Friendship:
    fr = db.query(Friendship).filter(Friendship.id == friendship_id).first()
    if not fr:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return fr


@router.get("/", response_model=List[UserPublic], summary="Список моих друзей")
def list_friends(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = (
        db.query(Friendship)
        .filter(
            Friendship.status == "accepted",
            or_(
                Friendship.requester_id == current_user.id,
                Friendship.addressee_id == current_user.id,
            ),
        )
        .all()
    )
    if not rows:
        return []

    friend_ids = [
        r.addressee_id if r.requester_id == current_user.id else r.requester_id
        for r in rows
    ]
    users_map = users_by_ids(db, friend_ids)
    return [UserPublic.model_validate(users_map[uid]) for uid in friend_ids if uid in users_map]


@router.get(
    "/requests",
    response_model=List[FriendRequestOut],
    summary="Входящие заявки в друзья",
)
def list_incoming_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = (
        db.query(Friendship)
        .filter(Friendship.addressee_id == current_user.id, Friendship.status == "pending")
        .order_by(Friendship.created_at.desc())
        .all()
    )
    if not rows:
        return []

    users_map = users_by_ids(db, [r.requester_id for r in rows])
    out = []
    for r in rows:
        user = users_map.get(r.requester_id)
        if not user:
            continue
        out.append(FriendRequestOut(id=r.id, user=UserPublic.model_validate(user), created_at=r.created_at))
    return out


@router.get(
    "/requests/sent",
    response_model=List[FriendRequestOut],
    summary="Мои отправленные заявки",
)
def list_sent_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = (
        db.query(Friendship)
        .filter(Friendship.requester_id == current_user.id, Friendship.status == "pending")
        .order_by(Friendship.created_at.desc())
        .all()
    )
    if not rows:
        return []

    users_map = users_by_ids(db, [r.addressee_id for r in rows])
    out = []
    for r in rows:
        user = users_map.get(r.addressee_id)
        if not user:
            continue
        out.append(FriendRequestOut(id=r.id, user=UserPublic.model_validate(user), created_at=r.created_at))
    return out


@router.get(
    "/status/{user_id}",
    response_model=FriendStatusOut,
    summary="Статус дружбы с конкретным пользователем",
)
def get_friend_status(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if user_id == current_user.id:
        return FriendStatusOut(status="none")

    key = pair_key_for(current_user.id, user_id)
    fr = db.query(Friendship).filter(Friendship.pair_key == key).first()
    if not fr:
        return FriendStatusOut(status="none")

    if fr.status == "accepted":
        return FriendStatusOut(status="friends", friendship_id=fr.id)
    if fr.status == "pending":
        if fr.requester_id == current_user.id:
            return FriendStatusOut(status="pending_sent", friendship_id=fr.id)
        return FriendStatusOut(status="pending_received", friendship_id=fr.id)

    # declined ранее — считаем, что отношений нет, заявку можно отправить снова
    return FriendStatusOut(status="none")


@router.post(
    "/request/{user_id}",
    response_model=FriendStatusOut,
    summary="Отправить заявку в друзья",
)
def send_friend_request(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя добавить в друзья самого себя")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    key = pair_key_for(current_user.id, user_id)
    existing = db.query(Friendship).filter(Friendship.pair_key == key).first()

    if existing:
        if existing.status == "accepted":
            raise HTTPException(status_code=400, detail="Вы уже друзья")
        if existing.status == "pending":
            if existing.requester_id == current_user.id:
                raise HTTPException(status_code=400, detail="Заявка уже отправлена")
            # Встречная заявка от того, кто уже написал нам — сразу дружим.
            existing.status = "accepted"
            existing.updated_at = utcnow()
            db.commit()
            return FriendStatusOut(status="friends", friendship_id=existing.id)

        # Ранее отклонённая заявка — отправляем заново.
        existing.status = "pending"
        existing.requester_id = current_user.id
        existing.addressee_id = user_id
        existing.updated_at = utcnow()
        db.commit()
        return FriendStatusOut(status="pending_sent", friendship_id=existing.id)

    fr = Friendship(
        pair_key=key,
        requester_id=current_user.id,
        addressee_id=user_id,
        status="pending",
    )
    db.add(fr)
    db.commit()
    db.refresh(fr)
    return FriendStatusOut(status="pending_sent", friendship_id=fr.id)


@router.post(
    "/{friendship_id}/accept",
    response_model=FriendStatusOut,
    summary="Принять заявку в друзья",
)
def accept_friend_request(
    friendship_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    fr = _get_friendship_or_404(db, friendship_id)
    if fr.addressee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваша заявка")
    if fr.status != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже обработана")

    fr.status = "accepted"
    fr.updated_at = utcnow()
    db.commit()
    return FriendStatusOut(status="friends", friendship_id=fr.id)


@router.post("/{friendship_id}/decline", summary="Отклонить заявку / отменить свою заявку")
def decline_friend_request(
    friendship_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    fr = _get_friendship_or_404(db, friendship_id)
    if fr.requester_id != current_user.id and fr.addressee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваша заявка")
    if fr.status != "pending":
        raise HTTPException(status_code=400, detail="Заявка уже обработана")

    fr.status = "declined"
    fr.updated_at = utcnow()
    db.commit()
    return {"message": "Заявка отклонена"}


@router.delete("/{friendship_id}", summary="Удалить из друзей")
def remove_friend(
    friendship_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    fr = _get_friendship_or_404(db, friendship_id)
    if fr.requester_id != current_user.id and fr.addressee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваша дружба")

    db.delete(fr)
    db.commit()
    return {"message": "Удалено из друзей"}
