from datetime import timedelta

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base
from app.models.base import new_id, utcnow
# Считаем юзера "онлайн", если он делал запрос к API в последние N минут
ONLINE_THRESHOLD_MINUTES = 5


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_id)

    # --- Учётные данные ---
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # --- Профиль ---
    full_name = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    phone = Column(String(30), nullable=True)
    country = Column(String(50), nullable=True, index=True)
    city = Column(String(100), nullable=True, index=True)
    instagram = Column(String(100), nullable=True)

    # --- Статусы ---
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    ban_reason = Column(Text, nullable=True)

    # --- CarSpot Premium ---
    # is_premium больше не хранимый флаг, а вычисляется из premium_until (см. ниже) —
    # так же, как is_online вычисляется из last_seen_at. Продлевается 14-дневным
    # пробным периодом (once) и реферальной программой (см. services.py).
    premium_until = Column(DateTime, nullable=True)
    premium_trial_used = Column(Boolean, default=False, nullable=False)
    referral_premium_claimed_count = Column(Integer, default=0, nullable=False)

    # --- Статистика (денормализована для скорости) ---
    average_rating = Column(Float, default=0.0, nullable=False)
    ratings_count = Column(Integer, default=0, nullable=False)
    events_created = Column(Integer, default=0, nullable=False)
    events_attended = Column(Integer, default=0, nullable=False)
    cars_count = Column(Integer, default=0, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    profile_views_count = Column(Integer, default=0, nullable=False)

    # --- Реферальная программа ---
    referral_code = Column(String(20), unique=True, index=True, nullable=True)
    referred_by_id = Column(String(36), index=True, nullable=True)

    # --- Служебное ---
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=True)
    @property
    def is_online(self) -> bool:
        """Онлайн = делал авторизованный запрос за последние ONLINE_THRESHOLD_MINUTES."""
        if not self.last_seen_at:
            return False
        return (utcnow() - self.last_seen_at) <= timedelta(minutes=ONLINE_THRESHOLD_MINUTES)

    @property
    def is_premium(self) -> bool:
        """Premium активен = premium_until в будущем (пробный период или награда за рефералов)."""
        return bool(self.premium_until and self.premium_until > utcnow())


class UserLike(Base):
    """Лайк профиля — один пользователь может лайкнуть другого один раз."""

    __tablename__ = "user_likes"
    __table_args__ = (
        UniqueConstraint("target_user_id", "liker_user_id", name="uq_user_like"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    target_user_id = Column(String(36), index=True, nullable=False)
    liker_user_id = Column(String(36), index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ProfileView(Base):
    """Просмотр профиля — храним по одной записи на пару (кого смотрели, кто смотрел),
    обновляя updated_at при повторном визите, чтобы список 'кто смотрел' не раздувался."""

    __tablename__ = "profile_views"
    __table_args__ = (
        UniqueConstraint("viewed_user_id", "viewer_id", name="uq_profile_view"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    viewed_user_id = Column(String(36), index=True, nullable=False)
    viewer_id = Column(String(36), index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class PasswordResetToken(Base):
    """Код восстановления пароля, отправленный на email.

    Храним хеш кода (bcrypt, как и пароль), а не сам код — чтобы утечка БД
    не давала возможность восстановить чужой аккаунт. Код одноразовый и
    короткоживущий (см. PASSWORD_RESET_CODE_TTL_MINUTES в config.py).
    """

    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), index=True, nullable=False)
    code_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
