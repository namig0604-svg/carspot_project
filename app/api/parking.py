from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.parking import ParkingSpot
from app.models.user import User
from app.schemas.parking import ParkingSpotOut, ParkingSpotSave

router = APIRouter()


@router.post("", response_model=ParkingSpotOut, summary="Сохранить/обновить место парковки")
def save_parking_spot(
    payload: ParkingSpotSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    spot = db.query(ParkingSpot).filter(ParkingSpot.user_id == current_user.id).first()
    if spot:
        spot.latitude = payload.latitude
        spot.longitude = payload.longitude
        spot.note = payload.note
        spot.photo_url = payload.photo_url
    else:
        spot = ParkingSpot(user_id=current_user.id, **payload.model_dump())
        db.add(spot)
    db.commit()
    db.refresh(spot)
    return spot


@router.get("/mine", response_model=ParkingSpotOut, summary="Моё текущее место парковки")
def my_parking_spot(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    spot = db.query(ParkingSpot).filter(ParkingSpot.user_id == current_user.id).first()
    if not spot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Место парковки не сохранено")
    return spot


@router.delete("/mine", summary="Удалить метку парковки")
def clear_parking_spot(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    db.query(ParkingSpot).filter(ParkingSpot.user_id == current_user.id).delete(synchronize_session=False)
    db.commit()
    return {"message": "Метка удалена"}
