"""
Топливный трекер: заправки по каждой машине из гаража + расчёт среднего
расхода (л/100км) и средней цены литра по истории заправок.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.car import Car
from app.models.fuel_entry import FuelEntry
from app.models.user import User
from app.schemas.fuel_entry import (
    FuelEntryCreate,
    FuelEntryListResponse,
    FuelEntryOut,
    FuelStats,
)

router = APIRouter()


def _get_own_car_or_404(db: Session, car_id: str, user_id: str) -> Car:
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Машина не найдена")
    if car.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша машина")
    return car


def _compute_stats(entries: list[FuelEntry]) -> FuelStats:
    """
    Считает суммарную статистику и средний расход по истории заправок.

    Расход л/100км считается только по интервалам между заправками
    "полный бак" (full_tank=True) с указанным пробегом — между двумя такими
    заправками расход = литры второй заправки / (разница пробега / 100).
    Частичные заправки внутри интервала не разбивают его отдельно — это
    упрощение, стандартное для потребительских трекеров расхода.
    """
    total_liters = sum(e.liters for e in entries)
    total_cost = sum(e.total_cost for e in entries)
    avg_price = round(total_cost / total_liters, 2) if total_liters else 0.0

    # Для расчёта расхода нужен порядок по пробегу — сортируем заправки с
    # известным одометром по возрастанию пробега (не по дате: пробег важнее,
    # если записи вносились не строго по хронологии).
    with_odometer = sorted(
        (e for e in entries if e.odometer_km is not None),
        key=lambda e: e.odometer_km,
    )

    consumptions: list[float] = []
    for prev, curr in zip(with_odometer, with_odometer[1:]):
        if not curr.full_tank:
            continue
        distance = curr.odometer_km - prev.odometer_km
        if distance <= 0:
            continue
        consumptions.append(curr.liters / (distance / 100))

    avg_consumption = round(sum(consumptions) / len(consumptions), 1) if consumptions else None
    last_odometer = with_odometer[-1].odometer_km if with_odometer else None

    return FuelStats(
        total_entries=len(entries),
        total_liters=round(total_liters, 2),
        total_cost=round(total_cost, 2),
        avg_price_per_liter=avg_price,
        avg_consumption_l_100km=avg_consumption,
        last_odometer_km=last_odometer,
    )


@router.post("", response_model=FuelEntryOut, status_code=status.HTTP_201_CREATED, summary="Добавить заправку")
def create_fuel_entry(
    payload: FuelEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_own_car_or_404(db, payload.car_id, current_user.id)

    entry = FuelEntry(user_id=current_user.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/car/{car_id}", response_model=FuelEntryListResponse, summary="Заправки по машине + статистика")
def list_for_car(
    car_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_own_car_or_404(db, car_id, current_user.id)

    items = (
        db.query(FuelEntry)
        .filter(FuelEntry.car_id == car_id)
        .order_by(FuelEntry.date.desc())
        .all()
    )

    return FuelEntryListResponse(items=items, stats=_compute_stats(items))


@router.delete("/{entry_id}", summary="Удалить заправку")
def delete_fuel_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    entry = db.query(FuelEntry).filter(FuelEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заправка не найдена")
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    db.delete(entry)
    db.commit()
    return {"message": "Удалено"}
