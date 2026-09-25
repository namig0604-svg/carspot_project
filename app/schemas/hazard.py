from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.hazard import HAZARD_TYPES


class HazardCreate(BaseModel):
    type: str = Field("other")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    note: Optional[str] = Field(None, max_length=300)

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in HAZARD_TYPES:
            raise ValueError(f"type должен быть одним из: {', '.join(HAZARD_TYPES)}")
        return v


class HazardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_by: str
    type: str
    latitude: float
    longitude: float
    note: Optional[str] = None
    confirms_count: int
    denies_count: int
    expires_at: Optional[datetime] = None
    created_at: datetime
    my_vote: Optional[str] = None


class HazardListResponse(BaseModel):
    items: List[HazardOut]


class HazardVoteIn(BaseModel):
    vote: str = Field(..., examples=["confirm"])

    @field_validator("vote")
    @classmethod
    def _check_vote(cls, v: str) -> str:
        if v not in ("confirm", "deny"):
            raise ValueError("vote должен быть 'confirm' или 'deny'")
        return v
