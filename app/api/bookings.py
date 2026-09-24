"""
Онлайн-запись в автосервис/ателье: клиент выбирает услугу и время,
владелец заведения подтверждает или отклоняет заявку.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.models.base import utcnow
from app.models.booking import BOOKING_STATUSES, BusinessBooking
from app.models.business import Business
from app.models.user import User
from app.schemas.booking import (
    BookingCreate,
    BookingListResponse,
    BookingOut,
    BookingStatusUpdate,
    BusinessBrief,
)
from app.schemas.user import UserPublic
from app.services import notify, users_by_ids

router = APIRouter()


def _get_booking_or_404(db: Session, booking_id: str) -> BusinessBooking:
    booking = db.query(BusinessBooking).filter(BusinessBooking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return booking


def _get_business_or_404(db: Session, business_id: str) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Заведение не найдено")
    return business


def _enrich(db: Session, bookings: List[BusinessBooking]) -> List[BookingOut]:
    if not bookings:
        return []
    user_map = users_by_ids(db, [b.user_id for b in bookings])
    business_map = {
        b.id: b
        for b in db.query(Business).filter(Business.id.in_({b.business_id for b in bookings})).all()
    }
    items = []
    for booking in bookings:
        out = BookingOut.model_validate(booking)
        user = user_map.get(booking.user_id)
        if user:
            out.user = UserPublic.model_validate(user)
        business = business_map.get(booking.business_id)
        if business:
            out.business = BusinessBrief.model_validate(business)
        items.append(out)
    return items


@router.post(
    "/business/{business_id}",
    response_model=BookingOut,
    status_code=201,
    summary="Записаться в автосервис/ателье",
)
def create_booking(
    business_id: str,
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    business = _get_business_or_404(db, business_id)
    if not business.is_active:
        raise HTTPException(status_code=400, detail="Заведение сейчас недоступно для записи")

    booking = BusinessBooking(
        business_id=business_id,
        user_id=current_user.id,
        service=payload.service,
        requested_at=payload.requested_at,
        note=payload.note,
    )
    db.add(booking)
    db.flush()

    if business.owner_id:
        when = payload.requested_at.strftime("%d.%m %H:%M")
        service_part = f" на «{payload.service}»" if payload.service else ""
        notify(
            db,
            user_id=business.owner_id,
            type="booking_request",
            actor_id=current_user.id,
            target_type="business",
            target_id=business.id,
            message=f"{current_user.username} хочет записаться{service_part} {when} в {business.name}",
        )

    db.commit()
    db.refresh(booking)
    return _enrich(db, [booking])[0]


@router.get("/mine", response_model=BookingListResponse, summary="Мои записи (как клиента)")
def list_my_bookings(
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if status is not None and status not in BOOKING_STATUSES:
        raise HTTPException(status_code=400, detail="Некорректный статус")

    query = db.query(BusinessBooking).filter(BusinessBooking.user_id == current_user.id)
    if status:
        query = query.filter(BusinessBooking.status == status)
    total = query.count()
    rows = (
        query.order_by(BusinessBooking.requested_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    return BookingListResponse(total=total, limit=page.limit, offset=page.offset, items=_enrich(db, rows))


@router.get(
    "/business/{business_id}",
    response_model=BookingListResponse,
    summary="Заявки на запись к заведению (только владелец)",
)
def list_business_bookings(
    business_id: str,
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    business = _get_business_or_404(db, business_id)
    if business.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Только владелец заведения видит его заявки")
    if status is not None and status not in BOOKING_STATUSES:
        raise HTTPException(status_code=400, detail="Некорректный статус")

    query = db.query(BusinessBooking).filter(BusinessBooking.business_id == business_id)
    if status:
        query = query.filter(BusinessBooking.status == status)
    total = query.count()
    rows = (
        query.order_by(BusinessBooking.requested_at.asc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    return BookingListResponse(total=total, limit=page.limit, offset=page.offset, items=_enrich(db, rows))


@router.post("/{booking_id}/status", response_model=BookingOut, summary="Изменить статус записи")
def update_booking_status(
    booking_id: str,
    payload: BookingStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    booking = _get_booking_or_404(db, booking_id)
    business = _get_business_or_404(db, booking.business_id)

    is_owner = business.owner_id == current_user.id or current_user.is_admin
    is_client = booking.user_id == current_user.id

    if payload.status in ("confirmed", "declined", "completed"):
        if not is_owner:
            raise HTTPException(status_code=403, detail="Подтверждать или отклонять записи может только владелец заведения")
    elif payload.status == "cancelled":
        if not (is_client or is_owner):
            raise HTTPException(status_code=403, detail="Отменить запись может только клиент или владелец заведения")
    else:
        raise HTTPException(status_code=400, detail="Недопустимый переход статуса")

    booking.status = payload.status
    if payload.status == "declined":
        booking.decline_reason = payload.decline_reason
    booking.updated_at = utcnow()

    if payload.status in ("confirmed", "declined"):
        when = booking.requested_at.strftime("%d.%m %H:%M")
        message = (
            f"Ваша запись в {business.name} на {when} подтверждена"
            if payload.status == "confirmed"
            else f"Ваша запись в {business.name} на {when} отклонена"
            + (f": {payload.decline_reason}" if payload.decline_reason else "")
        )
        notify(
            db,
            user_id=booking.user_id,
            type=f"booking_{payload.status}",
            actor_id=current_user.id,
            target_type="business",
            target_id=business.id,
            message=message,
        )

    db.commit()
    db.refresh(booking)
    return _enrich(db, [booking])[0]
