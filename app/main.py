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
* **Чаты** — личные, чаты сходок и клубов + WebSocket
* **Рейтинги** — оценки сходок, пользователей и спотов
* **Фото** — загрузка к сходкам и машинам, лайки

### Как авторизоваться в этой документации
1. Выполните `POST /api/auth/register` или `/api/auth/login`
2. Скопируйте `access_token` из ответа
3. Нажмите кнопку **Authorize** вверху справа и вставьте токен
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[APP] Запуск {settings.APP_NAME} v{settings.APP_VERSION}")

    # Инициализация БД не должна ронять приложение
    init_db()

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

from app.api import auth, cars, chats, clubs, events, photos, ratings, users  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["Авторизация"])
app.include_router(users.router, prefix="/api/users", tags=["Пользователи"])
app.include_router(cars.router, prefix="/api/cars", tags=["Мой Гараж"])
app.include_router(events.router, prefix="/api/events", tags=["Сходки"])
app.include_router(clubs.router, prefix="/api/clubs", tags=["Клубы"])
app.include_router(chats.router, prefix="/api/chats", tags=["Чаты"])
app.include_router(ratings.router, prefix="/api/ratings", tags=["Рейтинги"])
app.include_router(photos.router, prefix="/api/photos", tags=["Фото"])
