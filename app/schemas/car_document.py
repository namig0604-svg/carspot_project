from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.car_document import DOCUMENT_TYPES


class CarDocumentCreate(BaseModel):
    car_id: str
    type: str = Field("other")
    title: str = Field(..., max_length=200)
    photo_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    note: Optional[str] = Field(None, max_length=500)

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in DOCUMENT_TYPES:
            raise ValueError(f"type должен быть одним из: {', '.join(DOCUMENT_TYPES)}")
        return v


class CarDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    car_id: str
    user_id: str
    type: str
    title: str
    photo_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime


class CarDocumentListResponse(BaseModel):
    total: int
    items: List[CarDocumentOut]
