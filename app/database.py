"""
Подключение к базе данных.

Работает и с PostgreSQL (Railway / Docker), и с SQLite (локальная разработка).
Строка подключения берётся из DATABASE_URL.
"""
from sqlalchemy import create_engine, event as _sa_event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


def _normalize_db_url(url: str) -> str:
    """Приводит строку подключения к виду, который понимает SQLAlchemy."""
    url = (url or "").strip()

    if not url:
        return "sqlite:///./carspot.db"

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return url


DATABASE_URL = _normalize_db_url(settings.DATABASE_URL)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=settings.DEBUG,
)

# SQLite: Unicode-aware lower()
if DATABASE_URL.startswith("sqlite"):
    @_sa_event.listens_for(engine, "connect")
    def _register_unicode_lower(dbapi_connection, _record):
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
    """Создаёт все таблицы, которых ещё нет."""
    try:
        from app import models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        print("[DB] Таблицы готовы")
        return True
    except Exception as exc:
        print(f"[DB] Не удалось инициализировать БД: {exc}")
        return False


def db_is_alive() -> bool:
    """Проверка живости БД для /health."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False