"""
Регистрация и авторизация.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.base import utcnow
from app.models.user import User
from app.schemas.user import (
    PasswordChange,
    Token,
    UserLogin,
    UserMe,
    UserRegister,
)
from app.security import (
    create_access_token,
    hash_password,
    token_expires_in_seconds,
    verify_password,
)

router = APIRouter()


def _find_user(db: Session, login: str) -> User | None:
    """Ищет пользователя по username или email (без учёта регистра)."""
    login = (login or "").strip()
    if not login:
        return None
    return (
        db.query(User)
        .filter(
            (func.lower(User.username) == login.lower())
            | (func.lower(User.email) == login.lower())
        )
        .first()
    )


def _build_token(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.id),
        token_type="bearer",
        expires_in=token_expires_in_seconds(),
        user=UserMe.model_validate(user),
    )


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Создаёт аккаунт и сразу возвращает токен — отдельный вход не нужен."""
    username = payload.username.strip()
    email = str(payload.email).strip().lower()

    if db.query(User).filter(func.lower(User.username) == username.lower()).first():
        raise HTTPException(status_code=400, detail="Это имя пользователя уже занято")

    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=400, detail="Этот email уже зарегистрирован")

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        country=payload.country,
        city=payload.city,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _build_token(user)


@router.post("/login", response_model=Token, summary="Вход (JSON)")
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Вход по username или email. Возвращает JWT."""
    user = _find_user(db, payload.username)

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")

    user.last_seen_at = utcnow()
    db.commit()
    db.refresh(user)

    return _build_token(user)


@router.post("/token", response_model=Token, summary="Вход (form-data, для Swagger)")
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Тот же вход, но в формате OAuth2 — чтобы работала кнопка **Authorize**
    в Swagger UI. В поле username можно вводить и email.
    """
    user = _find_user(db, form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_seen_at = utcnow()
    db.commit()
    db.refresh(user)

    return _build_token(user)


@router.get("/me", response_model=UserMe, summary="Мой профиль")
def read_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.post("/change-password", summary="Сменить пароль")
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Текущий пароль неверный")

    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Пароль изменён"}
