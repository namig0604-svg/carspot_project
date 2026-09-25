import math
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.base import utcnow
from app.models.hazard import RoadHazard, RoadHazardVote
from app.models.user import User
from app.schemas.hazard import HazardCreate, HazardListResponse, HazardOut, HazardVoteIn

router = APIRouter()

# Сколько живёт метка без "постоянного" типа, если её никто не продлевает голосами.
TEMPORARY_TYPES = ("ice", "accident", "police")
TEMPORARY_TTL_HOURS = 6


def _to_out(hazard: RoadHazard, my_vote: str | None) -> HazardOut:
    item = HazardOut.model_validate(hazard)
    item.my_vote = my_vote
    return item


@router.post("", response_model=HazardOut, status_code=status.HTTP_201_CREATED, summary="Отметить дорожную опасность")
def create_hazard(
    payload: HazardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    expires_at = None
    if payload.type in TEMPORARY_TYPES:
        expires_at = utcnow() + timedelta(hours=TEMPORARY_TTL_HOURS)

    hazard = RoadHazard(created_by=current_user.id, expires_at=expires_at, **payload.model_dump())
    db.add(hazard)
    db.commit()
    db.refresh(hazard)
    return _to_out(hazard, None)


@router.get("/nearby", response_model=HazardListResponse, summary="Опасности рядом")
def nearby_hazards(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(15, ge=0.5, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Простое приближение bbox по градусам (достаточно для радиуса в десятки км).
    delta_lat = radius_km / 111.0
    delta_lng = radius_km / (111.0 * max(0.2, abs(math.cos(math.radians(lat)))))

    now = utcnow()
    query = db.query(RoadHazard).filter(
        RoadHazard.latitude.between(lat - delta_lat, lat + delta_lat),
        RoadHazard.longitude.between(lng - delta_lng, lng + delta_lng),
        or_(RoadHazard.expires_at.is_(None), RoadHazard.expires_at > now),
    )
    hazards = query.order_by(RoadHazard.created_at.desc()).limit(200).all()

    my_votes = {}
    if hazards:
        rows = (
            db.query(RoadHazardVote)
            .filter(
                RoadHazardVote.hazard_id.in_([h.id for h in hazards]),
                RoadHazardVote.user_id == current_user.id,
            )
            .all()
        )
        my_votes = {r.hazard_id: r.vote for r in rows}

    return HazardListResponse(items=[_to_out(h, my_votes.get(h.id)) for h in hazards])


@router.post("/{hazard_id}/vote", response_model=HazardOut, summary="Подтвердить или опровергнуть метку")
def vote_hazard(
    hazard_id: str,
    payload: HazardVoteIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    hazard = db.query(RoadHazard).filter(RoadHazard.id == hazard_id).first()
    if not hazard:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Метка не найдена")

    existing = (
        db.query(RoadHazardVote)
        .filter(RoadHazardVote.hazard_id == hazard_id, RoadHazardVote.user_id == current_user.id)
        .first()
    )
    if existing:
        if existing.vote != payload.vote:
            if existing.vote == "confirm":
                hazard.confirms_count = max(0, hazard.confirms_count - 1)
            else:
                hazard.denies_count = max(0, hazard.denies_count - 1)
            existing.vote = payload.vote
            if payload.vote == "confirm":
                hazard.confirms_count += 1
            else:
                hazard.denies_count += 1
    else:
        vote = RoadHazardVote(hazard_id=hazard_id, user_id=current_user.id, vote=payload.vote)
        db.add(vote)
        if payload.vote == "confirm":
            hazard.confirms_count += 1
            if hazard.expires_at:
                hazard.expires_at = utcnow() + timedelta(hours=TEMPORARY_TTL_HOURS)
        else:
            hazard.denies_count += 1

    # Если метку массово опровергли — гасим её сразу.
    if hazard.denies_count >= 3 and hazard.denies_count > hazard.confirms_count:
        hazard.expires_at = utcnow()

    db.commit()
    db.refresh(hazard)
    return _to_out(hazard, payload.vote)
