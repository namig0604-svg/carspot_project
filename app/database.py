"""
Подключение к базе данных.

Работает и с PostgreSQL (Railway / Docker), и с SQLite (локальная разработка).
Строка подключения берётся из DATABASE_URL.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


def _normalize_db_url(url: str) -> str:
    """Приводит строку подключения к виду, который понимает SQLAlchemy."""
    url = (url or "").strip()

    if not url:
        return "sqlite:///./carspot.db"

    # Railway/Heroku иногда отдают postgres:// — SQLAlchemy 2.0 такое не понимает
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return url


DATABASE_URL = _normalize_db_url(settings.DATABASE_URL)

# SQLite требует особый флаг для работы в многопоточном FastAPI
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,       # проверяет соединение перед использованием
    pool_recycle=1800,        # пересоздаёт соединения раз в 30 минут
    echo=settings.DEBUG,
)


# SQLite умеет приводить к нижнему регистру только латиницу, поэтому поиск
# по русским названиям без учёта регистра там не работает. Подменяем lower()
# на питоновский — тогда локальная разработка ведёт себя как PostgreSQL.
if DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event as _sa_event

    @_sa_event.listens_for(engine, "connect")
    def _register_unicode_lower(dbapi_connection, _record):  # pragma: no cover
        dbapi_connection.create_function(
            "lower", 1, lambda value: value.lower() if isinstance(value, str) else value
        )


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI-зависимость: сессия БД на один запрос."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> bool:
    """
    Создаёт все таблицы, которых ещё нет.
    Возвращает True при успехе. Не бросает исключение — приложение
    должно подниматься даже если БД временно недоступна.
    """
    try:
        # Импорт моделей обязателен: без него Base не знает о таблицах
        from app import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        print("[DB] Таблицы готовы")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[DB] Не удалось инициализировать БД: {exc}")
        return False


def db_is_alive() -> bool:
    """Быстрая проверка живости БД для /health."""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
