import uuid
from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime, Text
 
from app.database import Base
 
class Story(Base):
    __tablename__ = "stories"
 
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)