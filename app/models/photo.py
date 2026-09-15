import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Boolean
 
from app.database import Base
 
class Photo(Base):
    __tablename__ = "photos"
 
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, ForeignKey("events.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    photo_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    caption = Column(Text, nullable=True)
    
    likes_count = Column(Integer, default=0)
    is_approved = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
 
 