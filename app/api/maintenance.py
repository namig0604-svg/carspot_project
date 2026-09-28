from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import premium_tiers
from app.database import get_db
from app.deps import get_current_active_user
from app.models.car import Car
from app.models.fuel_entry import FuelEntry
from app.models.maintenance import MaintenanceRecord
from app.models.user import User
from app.schemas.maintenance import (
    MaintenanceCreate,
    MaintenanceForecastItem,
    MaintenanceForecastResponse,
    MaintenanceListResponse,
    MaintenanceOut,
)

router = APIRouter()

# Типы, для которых имеет смысл прогнозировать следующий раз — "repair" и
# "other" разовые/непредсказуемые по своей природе, их не прогнозируем.
_FORECASTABLE_TYPES = ("oil", "tires", "brakes", "filters", "inspection", "insurance")


def _get_own_car_or_404(db: Session, car_id: str, user_id: str) -> Car:
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Машина не найдена")
    if car.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша машина")
    return car


@router.post("", response_model=MaintenanceOut, status_code=status.HTTP_201_CREATED, summary="Добавить запись в сервисный дневник")
def create_record(
    payload: MaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_own_car_or_404(db, payload.car_id, current_user.id)

    record = MaintenanceRecord(user_id=current_user.id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/car/{car_id}", response_model=MaintenanceListResponse, summary="История ТО машины")
def list_for_car(
    car_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_own_car_or_404(db, car_id, current_user.id)

    items = (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.car_id == car_id)
        .order_by(MaintenanceRecord.done_at.desc())
        .all()
    )
    return MaintenanceListResponse(total=len(items), items=items)


@router.get(
    "/forecast/{car_id}",
    response_model=MaintenanceForecastResponse,
    summary="Прогноз следующего ТО по истории (CarSpot Max)",
)
def forecast_for_car(
    car_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not premium_tiers.can_use_maintenance_forecast(current_user) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Прогноз ТО доступен только с CarSpot Max",
        )

    _get_own_car_or_404(db, car_id, current_user.id)

    records = (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.car_id == car_id, MaintenanceRecord.type.in_(_FORECASTABLE_TYPES))
        .order_by(MaintenanceRecord.done_at.asc())
        .all()
    )

    by_type: dict = defaultdict(list)
    for r in records:
        by_type[r.type].append(r)

    # "Текущий пробег" машины — максимум среди пробегов записей ТО и заправок
    # (Car сам по себе пробег не хранит, только каждая запись по отдельности).
    mileages = [r.mileage_km for r in records if r.mileage_km is not None]
    fuel_odometers = [
        int(o)
        for (o,) in db.query(FuelEntry.odometer_km)
        .filter(FuelEntry.car_id == car_id, FuelEntry.odometer_km.isnot(None))
        .all()
    ]
    mileages.extend(fuel_odometers)
    current_mileage = max(mileages) if mileages else None

    now = datetime.utcnow()
    items = []

    for type_, group in by_type.items():
        last = group[-1]  # group отсортирован по done_at asc

        predicted_at = last.next_due_at
        predicted_mileage = last.next_due_mileage_km
        source = "manual" if (predicted_at or predicted_mileage) else None

        if source is None and len(group) >= 2:
            # Средний интервал между прошлыми записями этого же типа — по
            # датам и (где есть пробег на обеих записях) по километражу.
            day_gaps = [(group[i].done_at - group[i - 1].done_at).days for i in range(1, len(group))]
            day_gaps = [g for g in day_gaps if g > 0]
            if day_gaps:
                avg_days = sum(day_gaps) / len(day_gaps)
                predicted_at = last.done_at + timedelta(days=avg_days)

            km_pairs = [(group[i - 1].mileage_km, group[i].mileage_km) for i in range(1, len(group))]
            km_gaps = [b - a for a, b in km_pairs if a is not None and b is not None and b > a]
            if km_gaps and last.mileage_km is not None:
                avg_km = sum(km_gaps) / len(km_gaps)
                predicted_mileage = int(last.mileage_km + avg_km)

            if predicted_at or predicted_mileage:
                source = "estimated"

        if source is None:
            continue  # недостаточно истории, чтобы что-то предсказать

        overdue = False
        soon = False
        if predicted_at is not None:
            if predicted_at <= now:
                overdue = True
            elif predicted_at <= now + timedelta(days=30):
                soon = True
        if predicted_mileage is not None and current_mileage is not None:
            if current_mileage >= predicted_mileage:
                overdue = True
            elif current_mileage >= predicted_mileage - 1000:
                soon = True

        urgency = "overdue" if overdue else ("soon" if soon else "ok")

        items.append(
            MaintenanceForecastItem(
                type=type_,
                last_done_at=last.done_at,
                last_mileage_km=last.mileage_km,
                predicted_next_at=predicted_at,
                predicted_next_mileage_km=predicted_mileage,
                source=source,
                urgency=urgency,
            )
        )

    order = {"overdue": 0, "soon": 1, "ok": 2}
    items.sort(key=lambda it: order[it.urgency])

    return MaintenanceForecastResponse(current_mileage_km=current_mileage, items=items)


@router.delete("/{record_id}", summary="Удалить запись сервисного дневника")
def delete_record(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    record = db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    if record.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    db.delete(record)
    db.commit()
    return {"message": "Запись удалена"}
