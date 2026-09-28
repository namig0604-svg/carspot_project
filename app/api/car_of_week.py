"""Голосование «Машина недели» — пользователи выставляют свою машину на
голосование в текущую ISO-неделю, остальные голосуют (один голос на
заявку на человека). Победитель предыдущей недели считается «на лету» —
без фонового job'а, только по запросу (GET /winner)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.car import Car
from app.models.car_of_week import CarOfWeekEntry, CarOfWeekVote, week_key
from app.models.user import User
from app.schemas.car import CarOut
from app.schemas.car_of_week import (
    CarOfWeekEntryCreate,
    CarOfWeekEntryListResponse,
    CarOfWeekEntryOut,
)
from app.schemas.user import UserPublic
from app.services import users_by_ids

router = APIRouter()


def _get_entry_or_404(db: Session, entry_id: str) -> CarOfWeekEntry:
    entry = db.query(CarOfWeekEntry).filter(CarOfWeekEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявка не найдена")
    return entry


def _enrich(db: Session, entries: list[CarOfWeekEntry], current_user: User | None) -> list[CarOfWeekEntryOut]:
    if not entries:
        return []
    car_map = {c.id: c for c in db.query(Car).filter(Car.id.in_([e.car_id for e in entries])).all()}
    user_map = users_by_ids(db, [e.user_id for e in entries])

    my_votes: set[str] = set()
    if current_user:
        rows = (
            db.query(CarOfWeekVote)
            .filter(
                CarOfWeekVote.entry_id.in_([e.id for e in entries]),
                CarOfWeekVote.voter_id == current_user.id,
            )
            .all()
        )
        my_votes = {r.entry_id for r in rows}

    items = []
    for entry in entries:
        item = CarOfWeekEntryOut.model_validate(entry)
        car = car_map.get(entry.car_id)
        if car:
            item.car = CarOut.model_validate(car)
        owner = user_map.get(entry.user_id)
        if owner:
            item.owner = UserPublic.model_validate(owner)
        item.my_voted = entry.id in my_votes
        item.is_mine = current_user is not None and entry.user_id == current_user.id
        items.append(item)
    return items


@router.post("/entries", response_model=CarOfWeekEntryOut, status_code=status.HTTP_201_CREATED, summary="Выставить машину на голосование текущей недели")
def create_entry(
    payload: CarOfWeekEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    car = db.query(Car).filter(Car.id == payload.car_id).first()
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Машина не найдена")
    if car.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша машина")

    key = week_key()
    existing = (
        db.query(CarOfWeekEntry)
        .filter(CarOfWeekEntry.week_key == key, CarOfWeekEntry.user_id == current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Вы уже выставили машину на эту неделю")

    entry = CarOfWeekEntry(week_key=key, user_id=current_user.id, car_id=payload.car_id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _enrich(db, [entry], current_user)[0]


@router.get("/entries", response_model=CarOfWeekEntryListResponse, summary="Список заявок недели, отсортирован по голосам")
def list_entries(
    week: str | None = Query(None, description="Неделя в формате 2026-W39, по умолчанию — текущая"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    key = week or week_key()
    entries = (
        db.query(CarOfWeekEntry)
        .filter(CarOfWeekEntry.week_key == key)
        .order_by(CarOfWeekEntry.votes_count.desc(), CarOfWeekEntry.created_at.asc())
        .all()
    )
    return CarOfWeekEntryListResponse(week_key=key, items=_enrich(db, entries, current_user))


@router.get("/winner", response_model=CarOfWeekEntryOut | None, summary="Победитель прошлой недели")
def previous_winner(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    weeks = [row[0] for row in db.query(CarOfWeekEntry.week_key).distinct().all()]
    current_key = week_key()
    past_weeks = sorted((w for w in weeks if w < current_key), reverse=True)
    if not past_weeks:
        return None
    winner = (
        db.query(CarOfWeekEntry)
        .filter(CarOfWeekEntry.week_key == past_weeks[0])
        .order_by(CarOfWeekEntry.votes_count.desc(), CarOfWeekEntry.created_at.asc())
        .first()
    )
    if not winner:
        return None
    return _enrich(db, [winner], current_user)[0]


@router.post("/entries/{entry_id}/vote", response_model=CarOfWeekEntryOut, summary="Проголосовать за заявку (повторный вызов снимает голос)")
def vote_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    entry = _get_entry_or_404(db, entry_id)
    if entry.user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нельзя голосовать за свою машину")

    existing = (
        db.query(CarOfWeekVote)
        .filter(CarOfWeekVote.entry_id == entry_id, CarOfWeekVote.voter_id == current_user.id)
        .first()
    )
    if existing:
        db.delete(existing)
        entry.votes_count = max(0, entry.votes_count - 1)
    else:
        db.add(CarOfWeekVote(entry_id=entry_id, voter_id=current_user.id))
        entry.votes_count += 1

    db.commit()
    db.refresh(entry)
    return _enrich(db, [entry], current_user)[0]


@router.delete("/entries/{entry_id}", summary="Снять свою заявку с голосования")
def delete_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    entry = _get_entry_or_404(db, entry_id)
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша заявка")
    db.query(CarOfWeekVote).filter(CarOfWeekVote.entry_id == entry_id).delete()
    db.delete(entry)
    db.commit()
    return {"message": "Заявка снята с голосования"}
