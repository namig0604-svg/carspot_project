from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.event import Event
from app.models.user import User
from app.utils.auth import get_current_active_user

router = APIRouter()

@router.post("/", status_code=201)
def create_event(
    event_data: dict,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Создать событие"""
    try:
        new_event = Event(
            creator_id=current_user.id,
            title=event_data.get("title"),
            description=event_data.get("description"),
            event_type=event_data.get("event_type"),
            country=event_data.get("country"),
            city=event_data.get("city"),
            location_name=event_data.get("location_name"),
            latitude=event_data.get("latitude"),
            longitude=event_data.get("longitude"),
            address=event_data.get("address"),
            event_date=event_data.get("event_date"),
            event_time=event_data.get("event_time"),
            duration_minutes=event_data.get("duration_minutes", 120),
            is_active=True,
            is_cancelled=False
        )
        
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        
        return {
            "id": new_event.id,
            "creator_id": new_event.creator_id,
            "title": new_event.title,
            "description": new_event.description,
            "event_type": new_event.event_type,
            "country": new_event.country,
            "city": new_event.city,
            "location_name": new_event.location_name,
            "latitude": new_event.latitude,
            "longitude": new_event.longitude,
            "address": new_event.address,
            "event_date": new_event.event_date,
            "event_time": new_event.event_time,
            "duration_minutes": new_event.duration_minutes,
            "participants_count": new_event.participants_count,
            "average_rating": new_event.average_rating,
            "is_active": new_event.is_active,
            "is_cancelled": new_event.is_cancelled,
            "created_at": new_event.created_at
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
def get_events(db: Session = Depends(get_db)):
    """Получить события"""
    events = db.query(Event).filter(Event.is_active == True).all()
    return events

@router.get("/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)):
    """Получить событие"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@router.post("/{event_id}/join")
def join_event(
    event_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Присоединиться к событию"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return {"message": "Joined event", "event_id": event_id}