"""
Регистрация и авторизация.
"""
import random
import re
import string
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_active_user
from app.verification import recompute_is_verified
from app.email_utils import send_password_reset_code
from app.models.base import new_id, utcnow
from app.models.user import PasswordResetToken, User
from app.schemas.user import (
    ForgotPasswordRequest,
    PasswordChange,
    ResetPasswordRequest,
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
from app.services import grant_referral_premium_if_earned

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


def _generate_referral_code(db: Session, username: str) -> str:
    """Генерирует уникальный реферальный код на основе логина."""
    base = re.sub(r"[^A-Za-z0-9]", "", username).upper()[:10] or "USER"
    code = base
    while db.query(User).filter(User.referral_code == code).first():
        suffix = "".join(random.choices(string.digits, k=4))
        code = f"{base}{suffix}"[:20]
    return code


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

    # --- Реферальная программа ---
    user.referral_code = _generate_referral_code(db, username)
    if payload.referral_code:
        referrer = (
            db.query(User)
            .filter(func.upper(User.referral_code) == payload.referral_code.strip().upper())
            .first()
        )
        if referrer and referrer.id != user.id:
            user.referred_by_id = referrer.id

    db.add(user)
    db.flush()  # чтобы новый пользователь уже учитывался в подсчёте рефералов ниже

    # Если пригласивший как раз набрал ещё 10 приглашённых — начисляем ему Premium.
    grant_referral_premium_if_earned(db, user.referred_by_id)

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
def read_me(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Единственный критерий верификации, не завязанный ни на одно действие
    # пользователя, — возраст аккаунта, поэтому пересчитываем и здесь: иначе
    # галочка появилась бы только при следующем join/leave сходки, а не
    # ровно тогда, когда исполнилось VERIFICATION_MIN_ACCOUNT_AGE_DAYS.
    recompute_is_verified(db, current_user)
    db.commit()
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


def _generate_reset_code() -> str:
    return "".join(random.choices(string.digits, k=6))


@router.post(
    "/forgot-password",
    summary="Запросить код восстановления пароля на email",
)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Всегда отвечает одинаково (не выдаём, существует ли такой email — иначе
    по ответу можно было бы проверять чужие email на регистрацию в CarSpot).
    Если аккаунт с таким email есть — отправляем 6-значный код на почту.
    """
    generic_response = {
        "message": "Если аккаунт с таким email существует, мы отправили на него код восстановления"
    }

    email = str(payload.email).strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user or not user.is_active:
        return generic_response

    # Предыдущие неиспользованные коды этого пользователя больше не действуют —
    # чтобы старое письмо нельзя было использовать после запроса нового кода.
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: utcnow()}, synchronize_session=False)

    code = _generate_reset_code()
    token = PasswordResetToken(
        id=new_id(),
        user_id=user.id,
        code_hash=hash_password(code),
        expires_at=utcnow() + timedelta(minutes=settings.PASSWORD_RESET_CODE_TTL_MINUTES),
    )
    db.add(token)
    db.commit()

    send_password_reset_code(user.email, user.username, code)

    return generic_response


@router.post(
    "/reset-password",
    summary="Сбросить пароль по коду из письма",
)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Неверный код или email")

    candidates = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > utcnow(),
        )
        .order_by(PasswordResetToken.created_at.desc())
        .all()
    )

    matching = next(
        (t for t in candidates if verify_password(payload.code.strip(), t.code_hash)),
        None,
    )
    if not matching:
        raise HTTPException(status_code=400, detail="Неверный или просроченный код")

    matching.used_at = utcnow()
    user.hashed_password = hash_password(payload.new_password)
    db.commit()

    return {"message": "Пароль успешно изменён, теперь можно войти с новым паролем"}
