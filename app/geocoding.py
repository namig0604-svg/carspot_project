"""
Обратное геокодирование координат в человекочитаемый адрес — через
публичный Nominatim (OpenStreetMap). Нужно в первую очередь для заведений,
импортированных из OSM (см. app/osm_import.py): у многих точек в OSM нет
тегов addr:street/addr:housenumber, поэтому поле address у них пустое.

Тот же класс осторожностей, что и с Overpass в osm_import.py: публичный
инстанс Nominatim требует внятный User-Agent и не более 1 запроса в
секунду (https://operations.osmfoundation.org/policies/nominatim/) —
вызывающий код (см. app/api/admin.py) сам выдерживает паузу между вызовами.
"""
from typing import Optional

import requests

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "CarSpotApp/1.0 (+https://github.com/namig0604-svg/carspot_project)"


def reverse_geocode_address(lat: float, lon: float) -> Optional[str]:
    """Один запрос обратного геокодирования. Возвращает короткую строку
    адреса или None, если ничего не удалось получить (сеть, таймаут,
    пустой ответ) — вызывающий код просто оставляет address пустым в
    этом случае, ничего не падает."""
    try:
        resp = requests.get(
            _NOMINATIM_URL,
            params={
                "format": "jsonv2",
                "lat": lat,
                "lon": lon,
                "accept-language": "ru",
                "zoom": 18,
            },
            timeout=10,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None

    addr = data.get("address") or {}
    road = addr.get("road")
    house_number = addr.get("house_number")
    if road:
        text = f"{road} {house_number}" if house_number else road
        return str(text)[:300]

    display_name = data.get("display_name")
    if display_name:
        return str(display_name)[:300]
    return None
