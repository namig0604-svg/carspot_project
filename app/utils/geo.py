"""
Геоутилиты для карты: расстояние между точками и рамка поиска.
Работают одинаково на PostgreSQL и SQLite — без PostGIS.
"""
import math
from typing import Tuple

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками на Земле в километрах."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bounding_box(lat: float, lon: float, radius_km: float) -> Tuple[float, float, float, float]:
    """
    Прямоугольник вокруг точки — чтобы SQL быстро отсёк дальние записи
    по индексу, а точное расстояние досчитали уже в Python.

    Возвращает (min_lat, max_lat, min_lon, max_lon).
    """
    radius_km = max(0.1, float(radius_km))

    lat_delta = radius_km / 111.32  # 1 градус широты ≈ 111.32 км

    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-6:  # у полюсов берём весь диапазон долгот
        lon_delta = 180.0
    else:
        lon_delta = radius_km / (111.32 * abs(cos_lat))

    return (
        max(-90.0, lat - lat_delta),
        min(90.0, lat + lat_delta),
        max(-180.0, lon - lon_delta),
        min(180.0, lon + lon_delta),
    )
