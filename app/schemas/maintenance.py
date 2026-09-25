from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.maintenance import MAINTENANCE_TYPES


class MaintenanceCreate(BaseModel):
    car_id: str
    type: str = Field("other", examples=["oil"])
    title: str = Field(..., max_length=200)
    done_at: datetime
    mileage_km: Optional[int] = Field(None, ge=0)
    cost: Optional[float] = Field(None, ge=0)
    note: Optional[str] = Field(None, max_length=1000)
    photo_url: Optional[str] = None
    next_due_at: Optional[datetime] = None
    next_due_mileage_km: Optional[int] = Field(None, ge=0)
    is_seasonal: Optional[str] = None  # "winter" | "summer"

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in MAINTENANCE_TYPES:
            raise ValueError(f"type должен быть одним из: {', '.join(MAINTENANCE_TYPES)}")
        return v

    @field_validator("is_seasonal")
    @classmethod
    def _check_seasonal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("winter", "summer"):
            raise ValueError("is_seasonal должен быть 'winter' или 'summer'")
        return v


class MaintenanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    car_id: str
    user_id: str
    type: str
    title: str
    done_at: datetime
    mileage_km: Optional[int] = None
    cost: Optional[float] = None
    note: Optional[str] = None
    photo_url: Optional[str] = None
    next_due_at: Optional[datetime] = None
    next_due_mileage_km: Optional[int] = None
    is_seasonal: Optional[str] = None
    created_at: datetime


class MaintenanceListResponse(BaseModel):
    total: int
    items: List[MaintenanceOut]
