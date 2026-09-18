from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.report import REPORT_REASONS, REPORT_TARGET_TYPES
from app.schemas.user import UserPublic


class ReportCreate(BaseModel):
    target_type: str = Field(..., examples=["user"])
    target_id: str = Field(..., examples=["<id>"])
    reason: str = Field(..., examples=["spam"])
    description: Optional[str] = Field(
        None, max_length=1000, examples=["Спамит рекламой в комментариях"]
    )

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, v: str) -> str:
        if v not in REPORT_TARGET_TYPES:
            raise ValueError(f"target_type должен быть одним из: {', '.join(REPORT_TARGET_TYPES)}")
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if v not in REPORT_REASONS:
            raise ValueError(f"reason должен быть одним из: {', '.join(REPORT_REASONS)}")
        return v


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reporter_id: str
    target_type: str
    target_id: str
    reason: str
    description: Optional[str] = None
    status: str
    resolution_note: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    # Заполняются отдельно в списке жалоб (admin.list_reports) — не хранятся в таблице.
    reporter: Optional[UserPublic] = None
    target_user: Optional[UserPublic] = None


class ReportListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ReportOut]


class ReportResolve(BaseModel):
    status: str = Field(..., examples=["resolved"])
    resolution_note: Optional[str] = Field(None, max_length=1000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("resolved", "dismissed"):
            raise ValueError("status должен быть 'resolved' или 'dismissed'")
        return v


class UserBanPayload(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, examples=["Оскорбления в чате"])
