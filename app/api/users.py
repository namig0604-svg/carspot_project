from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.utils.auth import get_password_hash, verify_password, create_access_token, get_current_active_user

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=201)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Регистрация"""
    # Проверяем email
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Создаём пользователя
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        country=user_data.country,
        city=user_data.city,
        is_active=True,
        is_premium=False,
        average_rating="0.0",
        events_created=0,
        events_attended=0
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

@router.post("/login")
def login_user(credentials: UserLogin, db: Session = Depends(get_db)):
    """Вход"""
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = create_access_token(data={"sub": user.id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "country": user.country,
            "city": user.city,
            "is_active": user.is_active,
            "is_premium": user.is_premium,
            "average_rating": user.average_rating,
            "events_created": user.events_created,
            "events_attended": user.events_attended,
            "created_at": user.created_at.isoformat()
        }
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)):
    """Мой профиль"""
    return current_user

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, db: Session = Depends(get_db)):
    """Получить пользователя"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user