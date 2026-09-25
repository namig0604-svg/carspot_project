"""
Автосервисы и тюнинг-ателье: каталог, карта, отзывы, избранное.
"""
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app import premium_tiers
from app.config import settings
from app.database import get_db
from app.deps import Pagination, get_current_active_user, get_optional_user
from app.models.base import utcnow
from app.models.business import Business, BusinessFavorite, BusinessReview
from app.models.user import User
from app.schemas.business import (
    BusinessCreate,
    BusinessDetail,
    BusinessListResponse,
    BusinessMapMarker,
    BusinessOut,
    BusinessReviewCreate,
    BusinessReviewListResponse,
    BusinessReviewOut,
    BusinessUpdate,
)
from app.schemas.user import UserPublic
from app.services import InsufficientCoinsError, recalc_business_rating, spend_coins, users_by_ids
from app.utils.geo import bounding_box, haversine_km

router = APIRouter()


def _recommended_score(
    item, latitude: float, longitude: float, item_lat, item_lon, boosted_until
) -> float:
    """Смешивает близость и рейтинг в одно число (больше — выше в списке).

    proximity: 1.0 рядом (0 км) → 0.0 далеко (250+ км), убывает плавно.
    rating: 0.0..1.0 от average_rating (шкала 0..5).
    Бустнутые Premium-записи получают крупный бонус, чтобы остаться в топе,
    как и при обычных сортировках каталога.
    """
    if item_lat is None or item_lon is None:
        proximity = 0.0  # неизвестные координаты — не выигрывают за близость
    else:
        distance = haversine_km(latitude, longitude, item_lat, item_lon)
        proximity = max(0.0, 1.0 - min(distance, 250.0) / 250.0)

    rating = max(0.0, min(5.0, item.average_rating or 0.0)) / 5.0
    score = 0.6 * proximity + 0.4 * rating

    if boosted_until and boosted_until > utcnow():
        score += 10.0  # бустнутые всегда выше не бустнутых

    return score


