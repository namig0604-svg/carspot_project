"""
Сквозной тест всего API: регистрация → гараж → сходка → карта →
участники → рейтинги → клуб → чат.

Запуск:  python tests/test_full_flow.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_carspot.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, extra: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  OK   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name} {extra}")


def main() -> int:
    # Чистая база на каждый прогон
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    client = TestClient(app)

    print("\n=== СЛУЖЕБНЫЕ РУЧКИ ===")
    r = client.get("/health")
    check("GET /health", r.status_code == 200 and r.json()["status"] == "ok", r.text)
    r = client.get("/")
    check("GET /", r.status_code == 200, r.text)

    print("\n=== АВТОРИЗАЦИЯ ===")
    r = client.post("/api/auth/register", json={
        "username": "namig", "email": "namig@example.com", "password": "Kalicto300",
        "full_name": "Namig Nabiev", "country": "Georgia", "city": "Tbilisi",
    })
    check("Регистрация пользователя 1", r.status_code == 201, r.text)
    token1 = r.json()["access_token"]
    user1 = r.json()["user"]
    h1 = {"Authorization": f"Bearer {token1}"}

    r = client.post("/api/auth/register", json={
        "username": "dato", "email": "dato@example.com", "password": "Passw0rd!",
        "full_name": "Dato G", "country": "Georgia", "city": "Tbilisi",
    })
    check("Регистрация пользователя 2", r.status_code == 201, r.text)
    token2 = r.json()["access_token"]
    user2 = r.json()["user"]
    h2 = {"Authorization": f"Bearer {token2}"}

    r = client.post("/api/auth/register", json={
        "username": "namig", "email": "other@example.com", "password": "Kalicto300"})
    check("Дубль username отклонён", r.status_code == 400, r.text)

    r = client.post("/api/auth/login", json={"username": "namig", "password": "Kalicto300"})
    check("Вход по username", r.status_code == 200, r.text)

    r = client.post("/api/auth/login", json={"username": "namig@example.com", "password": "Kalicto300"})
    check("Вход по email", r.status_code == 200, r.text)

    r = client.post("/api/auth/login", json={"username": "namig", "password": "wrong"})
    check("Неверный пароль отклонён", r.status_code == 401, r.text)

    r = client.post("/api/auth/token", data={"username": "namig", "password": "Kalicto300"})
    check("OAuth2-форма (кнопка Authorize)", r.status_code == 200, r.text)

    r = client.get("/api/auth/me", headers=h1)
    check("GET /api/auth/me", r.status_code == 200 and r.json()["username"] == "namig", r.text)

    r = client.get("/api/auth/me")
    check("Без токена — 401", r.status_code == 401, r.text)

    print("\n=== ПРОФИЛЬ ===")
    r = client.patch("/api/users/me", headers=h1, json={"bio": "Дрифт и JDM", "instagram": "@namig"})
    check("Обновление профиля", r.status_code == 200 and r.json()["bio"] == "Дрифт и JDM", r.text)

    r = client.get(f"/api/users/{user2['id']}")
    check("Чужой профиль", r.status_code == 200, r.text)

    r = client.get("/api/users/", params={"q": "dat"})
    check("Поиск пользователей", r.status_code == 200 and len(r.json()) >= 1, r.text)

    print("\n=== МОЙ ГАРАЖ ===")
    r = client.post("/api/cars/", headers=h1, json={
        "make": "Nissan", "model": "Silvia S15", "year": 1999, "generation": "S15",
        "body_type": "coupe", "engine": "SR20DET", "engine_volume": "2.0",
        "power_hp": 450, "torque_nm": 520, "drivetrain": "RWD", "transmission": "manual",
        "fuel_type": "petrol", "weight_kg": 1240, "zero_to_hundred": "4.5",
        "color": "Midnight Purple", "mods": "Garrett GT2871R, HKS coilovers",
        "description": "Билд для дрифта",
    })
    check("Добавление машины", r.status_code == 201, r.text)
    car1 = r.json()
    check("Первая машина стала основной", car1["is_primary"] is True, str(car1))

    r = client.post("/api/cars/", headers=h1, json={
        "make": "Toyota", "model": "Supra MK4", "year": 1997, "power_hp": 700,
        "engine": "2JZ-GTE", "drivetrain": "RWD",
    })
    check("Вторая машина", r.status_code == 201, r.text)
    car2 = r.json()

    r = client.get("/api/cars/my", headers=h1)
    check("Мой гараж содержит 2 машины", r.status_code == 200 and r.json()["cars_count"] == 2, r.text)

    r = client.post(f"/api/cars/{car2['id']}/primary", headers=h1)
    check("Смена основной машины", r.status_code == 200 and r.json()["is_primary"] is True, r.text)

    r = client.get("/api/cars/my", headers=h1)
    primaries = [c for c in r.json()["cars"] if c["is_primary"]]
    check("Основная машина ровно одна", len(primaries) == 1, str(primaries))

    r = client.patch(f"/api/cars/{car1['id']}", headers=h1, json={"power_hp": 480})
    check("Обновление характеристик", r.status_code == 200 and r.json()["power_hp"] == 480, r.text)

    r = client.patch(f"/api/cars/{car1['id']}", headers=h2, json={"power_hp": 1})
    check("Чужую машину менять нельзя", r.status_code == 403, r.text)

    r = client.get(f"/api/users/{user1['id']}/cars")
    check("Гараж виден в профиле", r.status_code == 200 and len(r.json()) == 2, r.text)

    print("\n=== СХОДКИ ===")
    r = client.post("/api/events/", headers=h1, json={
        "title": "Ночная сходка на Ваке", "description": "Собираемся, общаемся",
        "event_type": "meetup", "country": "Georgia", "city": "Tbilisi",
        "location_name": "Vake Park", "latitude": 41.7151, "longitude": 44.7671,
        "event_date": "2026-10-01T20:00:00", "event_time": "20:00",
        "duration_minutes": 180, "max_participants": 50,
    })
    check("Создание сходки", r.status_code == 201, r.text)
    event1 = r.json()
    check("Создатель — участник", event1["participants_count"] == 1, str(event1))
    check("Чат сходки создан", bool(event1["chat_room_id"]), str(event1))

    r = client.post("/api/events/", headers=h2, json={
        "title": "Дрифт в Рустави", "event_type": "drift", "country": "Georgia",
        "city": "Rustavi", "latitude": 41.5495, "longitude": 45.0000,
        "event_date": "2026-10-05T14:00:00",
    })
    check("Вторая сходка", r.status_code == 201, r.text)
    event2 = r.json()

    r = client.post("/api/events/", headers=h1, json={
        "title": "Далеко", "event_type": "meetup", "latitude": 55.75, "longitude": 37.61,
        "event_date": "2026-10-10T12:00:00", "city": "Moscow",
    })
    check("Третья сходка (далеко)", r.status_code == 201, r.text)

    r = client.post("/api/events/", headers=h1, json={
        "title": "Битый тип", "event_type": "неизвестно", "latitude": 41.7,
        "longitude": 44.7, "event_date": "2026-10-01T20:00:00"})
    check("Неверный event_type отклонён", r.status_code == 422, r.text)

    r = client.get("/api/events/", params={"city": "Tbilisi"})
    check("Список с фильтром по городу", r.status_code == 200 and r.json()["total"] == 1, r.text)

    r = client.get("/api/events/", params={"search": "дрифт"})
    check("Поиск по тексту", r.status_code == 200 and r.json()["total"] >= 1, r.text)

    r = client.get("/api/events/", params={"event_type": "drift"})
    check("Фильтр по типу", r.status_code == 200 and r.json()["total"] == 1, r.text)

    print("\n=== КАРТА И ГЕОПОИСК ===")
    r = client.get("/api/events/map", params={
        "min_lat": 41.0, "max_lat": 42.0, "min_lon": 44.0, "max_lon": 46.0})
    check("Метки в области карты", r.status_code == 200 and len(r.json()) == 2, r.text)

    r = client.get("/api/events/nearby", params={
        "latitude": 41.7151, "longitude": 44.7671, "radius_km": 5})
    near5 = r.json()
    check("Рядом 5 км — только Ваке", r.status_code == 200 and len(near5) == 1, r.text)

    r = client.get("/api/events/nearby", params={
        "latitude": 41.7151, "longitude": 44.7671, "radius_km": 60})
    near60 = r.json()
    check("Рядом 60 км — Ваке + Рустави", len(near60) == 2, str(near60))
    check("Расстояние посчитано", near60[0]["distance_km"] is not None, str(near60[0]))
    check("Сортировка по близости",
          near60[0]["distance_km"] <= near60[1]["distance_km"], str(near60))
    check("Москва не попала в радиус",
          all("Далеко" != m["title"] for m in near60), str(near60))

    print("\n=== УЧАСТИЕ В СХОДКЕ ===")
    r = client.post(f"/api/events/{event1['id']}/join", headers=h2, json={"status": "going"})
    check("Присоединение к сходке", r.status_code == 200, r.text)
    check("Счётчик участников вырос", r.json()["participants_count"] == 2, r.text)

    r = client.post(f"/api/events/{event1['id']}/join", headers=h2,
                    json={"status": "going", "car_id": car1["id"]})
    check("Чужая машина при join отклонена", r.status_code == 400, r.text)

    r = client.get(f"/api/events/{event1['id']}/participants")
    check("Список участников", r.status_code == 200 and len(r.json()) == 2, r.text)
    check("Данные пользователя приложены", r.json()[0]["user"] is not None, r.text)

    r = client.get(f"/api/events/{event1['id']}", headers=h2)
    check("Карточка: is_joined", r.json()["is_joined"] is True, r.text)
    check("Карточка: creator приложен", r.json()["creator"]["username"] == "namig", r.text)

    r = client.get(f"/api/events/{event1['id']}", headers=h1)
    check("Карточка: is_creator", r.json()["is_creator"] is True, r.text)

    r = client.post(f"/api/events/{event1['id']}/leave", headers=h2)
    check("Выход из сходки", r.status_code == 200 and r.json()["participants_count"] == 1, r.text)

    r = client.post(f"/api/events/{event1['id']}/join", headers=h2, json={"status": "going"})
    check("Повторное присоединение", r.status_code == 200, r.text)

    r = client.patch(f"/api/events/{event1['id']}", headers=h2, json={"title": "Взлом"})
    check("Чужую сходку менять нельзя", r.status_code == 403, r.text)

    r = client.patch(f"/api/events/{event1['id']}", headers=h1,
                     json={"title": "Ночная сходка на Ваке (обновлено)"})
    check("Редактирование своей сходки", r.status_code == 200, r.text)

    print("\n=== РЕЙТИНГИ ===")
    r = client.post("/api/ratings/events", headers=h2, json={
        "event_id": event1["id"], "rating": 5, "review": "Отличная сходка",
        "atmosphere_rating": 5, "organization_rating": 4, "location_rating": 5})
    check("Оценка сходки", r.status_code == 201, r.text)

    r = client.post("/api/ratings/events", headers=h2, json={"event_id": event1["id"], "rating": 4})
    check("Повторная оценка обновляет", r.status_code == 201 and r.json()["rating"] == 4, r.text)

    r = client.get(f"/api/ratings/events/{event1['id']}/summary")
    check("Сводка рейтинга сходки",
          r.status_code == 200 and r.json()["ratings_count"] == 1 and r.json()["average_rating"] == 4.0,
          r.text)

    r = client.get(f"/api/events/{event1['id']}", headers=h2)
    check("Рейтинг попал в карточку", r.json()["average_rating"] == 4.0, r.text)
    check("my_rating виден", r.json()["my_rating"] == 4, r.text)

    r = client.post("/api/ratings/users", headers=h2, json={
        "rated_user_id": user1["id"], "rating": 5, "review": "Отличный организатор",
        "punctuality_rating": 5, "behavior_rating": 5})
    check("Оценка пользователя", r.status_code == 201, r.text)

    r = client.post("/api/ratings/users", headers=h1, json={"rated_user_id": user1["id"], "rating": 5})
    check("Самого себя оценить нельзя", r.status_code == 400, r.text)

    r = client.get(f"/api/ratings/users/{user1['id']}/summary")
    check("Сводка рейтинга пользователя", r.json()["average_rating"] == 5.0, r.text)

    r = client.get(f"/api/users/{user1['id']}")
    check("Рейтинг в профиле", r.json()["average_rating"] == 5.0, r.text)

    r = client.post("/api/ratings/spots", headers=h1, json={
        "spot_name": "Парковка у Vake Park", "event_id": event1["id"],
        "latitude": 41.7151, "longitude": 44.7671, "rating": 4,
        "parking_rating": 5, "safety_rating": 4})
    check("Оценка спота", r.status_code == 201, r.text)

    r = client.get("/api/ratings/spots", params={"event_id": event1["id"]})
    check("Список оценок спотов", r.status_code == 200 and len(r.json()) == 1, r.text)

    r = client.post("/api/ratings/events", headers=h2, json={"event_id": event1["id"], "rating": 9})
    check("Оценка вне 1..5 отклонена", r.status_code == 422, r.text)

    print("\n=== КЛУБЫ ===")
    r = client.post("/api/clubs/", headers=h1, json={
        "name": "Tbilisi JDM Crew", "description": "Клуб любителей японских авто",
        "country": "Georgia", "city": "Tbilisi", "tags": "JDM,Drift", "is_public": True})
    check("Создание клуба", r.status_code == 201, r.text)
    club = r.json()
    check("Владелец — участник", club["members_count"] == 1, str(club))
    check("Чат клуба создан", bool(club["chat_room_id"]), str(club))
    check("my_role = owner", club["my_role"] == "owner", str(club))

    r = client.post("/api/clubs/", headers=h2, json={"name": "Tbilisi JDM Crew"})
    check("Дубль названия клуба отклонён", r.status_code == 400, r.text)

    r = client.post("/api/clubs/", headers=h2, json={
        "name": "Closed Club", "is_public": False, "city": "Batumi"})
    check("Закрытый клуб создан", r.status_code == 201, r.text)
    closed_club = r.json()

    r = client.post(f"/api/clubs/{club['id']}/join", headers=h2)
    check("Вступление в открытый клуб", r.status_code == 200 and r.json()["status"] == "approved", r.text)

    r = client.post(f"/api/clubs/{club['id']}/join", headers=h2)
    check("Повторное вступление отклонено", r.status_code == 400, r.text)

    r = client.get(f"/api/clubs/{club['id']}")
    check("Счётчик участников клуба", r.json()["members_count"] == 2, r.text)

    r = client.post(f"/api/clubs/{closed_club['id']}/join", headers=h1)
    check("В закрытый клуб — заявка", r.status_code == 200 and r.json()["status"] == "pending", r.text)

    r = client.get(f"/api/clubs/{closed_club['id']}/members", params={"member_status": "pending"})
    check("Список заявок", r.status_code == 200 and len(r.json()) == 1, r.text)

    r = client.post(f"/api/clubs/{closed_club['id']}/members/{user1['id']}/approve", headers=h2)
    check("Одобрение заявки", r.status_code == 200, r.text)

    r = client.get(f"/api/clubs/{closed_club['id']}")
    check("После одобрения счётчик = 2", r.json()["members_count"] == 2, r.text)

    r = client.patch(f"/api/clubs/{club['id']}/members/{user2['id']}/role",
                     headers=h1, json={"role": "admin"})
    check("Назначение админа", r.status_code == 200, r.text)

    r = client.get(f"/api/clubs/{club['id']}/members")
    roles = {m["user_id"]: m["role"] for m in r.json()}
    check("Роль сохранена", roles.get(user2["id"]) == "admin", str(roles))

    r = client.post("/api/events/", headers=h2, json={
        "title": "Клубный выезд", "event_type": "cruise", "latitude": 41.72,
        "longitude": 44.78, "event_date": "2026-11-01T10:00:00",
        "city": "Tbilisi", "club_id": club["id"]})
    check("Событие клуба (админ может)", r.status_code == 201, r.text)

    r = client.get(f"/api/clubs/{club['id']}/events")
    check("События клуба в списке", r.status_code == 200 and len(r.json()) == 1, r.text)

    r = client.get("/api/clubs/my", headers=h2)
    check("Мои клубы", r.status_code == 200 and len(r.json()) == 2, r.text)

    r = client.get("/api/clubs/", params={"q": "JDM"})
    check("Поиск клубов", r.status_code == 200 and r.json()["total"] == 1, r.text)

    r = client.post(f"/api/clubs/{club['id']}/leave", headers=h1)
    check("Владелец не может выйти", r.status_code == 400, r.text)

    print("\n=== ЧАТЫ ===")
    event_room = event1["chat_room_id"]

    r = client.post(f"/api/chats/{event_room}/messages", headers=h1,
                    json={"text": "Всем привет, кто едет?"})
    check("Сообщение в чат сходки", r.status_code == 201, r.text)
    check("Автор приложен", r.json()["user"]["username"] == "namig", r.text)

    r = client.post(f"/api/chats/{event_room}/messages", headers=h2, json={"text": "Я еду!"})
    check("Второй участник пишет", r.status_code == 201, r.text)

    r = client.get(f"/api/chats/{event_room}/messages", headers=h1)
    data = r.json()
    check("История сообщений", r.status_code == 200 and data["total"] >= 2, r.text)
    texts = [m["text"] for m in data["items"]]
    check("Порядок от старых к новым",
          texts.index("Всем привет, кто едет?") < texts.index("Я еду!"), str(texts))

    r = client.post(f"/api/chats/{event_room}/messages", headers=h1, json={})
    check("Пустое сообщение отклонено", r.status_code == 400, r.text)

    r = client.post("/api/chats/direct", headers=h1, json={"user_id": user2["id"]})
    check("Личный чат создан", r.status_code == 200, r.text)
    direct_room = r.json()["id"]

    r = client.post("/api/chats/direct", headers=h2, json={"user_id": user1["id"]})
    check("Повторно — та же комната", r.json()["id"] == direct_room, r.text)

    r = client.post("/api/chats/direct", headers=h1, json={"user_id": user1["id"]})
    check("Чат с самим собой отклонён", r.status_code == 400, r.text)

    r = client.post(f"/api/chats/{direct_room}/messages", headers=h1, json={"text": "Здорово!"})
    check("Личное сообщение", r.status_code == 201, r.text)
    msg_id = r.json()["id"]

    r = client.get("/api/chats/", headers=h1)
    check("Список моих чатов", r.status_code == 200 and len(r.json()) >= 2, r.text)

    r = client.get(f"/api/chats/{direct_room}", headers=h1)
    check("Инфо о чате с участниками", r.status_code == 200 and len(r.json()["members"]) == 2, r.text)

    r = client.delete(f"/api/chats/{direct_room}/messages/{msg_id}", headers=h2)
    check("Чужое сообщение удалить нельзя", r.status_code == 403, r.text)

    r = client.delete(f"/api/chats/{direct_room}/messages/{msg_id}", headers=h1)
    check("Своё сообщение удалено", r.status_code == 200, r.text)

    r = client.post(f"/api/chats/{direct_room}/read", headers=h2)
    check("Отметка прочитанным", r.status_code == 200, r.text)

    # Посторонний не должен видеть чужой личный чат
    r = client.post("/api/auth/register", json={
        "username": "stranger", "email": "s@example.com", "password": "Passw0rd!"})
    h3 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.get(f"/api/chats/{direct_room}/messages", headers=h3)
    check("Посторонний не видит чужой чат", r.status_code == 403, r.text)

    print("\n=== ФОТО ===")
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
        "00000049454e44ae426082"
    )
    r = client.post("/api/photos/upload", headers=h1,
                    files={"file": ("test.png", png, "image/png")},
                    data={"event_id": event1["id"], "caption": "Тестовое фото"})
    check("Загрузка фото к сходке", r.status_code == 201, r.text)
    photo = r.json()

    r = client.get(f"/api/photos/event/{event1['id']}")
    check("Фото сходки в списке", r.status_code == 200 and r.json()["total"] == 1, r.text)

    r = client.get(f"/api/events/{event1['id']}")
    check("Счётчик фото у сходки", r.json()["photos_count"] == 1, r.text)

    r = client.post("/api/photos/upload", headers=h1,
                    files={"file": ("car.png", png, "image/png")},
                    data={"car_id": car1["id"]})
    check("Загрузка фото машины", r.status_code == 201, r.text)

    r = client.post("/api/photos/upload", headers=h2,
                    files={"file": ("car.png", png, "image/png")},
                    data={"car_id": car1["id"]})
    check("Фото к чужой машине отклонено", r.status_code == 403, r.text)

    r = client.post("/api/photos/upload", headers=h1,
                    files={"file": ("doc.txt", b"hello", "text/plain")},
                    data={"event_id": event1["id"]})
    check("Неверный формат отклонён", r.status_code == 400, r.text)

    r = client.post(f"/api/photos/{photo['id']}/like", headers=h2)
    check("Лайк фото", r.status_code == 200 and r.json()["likes_count"] == 1, r.text)

    r = client.post(f"/api/photos/{photo['id']}/like", headers=h2)
    check("Повторный лайк снимает", r.json()["likes_count"] == 0, r.text)

    r = client.delete(f"/api/photos/{photo['id']}", headers=h2)
    check("Чужое фото удалить нельзя", r.status_code == 403, r.text)

    r = client.delete(f"/api/photos/{photo['id']}", headers=h1)
    check("Своё фото удалено", r.status_code == 200, r.text)

    print("\n=== WEBSOCKET ЧАТ ===")
    try:
        with client.websocket_connect(f"/api/chats/ws/{event_room}?token={token1}") as ws1:
            ws1.receive_json()  # presence самого себя
            with client.websocket_connect(f"/api/chats/ws/{event_room}?token={token2}") as ws2:
                presence = ws1.receive_json()
                check("WS: присутствие второго участника",
                      presence["type"] == "presence" and presence["data"]["status"] == "online",
                      str(presence))
                ws2.receive_json()  # своё presence

                ws1.send_json({"text": "Сообщение через WebSocket"})
                received = ws2.receive_json()
                check("WS: сообщение доставлено",
                      received["type"] == "message"
                      and received["data"]["text"] == "Сообщение через WebSocket",
                      str(received))

                ws1.send_json({"type": "ping"})
                # ws1 получает и своё же message-эхо, и pong — читаем до pong
                got_pong = False
                for _ in range(3):
                    frame = ws1.receive_json()
                    if frame.get("type") == "pong":
                        got_pong = True
                        break
                check("WS: ping/pong", got_pong)
    except Exception as exc:  # noqa: BLE001
        check("WebSocket работает", False, repr(exc))

    r = client.get(f"/api/chats/{event_room}/messages", headers=h1)
    ws_saved = any(m["text"] == "Сообщение через WebSocket" for m in r.json()["items"])
    check("WS-сообщение сохранено в БД", ws_saved, r.text[:200])

    print("\n=== УДАЛЕНИЕ ===")
    r = client.delete(f"/api/cars/{car2['id']}", headers=h1)
    check("Удаление машины", r.status_code == 200, r.text)

    r = client.get("/api/cars/my", headers=h1)
    check("В гараже осталась 1 машина", r.json()["cars_count"] == 1, r.text)
    check("Оставшаяся стала основной", r.json()["cars"][0]["is_primary"] is True, r.text)

    r = client.delete(f"/api/events/{event2['id']}", headers=h2)
    check("Отмена сходки", r.status_code == 200, r.text)

    r = client.get("/api/events/", params={"event_type": "drift"})
    check("Отменённая сходка скрыта", r.json()["total"] == 0, r.text)

    print("\n" + "=" * 55)
    print(f"ПРОЙДЕНО: {PASSED}    ПРОВАЛЕНО: {FAILED}")
    print("=" * 55)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
