"""
Обратное геокодирование координат в человекочитаемый адрес — через
публичный Nominatim (OpenStreetMap). Нужно в первую очередь для заведений,
импортированных из OSM (см. app/osm_import.py): у многих точек в OSM нет
тегов addr:street/addr:housenumber, поэтому поле address у них пустое.

Также используется, чтобы понять, в какой стране находится пользователь по
его GPS-координатам (reverse_geocode_country) — это и есть "привязка" импорта
заведений к региону/местоположению пользователя (см. авто-триггер в
app/api/businesses.list_businesses): вместо того чтобы админ вручную запускал
импорт по одной стране за раз, при запросе каталога с реальными координатами
пользователя мы сами определяем его страну и, если для неё ещё ничего не
импортировано, подтягиваем данные из OSM в фоне.

Тот же класс осторожностей, что и с Overpass в osm_import.py: публичный
инстанс Nominatim требует внятный User-Agent и не более 1 запроса в
секунду (https://operations.osmfoundation.org/policies/nominatim/) —
вызывающий код (см. app/api/admin.py, app/api/businesses.py) сам выдерживает
паузу между вызовами.
"""
from typing import Optional

import requests

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "CarSpotApp/1.0 (+https://github.com/namig0604-svg/carspot_project)"


def _reverse_geocode_raw(lat: float, lon: float) -> Optional[dict]:
    """Один запрос обратного геокодирования, сырой ответ Nominatim (jsonv2)
    или None при любой сетевой ошибке/таймауте — общая часть для
    reverse_geocode_address и reverse_geocode_country, чтобы не плодить
    по два запроса на одни и те же координаты."""
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
        return resp.json()
    except requests.RequestException:
        return None


def reverse_geocode_address(lat: float, lon: float) -> Optional[str]:
    """Один запрос обратного геокодирования. Возвращает короткую строку
    адреса или None, если ничего не удалось получить (сеть, таймаут,
    пустой ответ) — вызывающий код просто оставляет address пустым в
    этом случае, ничего не падает."""
    data = _reverse_geocode_raw(lat, lon)
    if not data:
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


def reverse_geocode_country(lat: float, lon: float) -> Optional[str]:
    """Определяет ISO 3166-1 alpha-2 код страны по координатам (например,
    "GE" для Грузии) через поле address.country_code в ответе Nominatim.
    Возвращает None, если геокодирование не удалось или страна не
    определена — вызывающий код в этом случае просто не запускает
    авто-импорт (см. app/api/businesses.py)."""
    data = _reverse_geocode_raw(lat, lon)
    if not data:
        return None

    addr = data.get("address") or {}
    country_code = addr.get("country_code")
    if not country_code:
        return None
    return str(country_code).strip().upper()[:2] or None
