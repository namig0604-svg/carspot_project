"""Витрина «Машина на продажу» — объявления о продаже машин между пользователями."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.models.car_listing import CarListing
from app.models.user import User
from app.schemas.car_listing import (
    CarListingCreate,
    CarListingListResponse,
    CarListingOut,
    CarListingStatusUpdate,
)
from app.schemas.user import UserPublic
from app.services import users_by_ids

router = APIRouter()


def _get_listing_or_404(db: Session, listing_id: str) -> CarListing:
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объявление не найдено")
    return listing


def _enrich(db: Session, listings: list[CarListing]) -> list[CarListingOut]:
    user_map = users_by_ids(db, [l.seller_id for l in listings])
    items = []
    for listing in listings:
        item = CarListingOut.model_validate(listing)
        seller = user_map.get(listing.seller_id)
        if seller:
            item.seller = UserPublic.model_validate(seller)
        items.append(item)
    return items


@router.post("", response_model=CarListingOut, status_code=status.HTTP_201_CREATED, summary="Создать объявление о продаже машины")
def create_listing(
    payload: CarListingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    listing = CarListing(seller_id=current_user.id, **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return _enrich(db, [listing])[0]


@router.get("", response_model=CarListingListResponse, summary="Список объявлений")
def list_listings(
    make: str | None = Query(None),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_year: int | None = Query(None, ge=1900),
    city: str | None = Query(None),
    q: str | None = Query(None, description="Поиск по марке/модели"),
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    query = db.query(CarListing).filter(CarListing.status == "active")
    if make:
        query = query.filter(CarListing.make.ilike(make))
    if min_price is not None:
        query = query.filter(CarListing.price >= min_price)
    if max_price is not None:
        query = query.filter(CarListing.price <= max_price)
    if min_year is not None:
        query = query.filter(CarListing.year >= min_year)
    if city:
        query = query.filter(CarListing.city.ilike(city))
    if q:
        like = f"%{q}%"
        query = query.filter((CarListing.make.ilike(like)) | (CarListing.model.ilike(like)))

    total = query.count()
    listings = (
        query.order_by(CarListing.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    return CarListingListResponse(total=total, limit=page.limit, offset=page.offset, items=_enrich(db, listings))


@router.get("/mine", response_model=CarListingListResponse, summary="Мои объявления")
def my_listings(
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(CarListing).filter(CarListing.seller_id == current_user.id)
    total = query.count()
    listings = (
        query.order_by(CarListing.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    return CarListingListResponse(total=total, limit=page.limit, offset=page.offset, items=_enrich(db, listings))


@router.get("/{listing_id}", response_model=CarListingOut, summary="Детали объявления")
def get_listing(
    listing_id: str,
    db: Session = Depends(get_db),
):
    listing = _get_listing_or_404(db, listing_id)
    return _enrich(db, [listing])[0]


@router.post("/{listing_id}/status", response_model=CarListingOut, summary="Изменить статус объявления")
def update_status(
    listing_id: str,
    payload: CarListingStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    listing = _get_listing_or_404(db, listing_id)
    if listing.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваше объявление")
    listing.status = payload.status
    db.commit()
    db.refresh(listing)
    return _enrich(db, [listing])[0]


@router.delete("/{listing_id}", summary="Удалить объявление")
def delete_listing(
    listing_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    listing = _get_listing_or_404(db, listing_id)
    if listing.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваше объявление")
    db.delete(listing)
    db.commit()
    return {"message": "Объявление удалено"}
