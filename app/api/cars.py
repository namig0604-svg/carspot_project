"""
Мой Гараж — автомобили пользователя.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.car import Car
from app.models.user import User
from app.schemas.car import CarCreate, CarOut, CarUpdate, GarageOut
from app.deps import get_current_active_user

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
    existing_count = db.query(Car).filter(Car.user_id == current_user.id).count()
    if existing_count >= settings.MAX_CARS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Максимум {settings.MAX_CARS_PER_USER} машин в гараже",
        )

    car = Car(user_id=current_user.id, **payload.model_dump())

    # Первая машина автоматически становится основной
    if existing_count == 0:
        car.is_primary = True

    db.add(car)
    db.flush()

    if car.is_primary:
        _clear_other_primary(db, current_user.id, car.id)

    _refresh_cars_count(db, current_user.id)
    db.commit()
    db.refresh(car)
    return car


@router.get("/{car_id}", response_model=CarOut, summary="Карточка машины")
def get_car(car_id: str, db: Session = Depends(get_db)):
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    return car


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
