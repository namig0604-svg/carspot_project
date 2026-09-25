from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.car import Car
from app.models.maintenance import MaintenanceRecord
from app.models.user import User
from app.schemas.maintenance import MaintenanceCreate, MaintenanceListResponse, MaintenanceOut

router = APIRouter()


def _get_own_car_or_404(db: Session, car_id: str, user_id: str) -> Car:
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Машина не найдена")
    if car.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша машина")
    return car


@router.post("", response_model=MaintenanceOut, status_code=status.HTTP_201_CREATED, summary="Добавить запись в сервисный дневник")
def create_record(
    payload: MaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_own_car_or_404(db, payload.car_id, current_user.id)

    record = MaintenanceRecord(user_id=current_user.id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/car/{car_id}", response_model=MaintenanceListResponse, summary="История ТО машины")
def list_for_car(
    car_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_own_car_or_404(db, car_id, current_user.id)

    items = (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.car_id == car_id)
        .order_by(MaintenanceRecord.done_at.desc())
        .all()
    )
    return MaintenanceListResponse(total=len(items), items=items)


@router.delete("/{record_id}", summary="Удалить запись сервисного дневника")
def delete_record(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    record = db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    if record.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    db.delete(record)
    db.commit()
    return {"message": "Запись удалена"}
