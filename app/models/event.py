import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Text, Boolean
 
from app.database import Base
 
class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    creator_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(50), nullable=False)
    
    country = Column(String(50), nullable=False)
    city = Column(String(100), nullable=True)
    location_name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=True)  # ✅ ДОБАВЬ ЭТУ СТРОКУ!
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    event_date = Column(DateTime, nullable=False)
    event_time = Column(String(10), nullable=False)
    duration_minutes = Column(Integer, default=120)
    
    participants_count = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    
    is_active = Column(Boolean, default=True)
    is_cancelled = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)