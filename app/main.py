"""
CarSpot API — приложение для автомобильных сходок в странах СНГ.

Запуск локально:
    uvicorn app.main:app --reload

Документация: /docs
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import db_is_alive, init_db

DESCRIPTION = """
API для поиска и организации автомобильных сходок.

### Возможности
* **Авторизация** — регистрация, вход, JWT
* **Профиль** — данные пользователя, рейтинг, статистика
* **Мой Гараж** — автомобили с полными характеристиками
* **Сходки** — создание, карта, поиск рядом, участники
* **Клубы** — создание, вступление, роли, события клуба
* **Автосервисы и ателье** — каталог, карта рядом, отзывы, избранное
* **Чаты** — личные, чаты сходок и клубов + WebSocket
* **Друзья** — заявки в друзья, список друзей
* **Уведомления** — лента событий: заявки, лайки, участие в сходках, комментарии
* **Комментарии** — обсуждение сходок и фото
* **Платежи** — оплата Premium через Trybit (крипто-эквайринг для СНГ)
* **Рейтинги** — оценки сходок, пользователей и спотов
* **Фото** — загрузка к сходкам и машинам, лайки
* **Жалобы и модерация** — жалобы на пользователей/контент, блокировка (для админов)

### Как авторизоваться в этой документации
1. Выполните `POST /api/auth/register` или `/api/auth/login`
2. Скопируйте `access_token` из ответа
3. Нажмите кнопку **Authorize** вверху справа и вставьте токен
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[APP] Запуск {settings.APP_NAME} v{settings.APP_VERSION}")

    # Инициализация БД не должна ронять приложение
    init_db()  # ← ЭТА СТРОКА ДОЛЖНА БЫТЬ

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    print("[APP] Готово к работе")
    yield
    print("[APP] Остановка")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Раздача загруженных фото (папку создаём заранее, иначе StaticFiles упадёт)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Веб-версия приложения (flutter build web) — тестовый доступ с любого
# устройства и браузера, включая iOS, без установки APK.
if os.path.isdir("web_static"):
    app.mount("/app", StaticFiles(directory="web_static", html=True), name="webapp")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Любая необработанная ошибка возвращает JSON, а не падение процесса."""
    print(f"[ERROR] {request.method} {request.url.path}: {exc!r}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера"},
    )


# ─────────────────────────── СЛУЖЕБНЫЕ РУЧКИ ───────────────────────────

@app.get("/", tags=["Служебное"], summary="Проверка работы")
def root():
    return {
        "message": "CarSpot API is running",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["Служебное"], summary="Health check")
def health():
    """Проверка живости сервиса и базы данных."""
    database_ok = db_is_alive()
    return {
        "status": "ok",
        "database": "ok" if database_ok else "unavailable",
        "version": settings.APP_VERSION,
    }


# ─────────────────────────── РОУТЕРЫ ───────────────────────────

from app.api import (  # noqa: E402
    admin,
    auth,
    bookings,
    businesses,
    cars,
    chats,
    clubs,
    comments,
    events,
    forum,
    friends,
    location,
    notifications,
    payments,
    photos,
    ratings,
    reports,
    stories,
    users,
)
from app.api import (  # noqa: E402
    parking,
    maintenance,
    car_documents,
    car_expenses,
    hazards,
    part_listings,
    carpool,
)

app.include_router(auth.router, prefix="/api/auth", tags=["Авторизация"])
app.include_router(users.router, prefix="/api/users", tags=["Пользователи"])
app.include_router(cars.router, prefix="/api/cars", tags=["Мой Гараж"])
app.include_router(events.router, prefix="/api/events", tags=["Сходки"])
app.include_router(clubs.router, prefix="/api/clubs", tags=["Клубы"])
app.include_router(businesses.router, prefix="/api/businesses", tags=["Автосервисы"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["Онлайн-запись"])
app.include_router(chats.router, prefix="/api/chats", tags=["Чаты"])
app.include_router(comments.router, prefix="/api/comments", tags=["Комментарии"])
app.include_router(friends.router, prefix="/api/friends", tags=["Друзья"])
app.include_router(forum.router, prefix="/api/forum", tags=["Форум"])
app.include_router(location.router, prefix="/api/location", tags=["Геолокация"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Уведомления"])
app.include_router(payments.router, prefix="/api/payments", tags=["Платежи"])
app.include_router(ratings.router, prefix="/api/ratings", tags=["Рейтинги"])
app.include_router(photos.router, prefix="/api/photos", tags=["Фото"])
app.include_router(stories.router, prefix="/api/stories", tags=["Истории"])
app.include_router(reports.router, prefix="/api/reports", tags=["Жалобы"])
app.include_router(admin.router, prefix="/api/admin", tags=["Админка"])

app.include_router(parking.router, prefix="/api/parking", tags=["Парковка"])
app.include_router(maintenance.router, prefix="/api/maintenance", tags=["Сервисный дневник"])
app.include_router(car_documents.router, prefix="/api/car-documents", tags=["Документы авто"])
app.include_router(car_expenses.router, prefix="/api/car-expenses", tags=["Расходы на авто"])
app.include_router(hazards.router, prefix="/api/hazards", tags=["Дорожные опасности"])
app.include_router(part_listings.router, prefix="/api/part-listings", tags=["Барахолка"])
app.include_router(carpool.router, prefix="/api/carpool", tags=["Карпулинг"])
