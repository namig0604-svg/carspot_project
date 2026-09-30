from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text

from app.database import Base
from app.models.base import new_id, utcnow


class Trip(Base):
    """
    Поездка, записанная трекером (GPS): дистанция/длительность/скорость +
    сам маршрут (JSON-массив точек в route_json — см. app/schemas/trip.py).

    Все агрегаты (distance_km, duration_s, avg_speed_kmh, top_speed_kmh)
    считаются НА КЛИЕНТЕ во время записи (непрерывный поток геопозиции
    доступен только там) и присылаются уже готовыми — бэкенд им доверяет
    и просто сохраняет, как и с заправками в app/models/fuel_entry.py.
    car_id необязателен: поездка не обязана быть привязана к конкретной
    машине из гаража.
    """

    __tablename__ = "trips"

    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), index=True, nullable=False)
    car_id = Column(String(36), index=True, nullable=True)

    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=False)

    distance_km = Column(Float, nullable=False)
    duration_s = Column(Integer, nullable=False)
    avg_speed_kmh = Column(Float, nullable=False)
    top_speed_kmh = Column(Float, nullable=False)

    # JSON-массив точек: [{"lat":.., "lng":.., "t":.., "speed_kmh":..}, ...]
    # (t — секунды от начала поездки). Text, а не JSON-тип колонки — проект
    # нигде не использует JSON-колонки СУБД, только сериализацию в Text
    # (см. app/schemas/trip.py: route_to_json/route_from_json).
    route_json = Column(Text, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)


Index("ix_trips_user_started", Trip.user_id, Trip.started_at)
Index("ix_trips_car_started", Trip.car_id, Trip.started_at)
