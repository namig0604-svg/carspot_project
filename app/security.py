"""
Пароли и JWT-токены.

Используем bcrypt напрямую (без passlib) — меньше зависимостей
и нет проблем совместимости passlib + bcrypt 4.x.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from app.config import settings

# bcrypt обрезает пароль до 72 байт — обрезаем сами, чтобы не было ошибки
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Возвращает bcrypt-хеш пароля."""
    pwd_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль против хеша. Никогда не бросает исключение."""
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return False


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """Создаёт JWT. subject — это user.id."""
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """
    Проверяет токен и возвращает user_id.
    Возвращает None, если токен невалиден или просрочен.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        return str(user_id) if user_id else None
    except Exception:  # noqa: BLE001  (просрочен, подделан, битый — всё одно)
        return None


def token_expires_in_seconds() -> int:
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
