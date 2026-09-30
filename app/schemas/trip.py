from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TripPoint(BaseModel):
    """Одна точка маршрута. t — секунды от начала поездки (не абсолютное
    время) — так проще и компактнее рисовать маршрут на клиенте."""

    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    t: int = Field(..., ge=0)
    speed_kmh: float = Field(..., ge=0, le=400)


class TripCreate(BaseModel):
    car_id: Optional[str] = None
    started_at: datetime
    ended_at: datetime
    distance_km: float = Field(..., ge=0, le=20_000)
    duration_s: int = Field(..., ge=0, le=86_400 * 3)
    avg_speed_kmh: float = Field(..., ge=0, le=400)
    top_speed_kmh: float = Field(..., ge=0, le=400)
    # Минимум 2 точки — иначе на карте нечего рисовать.
    route: List[TripPoint] = Field(..., min_length=2, max_length=20_000)


class TripSummaryOut(BaseModel):
    """Без маршрута — для списков, чтобы не гонять по сети тяжёлый JSON
    с сотнями точек там, где нужны только дата/дистанция/время."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    car_id: Optional[str] = None
    started_at: datetime
    ended_at: datetime
    distance_km: float
    duration_s: int
    avg_speed_kmh: float
    top_speed_kmh: float
    created_at: datetime


class TripOut(TripSummaryOut):
    """Полная карточка поездки — с маршрутом, для экрана деталей."""

    route: List[TripPoint]


class TripListResponse(BaseModel):
    items: List[TripSummaryOut]


class MonthlyDistance(BaseModel):
    month: str  # "2026-09"
    distance_km: float


class TripStats(BaseModel):
    total_trips: int
    total_distance_km: float
    total_duration_s: int
    top_speed_kmh: float
    # Последние 6 месяцев (включая текущий), по возрастанию.
    monthly: List[MonthlyDistance]
