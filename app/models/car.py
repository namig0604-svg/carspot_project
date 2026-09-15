import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
 
from app.database import Base
 
class Car(Base):
    __tablename__ = "cars"
 
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    mods = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)