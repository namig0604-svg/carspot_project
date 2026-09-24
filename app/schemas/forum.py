"""Forum: temy i otvety."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.forum import FORUM_CATEGORIES
from app.schemas.user import UserPublic


class ForumTopicCreate(BaseModel):
    category: str
    country: Optional[str] = Field(None, max_length=50)
    title: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=1, max_length=5000)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in FORUM_CATEGORIES:
            raise ValueError(f"category dolzhen byt odnim iz: {', '.join(FORUM_CATEGORIES)}")
        return v

    @field_validator("title", "body")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Pole ne mozhet byt pustym")
        return v


class ForumReplyCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=3000)

    @field_validator("body")
    @classmethod
    def strip_body(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Otvet ne mozhet byt pustym")
        return v


class ForumTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: str
    country: Optional[str] = None
    title: str
    body: str
    replies_count: int
    created_at: datetime
    author: Optional[UserPublic] = None


class ForumTopicListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ForumTopicOut]


class ForumReplyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    topic_id: str
    body: str
    created_at: datetime
    author: Optional[UserPublic] = None


class ForumTopicDetail(ForumTopicOut):
    replies: List[ForumReplyOut] = []


class ForumCategoryCount(BaseModel):
    category: str
    topics_count: int
