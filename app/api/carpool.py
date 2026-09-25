from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.ride_pool import RideBooking, RideOffer
from app.models.user import User
from app.schemas.ride_pool import RideOfferCreate, RideOfferListResponse, RideOfferOut
from app.schemas.user import UserPublic
from app.services import notify, users_by_ids

router = APIRouter()


def _enrich(db: Session, offers: list[RideOffer], current_user_id: str) -> list[RideOfferOut]:
    if not offers:
        return []
    driver_map = users_by_ids(db, [o.driver_id for o in offers])
    bookings = (
        db.query(RideBooking).filter(RideBooking.offer_id.in_([o.id for o in offers])).all()
    )
    by_offer: dict[str, list[str]] = {}
    for b in bookings:
        by_offer.setdefault(b.offer_id, []).append(b.passenger_id)

    all_passenger_ids = {pid for ids in by_offer.values() for pid in ids}
    passenger_map = users_by_ids(db, list(all_passenger_ids)) if all_passenger_ids else {}

    items = []
    for offer in offers:
        item = RideOfferOut.model_validate(offer)
        driver = driver_map.get(offer.driver_id)
        if driver:
            item.driver = UserPublic.model_validate(driver)
        passenger_ids = by_offer.get(offer.id, [])
        item.seats_taken = len(passenger_ids)
        item.passengers = [
            UserPublic.model_validate(passenger_map[pid]) for pid in passenger_ids if pid in passenger_map
        ]
        item.i_booked = current_user_id in passenger_ids
        items.append(item)
    return items


@router.post("", response_model=RideOfferOut, status_code=status.HTTP_201_CREATED, summary="Предложить место в машине")
def create_offer(
    payload: RideOfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    offer = RideOffer(driver_id=current_user.id, **payload.model_dump())
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return _enrich(db, [offer], current_user.id)[0]


@router.get("/event/{event_id}", response_model=RideOfferListResponse, summary="Попутчики на мероприятие")
def list_for_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    offers = (
        db.query(RideOffer)
        .filter(RideOffer.event_id == event_id)
        .order_by(RideOffer.created_at.desc())
        .all()
    )
    return RideOfferListResponse(items=_enrich(db, offers, current_user.id))


@router.post("/{offer_id}/book", response_model=RideOfferOut, summary="Забронировать место")
def book_seat(
    offer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    offer = db.query(RideOffer).filter(RideOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Предложение не найдено")
    if offer.driver_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя забронировать место у себя же")

    existing = (
        db.query(RideBooking)
        .filter(RideBooking.offer_id == offer_id, RideBooking.passenger_id == current_user.id)
        .first()
    )
    if existing:
        return _enrich(db, [offer], current_user.id)[0]

    taken = db.query(RideBooking).filter(RideBooking.offer_id == offer_id).count()
    if taken >= offer.seats_total:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Свободных мест нет")

    booking = RideBooking(offer_id=offer_id, passenger_id=current_user.id)
    db.add(booking)
    db.commit()

    notify(
        db,
        user_id=offer.driver_id,
        actor_id=current_user.id,
        type="ride_booked",
        target_type="event",
        target_id=offer.event_id,
        message=f"{current_user.username} забронировал(а) место в вашей поездке",
    )

    db.refresh(offer)
    return _enrich(db, [offer], current_user.id)[0]


@router.delete("/{offer_id}/book", summary="Отменить своё бронирование места")
def cancel_booking(
    offer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    db.query(RideBooking).filter(
        RideBooking.offer_id == offer_id, RideBooking.passenger_id == current_user.id
    ).delete(synchronize_session=False)
    db.commit()
    return {"message": "Бронирование отменено"}


@router.delete("/{offer_id}", summary="Удалить своё предложение")
def delete_offer(
    offer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    offer = db.query(RideOffer).filter(RideOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Предложение не найдено")
    if offer.driver_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    db.query(RideBooking).filter(RideBooking.offer_id == offer_id).delete(synchronize_session=False)
    db.delete(offer)
    db.commit()
    return {"message": "Удалено"}
