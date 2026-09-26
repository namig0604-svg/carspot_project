"""
Импорт автосервисов/тюнинг-ателье/шиномонтажей/магазинов запчастей из
OpenStreetMap (через публичный Overpass API) в каталог заведений.

Почему OSM, а не парсинг Яндекс.Карт: массовое копирование карточек заведений
с Яндекс.Карт нарушает их условия использования. OSM — открытые данные
(ODbL), их использование для такой цели прямо разрешено. Визуальный стиль
карты в приложении (тайлы) при этом не меняется — это отдельная настройка
(см. lib/utils/map_config.dart на клиенте), тут речь только об ИСТОЧНИКЕ
данных о заведениях.

Логика намеренно разбита на чистые функции (build_overpass_query,
element_to_business_fields), которые не делают HTTP/DB-запросов — это
позволяет их протестировать на примере JSON-ответа Overpass без сети,
которая в CI/песочнице может быть недоступна.

Импорт привязан к региону/местоположению пользователя (см.
app/geocoding.reverse_geocode_country и авто-триггер в
app/api/businesses.list_businesses): страна, для которой запускается импорт,
определяется по GPS-координатам, которые уже присылает клиент, а не
захардкожена на Грузию.
"""
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.config import settings

# Категории, которые попросил добавить пользователь (в порядке его выбора):
# "Автосервисы и автоэлектрики", "Тюнинг-ателье и кузовной ремонт",
# "Шиномонтаж и автомойка", "Магазины запчастей".
# OSM не имеет отдельных тегов для tuning/electric — они выделяются из
# car_repair по ключевым словам в названии (см. _classify_repair_name).
_OSM_QUERY_BLOCKS = [
    # (osm selector for Overpass QL, without leading "node"/"way"/"relation")
    '["amenity"="car_repair"]',
    '["shop"="car_repair"]',
    '["amenity"="car_wash"]',
    '["shop"="tyres"]',
    '["shop"="car_parts"]',
    '["craft"="bodywork"]',
]

_TUNING_KEYWORDS = ("тюнинг", "tuning", "тюнинг-ателье", "чип-тюнинг", "chiptuning")
_ELECTRIC_KEYWORDS = ("автоэлектрик", "электрик", "electric", "auto electric")
_BODY_SHOP_KEYWORDS = ("кузов", "покрас", "bodywork", "body shop", "паинт", "paint")

# ISO 3166-1 alpha-2 -> русское название страны. Ровно те 11 стран СНГ,
# которые приложение поддерживает на клиенте (см. lib/utils/cities_data.dart)
# — им и должен быть ограничен как ручной, так и авто-импорт из OSM.
ISO2_TO_COUNTRY_RU = {
    "RU": "Россия",
    "UA": "Украина",
    "BY": "Беларусь",
    "KZ": "Казахстан",
    "UZ": "Узбекистан",
    "AZ": "Азербайджан",
    "AM": "Армения",
    "GE": "Грузия",
    "TJ": "Таджикистан",
    "TM": "Туркменистан",
    "MD": "Молдова",
}


def country_name_from_iso2(country_iso2: str) -> str:
    """ISO2 -> русское название страны из ISO2_TO_COUNTRY_RU, либо сам код
    заглавными буквами, если страна не из поддерживаемого списка (на случай
    ручного вызова эндпоинта админом с произвольным кодом)."""
    return ISO2_TO_COUNTRY_RU.get((country_iso2 or "").upper(), (country_iso2 or "").upper())


def is_supported_country(country_iso2: Optional[str]) -> bool:
    """Входит ли код страны в список стран, которые реально поддерживает
    приложение (см. ISO2_TO_COUNTRY_RU) — авто-импорт по геолокации
    запускаем только для них, чтобы не дёргать Overpass для случайных
    координат за пределами СНГ."""
    return bool(country_iso2) and country_iso2.upper() in ISO2_TO_COUNTRY_RU


def build_overpass_query(country_iso2: str = "GE", timeout_seconds: Optional[int] = None) -> str:
    """Overpass QL: все заведения из _OSM_QUERY_BLOCKS в пределах страны (по ISO 3166-1)."""
    timeout_seconds = timeout_seconds or settings.OVERPASS_TIMEOUT_SECONDS
    selectors = "\n  ".join(
        f'node{sel}(area.searchArea);\n  way{sel}(area.searchArea);\n  relation{sel}(area.searchArea);'
        for sel in _OSM_QUERY_BLOCKS
    )
    return (
        f'[out:json][timeout:{timeout_seconds}];\n'
        f'area["ISO3166-1"="{country_iso2}"]["boundary"="administrative"]->.searchArea;\n'
        f'(\n  {selectors}\n);\n'
        f'out center tags;'
    )


def _classify_repair_name(name: str) -> str:
    """Для car_repair/car_repair-shop уточняем подкатегорию по названию."""
    low = (name or "").lower()
    if any(kw in low for kw in _TUNING_KEYWORDS):
        return "tuning"
    if any(kw in low for kw in _ELECTRIC_KEYWORDS):
        return "electric"
    if any(kw in low for kw in _BODY_SHOP_KEYWORDS):
        return "body_shop"
    return "service"


