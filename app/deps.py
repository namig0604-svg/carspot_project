from typing import Optional
 
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
 
from app.database import get_db
from app.models.base import utcnow
from app.models.user import User
from app.security import decode_access_token
 
# tokenUrl указывает на форму логина — кнопка Authorize в Swagger будет работать
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)
 
CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Требуется авторизация",
    headers={"WWW-Authenticate": "Bearer"},
)
 
 
def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Достаёт пользователя из JWT. Бросает 401, если токена нет или он плохой."""
    if not token:
        raise CREDENTIALS_ERROR
 
    user_id = decode_access_token(token)
    if not user_id:
        raise CREDENTIALS_ERROR
 
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise CREDENTIALS_ERROR
 
    _touch_last_seen(db, user)
    return user
 
 
def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Пользователь должен быть не заблокирован."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован",
        )
    return current_user
 
 
def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Пользователь, если авторизован. Иначе None — без ошибки."""
    if not token:
        return None
    user_id = decode_access_token(token)
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        _touch_last_seen(db, user)
    return user
 
 
def _touch_last_seen(db: Session, user: User) -> None:
    """Обновляет last_seen_at не чаще раза в минуту, чтобы не долбить БД на каждый запрос."""
    now = utcnow()
    if not user.last_seen_at or (now - user.last_seen_at).total_seconds() >= 60:
        user.last_seen_at = now
        db.commit()
 
 
class Pagination:
    """Стандартная пагинация: ?limit=&offset="""
 
    def __init__(
        self,
        limit: int = Query(50, ge=1, le=200, description="Сколько записей вернуть"),
        offset: int = Query(0, ge=0, description="Сколько записей пропустить"),
    ):
        self.limit = limit
        self.offset = offset
 
