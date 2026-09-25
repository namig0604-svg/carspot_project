from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPublic


class ClubCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, examples=["Tbilisi JDM Crew"])
    description: Optional[str] = Field(None, examples=["Клуб любителей японских авто в Тбилиси"])
    logo_url: Optional[str] = Field(None, max_length=500)
    cover_url: Optional[str] = Field(None, max_length=500)
    country: Optional[str] = Field(None, max_length=50, examples=["Georgia"])
    city: Optional[str] = Field(None, max_length=100, examples=["Tbilisi"])
    tags: Optional[str] = Field(None, max_length=300, examples=["JDM,Drift,Stance"])
    is_public: bool = True


class ClubUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = None
    logo_url: Optional[str] = Field(None, max_length=500)
    cover_url: Optional[str] = Field(None, max_length=500)
    country: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = Field(None, max_length=300)
    is_public: Optional[bool] = None


class ClubOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    cover_url: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    tags: Optional[str] = None
    is_public: bool
    is_verified: bool
    members_count: int
    events_count: int
    created_at: datetime
    is_favorite: bool = False


class ClubDetail(ClubOut):
    owner: Optional[UserPublic] = None
    chat_room_id: Optional[str] = None
    my_role: Optional[str] = None      # owner / admin / member / None
    my_status: Optional[str] = None    # approved / pending / None


class ClubMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    user_id: str
    role: str
    status: str
    joined_at: datetime
    custom_title: Optional[str] = None
    user: Optional[UserPublic] = None


class ClubRoleUpdate(BaseModel):
    role: str = Field(..., examples=["admin"], description="owner | admin | moderator | member")


class ClubMemberTitleUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=40, description="Кастомное звание участника, например \"Ветеран\". null — снять")


class ClubListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ClubOut]


class ClubLeaderboardOut(BaseModel):
    """Строка рейтинга клубов: активность (события, участники, оценки)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    logo_url: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    is_verified: bool = False
    members_count: int = 0
    events_count: int = 0
    average_rating: float = 0.0
    score: int = 0
