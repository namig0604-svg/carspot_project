from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.car import Car
from app.models.car_document import CarDocument
from app.models.user import User
from app.schemas.car_document import CarDocumentCreate, CarDocumentListResponse, CarDocumentOut

router = APIRouter()


def _get_own_car_or_404(db: Session, car_id: str, user_id: str) -> Car:
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Машина не найдена")
    if car.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша машина")
    return car


@router.post("", response_model=CarDocumentOut, status_code=status.HTTP_201_CREATED, summary="Добавить документ")
def create_document(
    payload: CarDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_own_car_or_404(db, payload.car_id, current_user.id)

    doc = CarDocument(user_id=current_user.id, **payload.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/car/{car_id}", response_model=CarDocumentListResponse, summary="Документы машины")
def list_for_car(
    car_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_own_car_or_404(db, car_id, current_user.id)

    items = (
        db.query(CarDocument)
        .filter(CarDocument.car_id == car_id)
        .order_by(CarDocument.expires_at.asc().nullslast())
        .all()
    )
    return CarDocumentListResponse(total=len(items), items=items)


@router.delete("/{document_id}", summary="Удалить документ")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    doc = db.query(CarDocument).filter(CarDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")
    if doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    db.delete(doc)
    db.commit()
    return {"message": "Документ удалён"}
