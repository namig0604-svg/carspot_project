"""
Мой Гараж — автомобили пользователя.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.car import Car, CarLike
from app.models.user import User
from app.schemas.car import CarCreate, CarOut, CarUpdate, GarageOut
from app.schemas.user import UserPublic
from app.deps import get_current_active_user, get_optional_user
from app.services import award_xp

router = APIRouter()


def _refresh_cars_count(db: Session, user_id: str) -> None:
    count = db.query(Car).filter(Car.user_id == user_id).count()
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.cars_count = count


def _clear_other_primary(db: Session, user_id: str, keep_car_id: str) -> None:
    """Основная машина может быть только одна."""
    db.query(Car).filter(
        Car.user_id == user_id,
        Car.id != keep_car_id,
        Car.is_primary.is_(True),
    ).update({Car.is_primary: False}, synchronize_session=False)


@router.get("/my", response_model=GarageOut, summary="Мой гараж")
def my_garage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    cars = (
        db.query(Car)
        .filter(Car.user_id == current_user.id)
        .order_by(Car.is_primary.desc(), Car.created_at.desc())
        .all()
    )
    return GarageOut(
        user_id=current_user.id,
        username=current_user.username,
        cars_count=len(cars),
        cars=[CarOut.model_validate(c) for c in cars],
    )


@router.post(
    "/",
    response_model=CarOut,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить машину в гараж",
)
def create_car(
    payload: CarCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    max_cars = settings.PREMIUM_MAX_CARS_PER_USER if current_user.is_premium else settings.MAX_CARS_PER_USER
    existing_count = db.query(Car).filter(Car.user_id == current_user.id).count()
    if existing_count >= max_cars:
        detail = f"Максимум {max_cars} машин в гараже"
        if not current_user.is_premium:
            detail += f". С CarSpot Premium — до {settings.PREMIUM_MAX_CARS_PER_USER}"
        raise HTTPException(status_code=400, detail=detail)

    car = Car(user_id=current_user.id, **payload.model_dump())

    # Первая машина автоматически становится основной
    if existing_count == 0:
        car.is_primary = True

    db.add(car)
    db.flush()

    if car.is_primary:
        _clear_other_primary(db, current_user.id, car.id)

    _refresh_cars_count(db, current_user.id)
    award_xp(db, current_user, 20, "car_add")
    db.commit()
    db.refresh(car)
    return car


@router.get("/{car_id}", response_model=CarOut, summary="Карточка машины")
def get_car(
    car_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Машина не найдена")

    out = CarOut.model_validate(car)
    if current_user:
        out.is_liked = (
            db.query(CarLike.id)
            .filter(CarLike.car_id == car_id, CarLike.user_id == current_user.id)
            .first()
            is not None
        )
    return out


@router.post("/{car_id}/like", summary="Лайк / снять лайк с машины")
def toggle_car_like(
    car_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    if car.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя лайкнуть свою машину")

    existing = (
        db.query(CarLike)
        .filter(CarLike.car_id == car_id, CarLike.user_id == current_user.id)
        .first()
    )

    if existing:
        db.delete(existing)
        car.likes_count = max(0, (car.likes_count or 1) - 1)
        liked = False
    else:
        db.add(CarLike(car_id=car_id, user_id=current_user.id))
        car.likes_count = (car.likes_count or 0) + 1
        liked = True

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        car = db.query(Car).filter(Car.id == car_id).first()
        return {"liked": True, "likes_count": car.likes_count if car else 0}

    db.refresh(car)
    return {"liked": liked, "likes_count": car.likes_count}


@router.get(
    "/{car_id}/likers",
    response_model=List[UserPublic],
    summary="Кто лайкнул машину (Premium)",
)
def car_likers(
    car_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    if car.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Это не ваша машина")
    if not current_user.is_premium and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Список тех, кто лайкнул машину, доступен только с CarSpot Premium",
        )

    liker_ids = [
        row[0]
        for row in db.query(CarLike.user_id)
        .filter(CarLike.car_id == car_id)
        .order_by(CarLike.created_at.desc())
        .limit(settings.PREMIUM_INSIGHTS_LIMIT)
        .all()
    ]
    if not liker_ids:
        return []

    users_by_id = {u.id: u for u in db.query(User).filter(User.id.in_(liker_ids)).all()}
    return [UserPublic.model_validate(users_by_id[uid]) for uid in liker_ids if uid in users_by_id]


@router.patch("/{car_id}", response_model=CarOut, summary="Изменить машину")
def update_car(
    car_id: str,
    payload: CarUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    if car.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваша машина")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(car, field, value)

    if car.is_primary:
        _clear_other_primary(db, current_user.id, car.id)

    db.commit()
    db.refresh(car)
    return car


@router.post("/{car_id}/primary", response_model=CarOut, summary="Сделать основной")
def set_primary(
    car_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    if car.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваша машина")

    car.is_primary = True
    _clear_other_primary(db, current_user.id, car.id)
    db.commit()
    db.refresh(car)
    return car


@router.delete("/{car_id}", summary="Удалить машину")
def delete_car(
    car_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    if car.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваша машина")

    was_primary = car.is_primary
    db.delete(car)
    db.flush()

    # Если удалили основную — назначаем основной следующую
    if was_primary:
        next_car = (
            db.query(Car)
            .filter(Car.user_id == current_user.id)
            .order_by(Car.created_at.desc())
            .first()
        )
        if next_car:
            next_car.is_primary = True

    _refresh_cars_count(db, current_user.id)
    db.commit()
    return {"message": "Машина удалена", "car_id": car_id}
