from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.car_expense import EXPENSE_CATEGORIES


class CarExpenseCreate(BaseModel):
    car_id: str
    category: str = Field("other")
    amount: float = Field(..., ge=0)
    date: datetime
    note: Optional[str] = Field(None, max_length=300)

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str) -> str:
        if v not in EXPENSE_CATEGORIES:
            raise ValueError(f"category должен быть одним из: {', '.join(EXPENSE_CATEGORIES)}")
        return v


class CarExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    car_id: str
    user_id: str
    category: str
    amount: float
    date: datetime
    note: Optional[str] = None
    created_at: datetime


class CarExpenseListResponse(BaseModel):
    total: int
    total_amount: float
    by_category: Dict[str, float]
    items: List[CarExpenseOut]
