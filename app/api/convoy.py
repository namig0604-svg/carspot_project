"""
Конвой-режим: временная группа для совместной поездки с live-локацией
участников на карте. Один пользователь состоит не более чем в одном
активном конвое одновременно. Видимость позиций друг друга для участников
одного конвоя обеспечивается в app/api/location.py (_visible_to учитывает
shares_active_convoy) — здесь только управление составом группы.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.base import utcnow
from app.models.convoy import Convoy, ConvoyMember, generate_unique_invite_code
from app.models.user import User
from app.schemas.convoy import (
    ConvoyCreate,
    ConvoyDestinationUpdate,
    ConvoyJoinIn,
    ConvoyMemberOut,
    ConvoyOut,
)
from app.services import users_by_ids

router = APIRouter()


def _active_membership(db: Session, user_id: str) -> ConvoyMember | None:
    return (
        db.query(ConvoyMember)
        .join(Convoy, Convoy.id == ConvoyMember.convoy_id)
        .filter(ConvoyMember.user_id == user_id, ConvoyMember.left_at.is_(None), Convoy.status == "active")
        .first()
    )


def _get_convoy_or_404(db: Session, convoy_id: str) -> Convoy:
    convoy = db.query(Convoy).filter(Convoy.id == convoy_id).first()
    if not convoy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Конвой не найден")
    return convoy


def _require_active_member(db: Session, convoy_id: str, user_id: str) -> ConvoyMember:
    member = (
        db.query(ConvoyMember)
        .filter(ConvoyMember.convoy_id == convoy_id, ConvoyMember.user_id == user_id, ConvoyMember.left_at.is_(None))
        .first()
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не участник этого конвоя")
    return member


def _enrich(db: Session, convoy: Convoy) -> ConvoyOut:
    active_members = (
        db.query(ConvoyMember)
        .filter(ConvoyMember.convoy_id == convoy.id, ConvoyMember.left_at.is_(None))
        .order_by(ConvoyMember.joined_at.asc())
        .all()
    )
    user_map = users_by_ids(db, [m.user_id for m in active_members])
    members_out = []
    for m in active_members:
        u = user_map.get(m.user_id)
        if not u:
            continue
        members_out.append(
            ConvoyMemberOut(
                user_id=u.id,
                username=u.username,
                full_name=u.full_name,
                avatar_url=u.avatar_url,
                is_creator=(u.id == convoy.creator_id),
                joined_at=m.joined_at,
                lat=u.last_lat,
                lng=u.last_lng,
                location_updated_at=u.location_updated_at,
            )
        )
    out = ConvoyOut.model_validate(convoy)
    out.members = members_out
    return out


def _mark_me(out: ConvoyOut, current_user_id: str) -> ConvoyOut:
    for m in out.members:
        m.is_me = m.user_id == current_user_id
    return out


@router.post("", response_model=ConvoyOut, status_code=status.HTTP_201_CREATED, summary="Создать конвой")
def create_convoy(
    payload: ConvoyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if _active_membership(db, current_user.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Вы уже состоите в активном конвое — сначала покиньте его")

    convoy = Convoy(
        name=payload.name,
        creator_id=current_user.id,
        invite_code=generate_unique_invite_code(db),
        destination_label=payload.destination_label,
        destination_lat=payload.destination_lat,
        destination_lng=payload.destination_lng,
    )
    db.add(convoy)
    db.flush()
    db.add(ConvoyMember(convoy_id=convoy.id, user_id=current_user.id))
    db.commit()
    db.refresh(convoy)
    return _mark_me(_enrich(db, convoy), current_user.id)


@router.post("/join", response_model=ConvoyOut, summary="Присоединиться к конвою по коду")
def join_convoy(
    payload: ConvoyJoinIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    code = payload.invite_code.strip().upper()
    convoy = db.query(Convoy).filter(Convoy.invite_code == code, Convoy.status == "active").first()
    if not convoy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Конвой с таким кодом не найден или уже завершён")

    existing_active = _active_membership(db, current_user.id)
    if existing_active:
        if existing_active.convoy_id == convoy.id:
            return _mark_me(_enrich(db, convoy), current_user.id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Вы уже состоите в активном конвое — сначала покиньте его")

    prior = (
        db.query(ConvoyMember)
        .filter(ConvoyMember.convoy_id == convoy.id, ConvoyMember.user_id == current_user.id)
        .first()
    )
    if prior:
        prior.left_at = None
        prior.joined_at = utcnow()
    else:
        db.add(ConvoyMember(convoy_id=convoy.id, user_id=current_user.id))
    db.commit()
    db.refresh(convoy)
    return _mark_me(_enrich(db, convoy), current_user.id)


@router.get("/mine", response_model=ConvoyOut | None, summary="Мой текущий активный конвой")
def my_convoy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    member = _active_membership(db, current_user.id)
    if not member:
        return None
    convoy = _get_convoy_or_404(db, member.convoy_id)
    return _mark_me(_enrich(db, convoy), current_user.id)


@router.get("/{convoy_id}", response_model=ConvoyOut, summary="Информация о конвое")
def get_convoy(
    convoy_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    convoy = _get_convoy_or_404(db, convoy_id)
    _require_active_member(db, convoy_id, current_user.id)
    return _mark_me(_enrich(db, convoy), current_user.id)


@router.post("/{convoy_id}/destination", response_model=ConvoyOut, summary="Обновить точку назначения (только создатель)")
def update_destination(
    convoy_id: str,
    payload: ConvoyDestinationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    convoy = _get_convoy_or_404(db, convoy_id)
    if convoy.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Конвой уже завершён")
    if convoy.creator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Изменить точку назначения может только создатель конвоя")
    convoy.destination_label = payload.destination_label
    convoy.destination_lat = payload.destination_lat
    convoy.destination_lng = payload.destination_lng
    db.commit()
    db.refresh(convoy)
    return _mark_me(_enrich(db, convoy), current_user.id)


@router.post("/{convoy_id}/leave", response_model=ConvoyOut, summary="Покинуть конвой")
def leave_convoy(
    convoy_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    convoy = _get_convoy_or_404(db, convoy_id)
    member = _require_active_member(db, convoy_id, current_user.id)
    member.left_at = utcnow()
    db.flush()

    remaining = (
        db.query(ConvoyMember)
        .filter(ConvoyMember.convoy_id == convoy_id, ConvoyMember.left_at.is_(None))
        .order_by(ConvoyMember.joined_at.asc())
        .all()
    )
    if not remaining:
        convoy.status = "ended"
        convoy.ended_at = utcnow()
    elif convoy.creator_id == current_user.id:
        # Создатель ушёл — старшинство переходит следующему по времени входа.
        convoy.creator_id = remaining[0].user_id

    db.commit()
    db.refresh(convoy)
    return _mark_me(_enrich(db, convoy), current_user.id)


@router.post("/{convoy_id}/end", response_model=ConvoyOut, summary="Завершить конвой (только создатель)")
def end_convoy(
    convoy_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    convoy = _get_convoy_or_404(db, convoy_id)
    if convoy.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Конвой уже завершён")
    if convoy.creator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Завершить конвой может только создатель")

    now = utcnow()
    db.query(ConvoyMember).filter(ConvoyMember.convoy_id == convoy_id, ConvoyMember.left_at.is_(None)).update(
        {ConvoyMember.left_at: now}, synchronize_session=False
    )
    convoy.status = "ended"
    convoy.ended_at = now
    db.commit()
    db.refresh(convoy)
    return _mark_me(_enrich(db, convoy), current_user.id)
