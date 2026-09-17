"""
Подключение к БД. Работает и с PostgreSQL, и с SQLite.
Инициализация ЛЕНИВА — не падает на импорте если БД недоступна.
"""
from sqlalchemy import create_engine, event as _sa_event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

DATABASE_URL = (settings.DATABASE_URL or "").strip()
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./carspot.db"

# Нормализация
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and "postgresql+psycopg2" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# Убираем TRAILING пробелы
DATABASE_URL = DATABASE_URL.rstrip()

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

try:
    engine = create_engine(
        DATABASE_URL,
        connect_args=_connect_args,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=settings.DEBUG,
    )
    
    # SQLite: Unicode lower()
    if DATABASE_URL.startswith("sqlite"):
        @_sa_event.listens_for(engine, "connect")
        def _register_unicode_lower(dbapi_connection, _record):
            dbapi_connection.create_function(
                "lower", 1, lambda value: value.lower() if isinstance(value, str) else value
            )
except Exception as e:
    print(f"[DB] Ошибка создания engine: {e}")
    engine = None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None
Base = declarative_base()


def get_db():
    if not engine or not SessionLocal:
        raise RuntimeError("Database not initialized")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> bool:
    if not engine:
        print("[DB] Engine не инициализирован")
        return False
    try:
        from app import models
        Base.metadata.create_all(bind=engine)
        print("[DB] Таблицы готовы")
        return True
    except Exception as exc:
        print(f"[DB] Ошибка init_db: {exc}")
        return False


def db_is_alive() -> bool:
    if not engine:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
