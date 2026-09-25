from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from app.database import Base
from app.models.base import new_id, utcnow

MAINTENANCE_TYPES = (
    "oil",            # замена масла
    "tires",          # шиномонтаж / сезонная замена резины
    "brakes",         # тормоза
    "filters",        # фильтры
    "inspection",     # ТО / диагностика
    "repair",         # ремонт
    "insurance",      # страховка (для напоминаний, не траты)
    "other",
)


class MaintenanceRecord(Base):
    """Запись сервисного дневника автомобиля: что и когда делали + когда следующее."""

    __tablename__ = "maintenance_records"

    id = Column(String(36), primary_key=True, default=new_id)
    car_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)

    type = Column(String(20), nullable=False, default="other")
    title = Column(String(200), nullable=False)          # "Замена масла и фильтра"
    done_at = Column(DateTime, nullable=False)            # когда сделали
    mileage_km = Column(Integer, nullable=True)           # пробег на момент
    cost = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=True)

    # Напоминание о следующем разе — по дате и/или по пробегу, что раньше наступит.
    next_due_at = Column(DateTime, nullable=True)
    next_due_mileage_km = Column(Integer, nullable=True)
    is_seasonal = Column(String(10), nullable=True)       # "winter" / "summer" для шин, иначе NULL
    reminder_sent = Column(String(5), nullable=False, default="no")  # "no" / "yes" — чтобы не спамить push

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


Index("ix_maintenance_car_done", MaintenanceRecord.car_id, MaintenanceRecord.done_at)
Index("ix_maintenance_due", MaintenanceRecord.next_due_at, MaintenanceRecord.reminder_sent)
