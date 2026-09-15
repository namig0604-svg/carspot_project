import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Float
 
from app.database import Base
 
class EventRating(Base):
    __tablename__ = "event_ratings"
 
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, ForeignKey("events.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    rating = Column(Integer, nullable=False)
    review = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
 
class UserRating(Base):
    __tablename__ = "user_ratings"
 
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    rated_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    rater_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    rating = Column(Integer, nullable=False)
    review = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
 
class SpotRating(Base):
    __tablename__ = "spot_ratings"
 
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    location_name = Column(String(255), nullable=False)
    
    rating = Column(Integer, nullable=False)
    review = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)