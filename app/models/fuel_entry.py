from sqlalchemy import Boolean, Column, DateTime, Float, Index, String, Text

from app.database import Base
from app.models.base import new_id, utcnow


class FuelEntry(Base):
    """
    Заправка — для учёта расхода топлива и его стоимости по каждой машине
    из гаража. На основе истории заправок считается средний расход
    (л/100км) и средняя цена литра — см. _compute_stats в
    app/api/fuel_entries.py.
    """

    __tablename__ = "fuel_entries"

    id = Column(String(36), primary_key=True, default=new_id)
    car_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)

    date = Column(DateTime, nullable=False)
    liters = Column(Float, nullable=False)
    total_cost = Column(Float, nullable=False)
    odometer_km = Column(Float, nullable=True)

    # Полный бак vs частичная заправка — важно для расчёта среднего расхода:
    # интервал между двумя заправками "полный бак" даёт корректный л/100км,
    # частичные заправки между ними в расчёт не попадают отдельно.
    full_tank = Column(Boolean, default=True, nullable=False)

    station = Column(String(120), nullable=True)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    @property
    def price_per_liter(self) -> float:
        return round(self.total_cost / self.liters, 2) if self.liters else 0.0


Index("ix_fuel_entries_car_date", FuelEntry.car_id, FuelEntry.date)
