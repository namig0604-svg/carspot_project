from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.event import Event
from app.models.rating import EventRating, SpotRating, UserRating
from app.schemas.rating import (
    EventRatingCreate, EventRatingResponse,
    SpotRatingCreate, SpotRatingResponse,
    UserRatingCreate, UserRatingResponse
)
from app.utils.auth import get_current_active_user

router = APIRouter(prefix="/api/ratings", tags=["ratings"])

# Event Ratings
@router.post("/events", response_model=EventRatingResponse)
async def create_event_rating(
    rating_data: EventRatingCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Rate an event"""
    
    # Check event exists
    event = db.query(Event).filter(Event.id == rating_data.event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    # Check if already rated
    existing_rating = db.query(EventRating).filter(
        EventRating.event_id == rating_data.event_id,
        EventRating.user_id == current_user.id
    ).first()
    
    if existing_rating:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already rated this event")
    
    # Create rating
    new_rating = EventRating(
        event_id=rating_data.event_id,
        user_id=current_user.id,
        rating=rating_data.rating,
        review=rating_data.review,
        atmosphere_rating=rating_data.atmosphere_rating,
        organization_rating=rating_data.organization_rating,
        location_rating=rating_data.location_rating
    )
    
    db.add(new_rating)
    
    # Update event average rating
    db.flush()
    ratings = db.query(EventRating).filter(EventRating.event_id == rating_data.event_id).all()
    if ratings:
        avg_rating = sum(r.rating for r in ratings) / len(ratings)
        event.average_rating = round(avg_rating, 2)
    
    db.commit()
    db.refresh(new_rating)
    
    return new_rating

@router.get("/events/{event_id}", response_model=List[EventRatingResponse])
async def get_event_ratings(
    event_id: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get event ratings"""
    
    ratings = db.query(EventRating).filter(
        EventRating.event_id == event_id
    ).order_by(EventRating.created_at.desc()).offset(offset).limit(limit).all()
    
    return ratings

# Spot Ratings
@router.post("/spots", response_model=SpotRatingResponse)
async def create_spot_rating(
    rating_data: SpotRatingCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Rate a spot/location"""
    
    # Check event exists
    event = db.query(Event).filter(Event.id == rating_data.event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    # Create rating
    new_rating = SpotRating(
        event_id=rating_data.event_id,
        user_id=current_user.id,
        spot_name=rating_data.spot_name,
        latitude=rating_data.latitude,
        longitude=rating_data.longitude,
        rating=rating_data.rating,
        review=rating_data.review,
        accessibility_rating=rating_data.accessibility_rating,
        parking_rating=rating_data.parking_rating,
        safety_rating=rating_data.safety_rating
    )
    
    db.add(new_rating)
    db.commit()
    db.refresh(new_rating)
    
    return new_rating

@router.get("/spots/{event_id}", response_model=List[SpotRatingResponse])
async def get_spot_ratings(
    event_id: str,
    db: Session = Depends(get_db)
):
    """Get spot ratings for an event"""
    
    ratings = db.query(SpotRating).filter(
        SpotRating.event_id == event_id
    ).order_by(SpotRating.rating.desc()).all()
    
    return ratings

# User Ratings
@router.post("/users", response_model=UserRatingResponse)
async def create_user_rating(
    rating_data: UserRatingCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Rate a user"""
    
    # Check user exists
    rated_user = db.query(User).filter(User.id == rating_data.rated_user_id).first()
    if not rated_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Cannot rate yourself
    if rating_data.rated_user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot rate yourself")
    
    # Check if already rated
    existing_rating = db.query(UserRating).filter(
        UserRating.rated_user_id == rating_data.rated_user_id,
        UserRating.rater_user_id == current_user.id
    ).first()
    
    if existing_rating:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already rated this user")
    
    # Create rating
    new_rating = UserRating(
        rated_user_id=rating_data.rated_user_id,
        rater_user_id=current_user.id,
        rating=rating_data.rating,
        review=rating_data.review,
        punctuality_rating=rating_data.punctuality_rating,
        behavior_rating=rating_data.behavior_rating
    )
    
    db.add(new_rating)
    
    # Update user average rating
    db.flush()
    ratings = db.query(UserRating).filter(UserRating.rated_user_id == rating_data.rated_user_id).all()
    if ratings:
        avg_rating = sum(r.rating for r in ratings) / len(ratings)
        rated_user.average_rating = str(round(avg_rating, 2))
    
    db.commit()
    db.refresh(new_rating)
    
    return new_rating

@router.get("/users/{user_id}", response_model=List[UserRatingResponse])
async def get_user_ratings(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get ratings for a user"""
    
    ratings = db.query(UserRating).filter(
        UserRating.rated_user_id == user_id
    ).order_by(UserRating.created_at.desc()).all()
    
    return ratings
