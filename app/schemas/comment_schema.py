"""Комментарии к сходкам и фото."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.comment import COMMENT_TARGET_TYPES
from app.schemas.user import UserPublic


class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Комментарий не может быть пустым")
        return v


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_type: str
    target_id: str
    text: str
    created_at: datetime
    user: Optional[UserPublic] = None
    is_mine: bool = False


class CommentListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[CommentOut]


def validate_target_type(target_type: str) -> str:
    if target_type not in COMMENT_TARGET_TYPES:
        raise ValueError(f"target_type должен быть одним из: {', '.join(COMMENT_TARGET_TYPES)}")
    return target_type
