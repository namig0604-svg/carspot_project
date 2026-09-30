"""
Трекер поездок: запись маршрута (GPS), дистанция/время/скорость по каждой
поездке + агрегированная статистика вождения (всего км, разбивка по месяцам).

Все агрегаты по конкретной поездке считает клиент (см. TripCreate) — у него
есть живой поток геопозиции, у бэкенда его нет. Бэкенд просто сохраняет и
отдаёт обратно, как и с заправками в app/api/fuel_entries.py.
"""
import json
from collections import OrderedDict
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.car import Car
from app.models.trip import Trip
from app.models.user import User
from app.schemas.trip import (
    TripCreate,
    TripListResponse,
    TripOut,
    TripPoint,
    TripStats,
    TripSummaryOut,
    MonthlyDistance,
)

router = APIRouter()


def _route_to_json(points: List[TripPoint]) -> str:
    return json.dumps([p.model_dump() for p in points])


def _route_from_json(raw: str) -> List[TripPoint]:
    try:
        return [TripPoint(**p) for p in json.loads(raw)]
    except Exception:
        return []


def _check_own_car(db: Session, car_id: str, user_id: str) -> None:
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Машина не найдена")
    if car.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша машина")


def _get_own_trip_or_404(db: Session, trip_id: str, user_id: str) -> Trip:
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Поездка не найдена")
    if trip.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    return trip


@router.post("", response_model=TripOut, status_code=status.HTTP_201_CREATED, summary="Сохранить записанную поездку")
def create_trip(
    payload: TripCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.car_id:
        _check_own_car(db, payload.car_id, current_user.id)

    trip = Trip(
        user_id=current_user.id,
        car_id=payload.car_id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        distance_km=payload.distance_km,
        duration_s=payload.duration_s,
        avg_speed_kmh=payload.avg_speed_kmh,
        top_speed_kmh=payload.top_speed_kmh,
        route_json=_route_to_json(payload.route),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)

    return TripOut(
        id=trip.id,
        user_id=trip.user_id,
        car_id=trip.car_id,
        started_at=trip.started_at,
        ended_at=trip.ended_at,
        distance_km=trip.distance_km,
        duration_s=trip.duration_s,
        avg_speed_kmh=trip.avg_speed_kmh,
        top_speed_kmh=trip.top_speed_kmh,
        created_at=trip.created_at,
        route=payload.route,
    )


@router.get("/mine", response_model=TripListResponse, summary="Мои поездки (без маршрута)")
def list_mine(
    car_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = db.query(Trip).filter(Trip.user_id == current_user.id)
    if car_id:
        q = q.filter(Trip.car_id == car_id)
    items = q.order_by(Trip.started_at.desc()).limit(limit).all()
    return TripListResponse(items=[TripSummaryOut.model_validate(t) for t in items])


@router.get("/stats/mine", response_model=TripStats, summary="Статистика вождения за всё время + по месяцам")
def stats_mine(
    car_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = db.query(Trip).filter(Trip.user_id == current_user.id)
    if car_id:
        q = q.filter(Trip.car_id == car_id)
    trips = q.all()

    total_distance = sum(t.distance_km for t in trips)
    total_duration = sum(t.duration_s for t in trips)
    top_speed = max((t.top_speed_kmh for t in trips), default=0.0)

    # Последние 6 календарных месяцев (включая текущий), по возрастанию —
    # с нулями там, где поездок не было, чтобы график не "прыгал".
    now = datetime.utcnow()
    months: "OrderedDict[str, float]" = OrderedDict()
    for i in range(5, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        months[f"{year:04d}-{month:02d}"] = 0.0

    for t in trips:
        key = f"{t.started_at.year:04d}-{t.started_at.month:02d}"
        if key in months:
            months[key] += t.distance_km

    return TripStats(
        total_trips=len(trips),
        total_distance_km=round(total_distance, 1),
        total_duration_s=int(total_duration),
        top_speed_kmh=round(top_speed, 1),
        monthly=[MonthlyDistance(month=k, distance_km=round(v, 1)) for k, v in months.items()],
    )


@router.get("/{trip_id}", response_model=TripOut, summary="Детали поездки (с маршрутом)")
def get_trip(
    trip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    trip = _get_own_trip_or_404(db, trip_id, current_user.id)
    return TripOut(
        id=trip.id,
        user_id=trip.user_id,
        car_id=trip.car_id,
        started_at=trip.started_at,
        ended_at=trip.ended_at,
        distance_km=trip.distance_km,
        duration_s=trip.duration_s,
        avg_speed_kmh=trip.avg_speed_kmh,
        top_speed_kmh=trip.top_speed_kmh,
        created_at=trip.created_at,
        route=_route_from_json(trip.route_json),
    )


@router.delete("/{trip_id}", summary="Удалить поездку")
def delete_trip(
    trip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    trip = _get_own_trip_or_404(db, trip_id, current_user.id)
    db.delete(trip)
    db.commit()
    return {"message": "Удалено"}
