from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, examples=["namig"])
    email: EmailStr = Field(..., examples=["namig@example.com"])
    password: str = Field(..., min_length=6, max_length=72, examples=["SuperPass123"])
    full_name: Optional[str] = Field(None, max_length=100, examples=["Namig Nabiev"])
    country: Optional[str] = Field(None, max_length=50, examples=["Georgia"])
    city: Optional[str] = Field(None, max_length=100, examples=["Tbilisi"])
    referral_code: Optional[str] = Field(None, max_length=20, examples=["NAMIG1234"])


class UserLogin(BaseModel):
    username: str = Field(..., description="Имя пользователя или email")
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = None
    avatar_url: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=30)
    country: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=100)
    instagram: Optional[str] = Field(None, max_length=100)


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=72)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., examples=["namig@example.com"])


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, examples=["123456"])
    new_password: str = Field(..., min_length=6, max_length=72)


class UserPublic(BaseModel):
    """Профиль, видимый другим пользователям."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    instagram: Optional[str] = None
    is_verified: bool = False
    is_admin: bool = False
    is_premium: bool = False
    is_online: bool = False
    average_rating: float = 0.0
    ratings_count: int = 0
    events_created: int = 0
    events_attended: int = 0
    cars_count: int = 0
    likes_count: int = 0
    is_liked: bool = False
    xp: int = 0  # бонусный опыт за монеты — плюсуется к уровню, который считает фронтенд
    equipped_frame: Optional[str] = None
    equipped_badge: Optional[str] = None
    equipped_name_color: Optional[str] = None
    created_at: datetime


class UserMe(UserPublic):
    """Собственный профиль — с приватными полями."""

    email: EmailStr
    phone: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False
    referral_code: Optional[str] = None
    premium_until: Optional[datetime] = None
    premium_trial_used: bool = False
    profile_views_count: int = 0
    coin_balance: int = 0
    profile_boosted_until: Optional[datetime] = None


class UserAdminOut(UserPublic):
    """Профиль для админки — с приватными полями, видимыми только модератору."""

    email: EmailStr
    is_active: bool = True
    is_admin: bool = False
    ban_reason: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserMe


class ReferralInfo(BaseModel):
    """Свой реферальный код, число приглашённых и прогресс до награды Premium."""

    code: Optional[str] = None
    referrals_count: int = 0
    referrals_per_premium_month: int = 10
    referrals_until_next_reward: int = 10
    premium_months_earned: int = 0


class ProfileViewOut(BaseModel):
    """Одна строка списка 'кто смотрел мой профиль' (Premium)."""

    user: UserPublic
    viewed_at: datetime