def _osm_tags_to_category(tags: dict) -> Optional[str]:
    name = tags.get("name") or tags.get("name:ru") or tags.get("name:en") or ""
    if tags.get("amenity") == "car_wash":
        return "car_wash"
    if tags.get("shop") == "tyres":
        return "tire"
    if tags.get("shop") == "car_parts":
        return "parts"
    if tags.get("craft") == "bodywork":
        return "body_shop"
    if tags.get("amenity") == "car_repair" or tags.get("shop") == "car_repair":
        return _classify_repair_name(name)
    return None


def _build_address(tags: dict) -> Optional[str]:
    parts = [
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
    ]
    parts = [p for p in parts if p]
    address = " ".join(parts) if parts else None
    return address or None


def element_to_business_fields(el: dict, country_iso2: str = "GE") -> Optional[dict]:
    """
    Один элемент ответа Overpass (`out center tags`) -> словарь полей для
    Business, либо None если элемент не подходит для импорта (нет имени
    или нет координат — например, заведение существует только как часть
    более крупного полигона без своей точки).

    country_iso2 — код страны, для которой реально был выполнен запрос к
    Overpass (см. fetch_overpass_elements) — раньше здесь было захардкожено
    "Georgia" независимо от того, какую страну запрашивали.
    """
    tags = el.get("tags") or {}
    name = (tags.get("name") or tags.get("name:ru") or tags.get("name:en") or "").strip()
    if not name:
        return None

    category = _osm_tags_to_category(tags)
    if not category:
        return None

    if "lat" in el and "lon" in el:
        lat, lon = el["lat"], el["lon"]
    elif "center" in el:
        lat, lon = el["center"].get("lat"), el["center"].get("lon")
    else:
        return None
    if lat is None or lon is None:
        return None

    osm_id = f'{el.get("type")}/{el.get("id")}'

    return {
        "osm_id": osm_id,
        "name": name[:150],
        "category": category,
        "description": None,
        "services": None,
        "country": country_name_from_iso2(country_iso2),
        "city": (tags.get("addr:city") or "").strip()[:100] or None,
        "address": _build_address(tags),
        "latitude": float(lat),
        "longitude": float(lon),
        "phone": (tags.get("phone") or tags.get("contact:phone") or "")[:30] or None,
        "website": (tags.get("website") or tags.get("contact:website") or "")[:300] or None,
        "instagram": None,
        "work_hours": (tags.get("opening_hours") or "")[:200] or None,
    }


def fetch_overpass_elements(country_iso2: str = "GE") -> list:
    """Реальный сетевой запрос к Overpass. Бросает исключение при ошибке —
    вызывающий код (эндпоинт) сам решает, как это подать пользователю."""
    query = build_overpass_query(country_iso2)
    resp = requests.post(
        settings.OVERPASS_URL,
        data={"data": query},
        timeout=settings.OVERPASS_TIMEOUT_SECONDS + 10,
        headers={
            "User-Agent": "CarSpotApp/1.0 (+https://github.com/namig0604-svg/carspot_project)",
            "Accept": "application/json",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("elements", [])


def run_osm_import(db: Session, country_iso2: str, dry_run: bool = False) -> dict:
    """
    Общая логика импорта/апдейта заведений из OSM для одной страны — вынесена
    в отдельную функцию, чтобы её могли использовать и ручной админ-эндпоинт
    (app/api/admin.import_osm_businesses), и авто-триггер по геолокации
    пользователя (app/api/businesses.list_businesses). Идемпотентно: каждое
    заведение хранит свой osm_id, повторный запуск обновит уже импортированные
    записи, а не создаст дубликаты.

    Возвращает {"found_in_osm", "created", "updated", "skipped"}. Может
    бросить requests.RequestException — вызывающий код решает, как её подать.
    """
    from app.models.business import Business

    elements = fetch_overpass_elements(country_iso2)

    created = 0
    updated = 0
    skipped = 0

    for el in elements:
        fields = element_to_business_fields(el, country_iso2)
        if not fields:
            skipped += 1
            continue

        osm_id = fields["osm_id"]
        existing = db.query(Business).filter(Business.osm_id == osm_id).first()

        if existing:
            if not dry_run:
                for key, value in fields.items():
                    if key == "osm_id":
                        continue
                    # Не затираем то, что владелец/админ мог вручную заполнить
                    # (описание, услуги, инста) — обновляем только "сырые" поля из OSM.
                    if key in ("description", "services", "instagram") and getattr(existing, key):
                        continue
                    setattr(existing, key, value)
            updated += 1
        else:
            if not dry_run:
                db.add(Business(owner_id=None, **fields))
            created += 1

    if not dry_run:
        db.commit()

    return {
        "found_in_osm": len(elements),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }
