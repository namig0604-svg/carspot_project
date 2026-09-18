from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CarBase(BaseModel):
    make: str = Field(..., max_length=50, examples=["Nissan"])
    model: str = Field(..., max_length=50, examples=["Silvia S15"])
    year: Optional[int] = Field(None, ge=1900, le=2100, examples=[1999])
    generation: Optional[str] = Field(None, max_length=50, examples=["S15"])
    body_type: Optional[str] = Field(None, max_length=30, examples=["coupe"])

    engine: Optional[str] = Field(None, max_length=100, examples=["SR20DET"])
    engine_volume: Optional[str] = Field(None, max_length=20, examples=["2.0"])
    power_hp: Optional[int] = Field(None, ge=0, le=5000, examples=[450])
    torque_nm: Optional[int] = Field(None, ge=0, le=10000, examples=[520])
    drivetrain: Optional[str] = Field(None, max_length=20, examples=["RWD"])
    transmission: Optional[str] = Field(None, max_length=30, examples=["manual"])
    fuel_type: Optional[str] = Field(None, max_length=20, examples=["petrol"])
    weight_kg: Optional[int] = Field(None, ge=0, le=20000, examples=[1240])
    zero_to_hundred: Optional[str] = Field(None, max_length=20, examples=["4.5"])

    color: Optional[str] = Field(None, max_length=50, examples=["Midnight Purple"])
    license_plate: Optional[str] = Field(None, max_length=20, examples=["AA-123-BB"])
    mods: Optional[str] = Field(None, examples=["Garrett GT2871R, HKS coilovers, Work Meister S1"])
    description: Optional[str] = None
    photo_url: Optional[str] = Field(None, max_length=500)
    is_primary: bool = False
    is_for_sale: bool = False


class CarCreate(CarBase):
    pass


class CarUpdate(BaseModel):
    make: Optional[str] = Field(None, max_length=50)
    model: Optional[str] = Field(None, max_length=50)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    generation: Optional[str] = Field(None, max_length=50)
    body_type: Optional[str] = Field(None, max_length=30)
    engine: Optional[str] = Field(None, max_length=100)
    engine_volume: Optional[str] = Field(None, max_length=20)
    power_hp: Optional[int] = Field(None, ge=0, le=5000)
    torque_nm: Optional[int] = Field(None, ge=0, le=10000)
    drivetrain: Optional[str] = Field(None, max_length=20)
    transmission: Optional[str] = Field(None, max_length=30)
    fuel_type: Optional[str] = Field(None, max_length=20)
    weight_kg: Optional[int] = Field(None, ge=0, le=20000)
    zero_to_hundred: Optional[str] = Field(None, max_length=20)
    color: Optional[str] = Field(None, max_length=50)
    license_plate: Optional[str] = Field(None, max_length=20)
    mods: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = Field(None, max_length=500)
    is_primary: Optional[bool] = None
    is_for_sale: Optional[bool] = None


class CarOut(CarBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    likes_count: int = 0
    photos: Optional[str] = None
    created_at: datetime


class GarageOut(BaseModel):
    """Гараж пользователя целиком."""

    user_id: str
    username: str
    cars_count: int
    cars: List[CarOut]