def _rank_by_recommended(candidates: list, latitude: float, longitude: float) -> list:
    scored = [
        (
            _recommended_score(c, latitude, longitude, c.latitude, c.longitude, c.boosted_until),
            c,
        )
        for c in candidates
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [c for _score, c in scored]


def _get_business_or_404(db: Session, business_id: str) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Заведение не найдено")
    return business


def _require_owner(business: Business, user: User) -> None:
    if business.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Только владелец может изменить это заведение")


def _favorite_ids(db: Session, user: Optional[User], business_ids: List[str]) -> set:
    if not user or not business_ids:
        return set()
    return {
        row[0]
        for row in db.query(BusinessFavorite.business_id)
        .filter(
            BusinessFavorite.user_id == user.id,
            BusinessFavorite.business_id.in_(business_ids),
        )
        .all()
    }


@router.post(
    "/",
    response_model=BusinessDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить автосервис/ателье",
)
def create_business(
    payload: BusinessCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not premium_tiers.can_create_business(current_user) and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Добавлять автосервисы и ателье могут только подписчики CarSpot Premium",
        )

    if not current_user.is_admin:
        max_businesses = premium_tiers.max_businesses(current_user)
        existing_count = db.query(Business).filter(Business.owner_id == current_user.id).count()
        if existing_count >= max_businesses:
            raise HTTPException(
                status_code=400,
                detail=f"На вашем уровне Premium можно добавить максимум {max_businesses} заведений",
            )

    business = Business(owner_id=current_user.id, **payload.model_dump())
    db.add(business)
    db.commit()
    db.refresh(business)

    detail = BusinessDetail.model_validate(business)
    detail.owner = UserPublic.model_validate(current_user)
    return detail


@router.get("/", response_model=BusinessListResponse, summary="Каталог автосервисов и ателье")
def list_businesses(
    q: Optional[str] = Query(None, description="Поиск по названию/описанию/услугам"),
    category: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    sort: str = Query("recommended", description="recommended | rating | new | reviews | name"),
    latitude: Optional[float] = Query(None, ge=-90, le=90, description="Широта пользователя (для sort=recommended)"),
    longitude: Optional[float] = Query(None, ge=-180, le=180, description="Долгота пользователя (для sort=recommended)"),
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    query = db.query(Business).filter(Business.is_active.is_(True))

    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Business.name.ilike(pattern),
                Business.description.ilike(pattern),
                Business.services.ilike(pattern),
            )
        )
    if category:
        query = query.filter(Business.category == category)
    if country:
        query = query.filter(func.lower(Business.country) == country.lower())
    if city:
        query = query.filter(func.lower(Business.city) == city.lower())

    total = query.count()

    # Бустнутые Premium-заведения всегда всплывают в топ каталога на BOOST_DURATION_HOURS часов.
    boosted_rank = case((Business.boosted_until > utcnow(), 0), else_=1)

    if sort == "recommended" and latitude is not None and longitude is not None:
        # "Рекомендовано": ближе и с лучшим рейтингом — выше. Бустнутые всё равно
        # в топе. Считаем расстояние в Python (без PostGIS) на ограниченном
        # наборе кандидатов — так же, как /nearby у сходок.
        candidates = query.order_by(boosted_rank, Business.average_rating.desc()).limit(1000).all()
        out_items = _rank_by_recommended(candidates, latitude, longitude)
        items = out_items[page.offset : page.offset + page.limit]
    else:
        if sort == "new":
            query = query.order_by(boosted_rank, Business.created_at.desc())
        elif sort == "reviews":
            query = query.order_by(boosted_rank, Business.reviews_count.desc(), Business.average_rating.desc())
        elif sort == "name":
            query = query.order_by(boosted_rank, Business.name.asc())
        else:
            query = query.order_by(boosted_rank, Business.average_rating.desc(), Business.reviews_count.desc())
        items = query.offset(page.offset).limit(page.limit).all()

    favorite_ids = _favorite_ids(db, current_user, [b.id for b in items])

    out_items = []
    for b in items:
        item = BusinessOut.model_validate(b)
        item.is_favorite = b.id in favorite_ids
        out_items.append(item)

    return BusinessListResponse(total=total, limit=page.limit, offset=page.offset, items=out_items)


@router.get(
    "/my/favorites",
    response_model=List[BusinessOut],
    summary="Мои избранные заведения",
)
def my_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    business_ids = [
        row[0]
        for row in db.query(BusinessFavorite.business_id)
        .filter(BusinessFavorite.user_id == current_user.id)
        .all()
    ]
    if not business_ids:
        return []

    businesses = (
        db.query(Business)
        .filter(Business.id.in_(business_ids), Business.is_active.is_(True))
        .order_by(Business.average_rating.desc())
        .all()
    )
    result = []
    for b in businesses:
        item = BusinessOut.model_validate(b)
        item.is_favorite = True
        result.append(item)
    return result


@router.get(
    "/my/added",
    response_model=List[BusinessOut],
    summary="Заведения, которые я добавил",
)
def my_added_businesses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    businesses = (
        db.query(Business)
        .filter(Business.owner_id == current_user.id)
        .order_by(Business.created_at.desc())
        .all()
    )
    favorite_ids = _favorite_ids(db, current_user, [b.id for b in businesses])
    result = []
    for b in businesses:
        item = BusinessOut.model_validate(b)
        item.is_favorite = b.id in favorite_ids
        result.append(item)
    return result


