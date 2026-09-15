import uuid
from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime, Boolean
 
from app.database import Base
 
class EventParticipant(Base):
    __tablename__ = "event_participants"
 
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String, ForeignKey("events.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    is_attending = Column(Boolean, default=True)
    attended = Column(Boolean, default=False)
    
    joined_at = Column(DateTime, default=datetime.utcnow)