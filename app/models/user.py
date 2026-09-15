import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer
 
from app.database import Base
 
class User(Base):
    __tablename__ = "users"
 
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String(100), nullable=True)
    country = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    is_pro = Column(Boolean, default=False)
    
    average_rating = Column(String(10), default="0.0")
    events_created = Column(Integer, default=0)
    events_attended = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)