@router.get(
    "/map",
    response_model=List[BusinessMapMarker],
    summary="Метки заведений для карты в видимой области",
)
def businesses_for_map(
    min_lat: float = Query(..., ge=-90, le=90),
    max_lat: float = Query(..., ge=-90, le=90),
    min_lon: float = Query(..., ge=-180, le=180),
    max_lon: float = Query(..., ge=-180, le=180),
    category: Optional[str] = None,
    limit: int = Query(300, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(Business).filter(
        Business.is_active.is_(True),
        Business.latitude.isnot(None),
        Business.longitude.isnot(None),
        Business.latitude.between(min(min_lat, max_lat), max(min_lat, max_lat)),
        Business.longitude.between(min(min_lon, max_lon), max(min_lon, max_lon)),
    )
    if category:
        query = query.filter(Business.category == category)

    items = query.order_by(Business.average_rating.desc()).limit(limit).all()
    return [BusinessMapMarker.model_validate(b) for b in items]


@router.get(
    "/nearby",
    response_model=List[BusinessMapMarker],
    summary="Автосервисы и ателье рядом со мной",
)
def businesses_nearby(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(None, ge=0.1, le=2000),
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    radius = radius_km or settings.DEFAULT_SEARCH_RADIUS_KM
    min_lat, max_lat, min_lon, max_lon = bounding_box(latitude, longitude, radius)

    query = db.query(Business).filter(
        Business.is_active.is_(True),
        Business.latitude.isnot(None),
        Business.longitude.isnot(None),
        Business.latitude.between(min_lat, max_lat),
        Business.longitude.between(min_lon, max_lon),
    )
    if category:
        query = query.filter(Business.category == category)

    candidates = query.limit(2000).all()

    result = []
    for business in candidates:
        distance = haversine_km(latitude, longitude, business.latitude, business.longitude)
        if distance <= radius:
            marker = BusinessMapMarker.model_validate(business)
            marker.distance_km = round(distance, 2)
            result.append(marker)

    result.sort(key=lambda m: m.distance_km or 0)
    return result[:limit]


@router.get("/{business_id}", response_model=BusinessDetail, summary="Карточка заведения")
def get_business(
    business_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    business = _get_business_or_404(db, business_id)

    business.views_count = (business.views_count or 0) + 1
    db.commit()
    db.refresh(business)

    detail = BusinessDetail.model_validate(business)

    owner = db.query(User).filter(User.id == business.owner_id).first() if business.owner_id else None
    if owner:
        detail.owner = UserPublic.model_validate(owner)

    if current_user:
        detail.is_favorite = business.id in _favorite_ids(db, current_user, [business.id])
        my_review = (
            db.query(BusinessReview)
            .filter(BusinessReview.business_id == business.id, BusinessReview.user_id == current_user.id)
            .first()
        )
        detail.my_rating = my_review.rating if my_review else None

    return detail


@router.patch("/{business_id}", response_model=BusinessOut, summary="Изменить заведение")
def update_business(
    business_id: str,
    payload: BusinessUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(business, field, value)

    db.commit()
    db.refresh(business)
    return business


@router.post(
    "/{business_id}/boost",
    response_model=BusinessOut,
    summary=f"Поднять заведение в топ каталога на {settings.BOOST_DURATION_HOURS} ч. (Premium)",
)
def boost_business(
    business_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)
    if not premium_tiers.gets_free_boost(current_user) and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Бесплатно поднимать заведение в топ каталога могут только подписчики CarSpot Pro",
        )

    now = utcnow()
    if business.boosted_until and business.boosted_until > now:
        raise HTTPException(
            status_code=400,
            detail=f"Буст уже активен до {business.boosted_until.isoformat()}",
        )

    business.boosted_until = now + timedelta(hours=premium_tiers.boost_duration_hours(current_user))
    db.commit()
    db.refresh(business)
    return business


@router.post(
    "/{business_id}/boost-with-coins",
    response_model=BusinessOut,
    summary=f"Поднять заведение в топ каталога на {settings.BOOST_DURATION_HOURS} ч. за {settings.COIN_BOOST_COST_BUSINESS} монет",
)
def boost_business_with_coins(
    business_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Тот же буст, что и /boost, но платный — монетами CarSpot Coins вместо
    Premium, доступен любому владельцу заведения."""
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)

    now = utcnow()
    if business.boosted_until and business.boosted_until > now:
        raise HTTPException(
            status_code=400,
            detail=f"Буст уже активен до {business.boosted_until.isoformat()}",
        )

    try:
        spend_coins(db, current_user, settings.COIN_BOOST_COST_BUSINESS, "boost_business", reference_id=business.id)
    except InsufficientCoinsError as e:
        raise HTTPException(status_code=402, detail=str(e))

    business.boosted_until = now + timedelta(hours=settings.BOOST_DURATION_HOURS)
    db.commit()
    db.refresh(business)
    return business


@router.delete("/{business_id}", summary="Удалить заведение")
def delete_business(
    business_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)

    db.query(BusinessReview).filter(BusinessReview.business_id == business_id).delete(
        synchronize_session=False
    )
    db.query(BusinessFavorite).filter(BusinessFavorite.business_id == business_id).delete(
        synchronize_session=False
    )
    db.delete(business)
    db.commit()
    return {"message": "Заведение удалено", "business_id": business_id}


# ─────────────────────────── ИЗБРАННОЕ ───────────────────────────

@router.post("/{business_id}/favorite", summary="Добавить в избранное")
def add_favorite(
    business_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_business_or_404(db, business_id)

    exists = (
        db.query(BusinessFavorite)
        .filter(BusinessFavorite.business_id == business_id, BusinessFavorite.user_id == current_user.id)
        .first()
    )
    if not exists:
        db.add(BusinessFavorite(business_id=business_id, user_id=current_user.id))
        db.commit()
    return {"message": "Добавлено в избранное", "is_favorite": True}


@router.delete("/{business_id}/favorite", summary="Убрать из избранного")
def remove_favorite(
    business_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    db.query(BusinessFavorite).filter(
        BusinessFavorite.business_id == business_id, BusinessFavorite.user_id == current_user.id
    ).delete(synchronize_session=False)
    db.commit()
    return {"message": "Убрано из избранного", "is_favorite": False}


# ─────────────────────────── ОТЗЫВЫ ───────────────────────────

@router.get(
    "/{business_id}/reviews",
    response_model=BusinessReviewListResponse,
    summary="Отзывы о заведении",
)
def list_reviews(
    business_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    _get_business_or_404(db, business_id)

    query = db.query(BusinessReview).filter(BusinessReview.business_id == business_id)
    total = query.count()
    reviews = (
        query.order_by(BusinessReview.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )

    user_map = users_by_ids(db, [r.user_id for r in reviews])
    items = []
    for r in reviews:
        item = BusinessReviewOut.model_validate(r)
        user = user_map.get(r.user_id)
        if user:
            item.user = UserPublic.model_validate(user)
        items.append(item)

    return BusinessReviewListResponse(total=total, limit=page.limit, offset=page.offset, items=items)


@router.post(
    "/{business_id}/reviews",
    response_model=BusinessReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Оставить/обновить отзыв",
)
def create_or_update_review(
    business_id: str,
    payload: BusinessReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    business = _get_business_or_404(db, business_id)

    review = (
        db.query(BusinessReview)
        .filter(BusinessReview.business_id == business_id, BusinessReview.user_id == current_user.id)
        .first()
    )

    if review:
        for field, value in payload.model_dump().items():
            setattr(review, field, value)
    else:
        review = BusinessReview(business_id=business_id, user_id=current_user.id, **payload.model_dump())
        db.add(review)

    db.flush()
    recalc_business_rating(db, business_id)
    db.commit()
    db.refresh(review)

    item = BusinessReviewOut.model_validate(review)
    item.user = UserPublic.model_validate(current_user)
    return item


@router.delete("/{business_id}/reviews/me", summary="Удалить свой отзыв")
def delete_my_review(
    business_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    review = (
        db.query(BusinessReview)
        .filter(BusinessReview.business_id == business_id, BusinessReview.user_id == current_user.id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")

    db.delete(review)
    db.flush()
    recalc_business_rating(db, business_id)
    db.commit()
    return {"message": "Отзыв удалён"}
