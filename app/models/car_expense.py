from sqlalchemy import Column, DateTime, Float, Index, String, Text

from app.database import Base
from app.models.base import new_id, utcnow

EXPENSE_CATEGORIES = (
    "fuel",       # топливо
    "service",    # ТО/ремонт
    "insurance",
    "parking",
    "carwash",
    "fines",      # штрафы
    "other",
)


class CarExpense(Base):
    """Трата на автомобиль — для учёта стоимости владения."""

    __tablename__ = "car_expenses"

    id = Column(String(36), primary_key=True, default=new_id)
    car_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)

    category = Column(String(20), nullable=False, default="other")
    amount = Column(Float, nullable=False)
    date = Column(DateTime, nullable=False)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)


Index("ix_car_expenses_car_date", CarExpense.car_id, CarExpense.date)
