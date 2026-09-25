from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.models.part_listing import PartListing
from app.models.user import User
from app.schemas.part_listing import (
    PartListingCreate,
    PartListingListResponse,
    PartListingOut,
    PartListingStatusUpdate,
)
from app.schemas.user import UserPublic
from app.services import users_by_ids

router = APIRouter()


def _get_listing_or_404(db: Session, listing_id: str) -> PartListing:
    listing = db.query(PartListing).filter(PartListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объявление не найдено")
    return listing


def _enrich(db: Session, listings: list[PartListing]) -> list[PartListingOut]:
    user_map = users_by_ids(db, [l.seller_id for l in listings])
    items = []
    for listing in listings:
        item = PartListingOut.model_validate(listing)
        seller = user_map.get(listing.seller_id)
        if seller:
            item.seller = UserPublic.model_validate(seller)
        items.append(item)
    return items


@router.post("", response_model=PartListingOut, status_code=status.HTTP_201_CREATED, summary="Создать объявление")
def create_listing(
    payload: PartListingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    listing = PartListing(seller_id=current_user.id, **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return _enrich(db, [listing])[0]


@router.get("", response_model=PartListingListResponse, summary="Список объявлений")
def list_listings(
    category: str | None = Query(None),
    car_brand: str | None = Query(None),
    q: str | None = Query(None, description="Поиск по названию"),
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    query = db.query(PartListing).filter(PartListing.status == "active")
    if category:
        query = query.filter(PartListing.category == category)
    if car_brand:
        query = query.filter(PartListing.car_brand == car_brand)
    if q:
        query = query.filter(PartListing.title.ilike(f"%{q}%"))

    total = query.count()
    listings = (
        query.order_by(PartListing.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    return PartListingListResponse(total=total, limit=page.limit, offset=page.offset, items=_enrich(db, listings))


@router.get("/mine", response_model=PartListingListResponse, summary="Мои объявления")
def my_listings(
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(PartListing).filter(PartListing.seller_id == current_user.id)
    total = query.count()
    listings = (
        query.order_by(PartListing.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    return PartListingListResponse(total=total, limit=page.limit, offset=page.offset, items=_enrich(db, listings))


@router.get("/{listing_id}", response_model=PartListingOut, summary="Детали объявления")
def get_listing(
    listing_id: str,
    db: Session = Depends(get_db),
):
    listing = _get_listing_or_404(db, listing_id)
    return _enrich(db, [listing])[0]


@router.post("/{listing_id}/status", response_model=PartListingOut, summary="Изменить статус объявления")
def update_status(
    listing_id: str,
    payload: PartListingStatusUpdate,
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
