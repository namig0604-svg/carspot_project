from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FuelEntryCreate(BaseModel):
    car_id: str
    date: datetime
    liters: float = Field(..., gt=0, le=1000)
    total_cost: float = Field(..., ge=0)
    odometer_km: Optional[float] = Field(None, ge=0, le=10_000_000)
    full_tank: bool = True
    station: Optional[str] = Field(None, max_length=120)
    note: Optional[str] = Field(None, max_length=300)


class FuelEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    car_id: str
    user_id: str
    date: datetime
    liters: float
    total_cost: float
    price_per_liter: float
    odometer_km: Optional[float] = None
    full_tank: bool
    station: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


class FuelStats(BaseModel):
    total_entries: int
    total_liters: float
    total_cost: float
    avg_price_per_liter: float
    # л/100км — None, если данных недостаточно (нужно минимум две заправки
    # "полный бак" с указанным пробегом, см. _compute_stats в app/api/fuel_entries.py).
    avg_consumption_l_100km: Optional[float] = None
    last_odometer_km: Optional[float] = None


class FuelEntryListResponse(BaseModel):
    items: List[FuelEntryOut]
    stats: FuelStats
