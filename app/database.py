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
# Убираем двойную схему если случайно добавилась
if DATABASE_URL.startswith("postgresql:postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql:postgresql://", "postgresql+psycopg2://", 1)

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


def _existing_columns(conn, table: str) -> set:
    """Колонки, которые реально есть в таблице (а не в модели)."""
    if DATABASE_URL.startswith("sqlite"):
        return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
    return {
        row[0]
        for row in conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
            {"t": table},
        )
    }


def _ensure_columns() -> None:
    """
    Alembic здесь не используется, а Base.metadata.create_all() создаёт только
    ОТСУТСТВУЮЩИЕ таблицы — он никогда не добавляет новые колонки в таблицу,
    которая уже существует. Поэтому каждая новая nullable-колонка, добавленная
    в модель после первого деплоя, должна быть перечислена здесь — иначе она
    существует только в коде, а в реальной базе её не будет, и любой запрос
    к ней будет падать с ошибкой "column does not exist".
    """
    additions = [
        ("users", "referral_code", "VARCHAR(20)"),
        ("users", "referred_by_id", "VARCHAR(36)"),
        ("cars", "license_plate", "VARCHAR(20)"),
    ]
    try:
        with engine.connect() as conn:
            for table, column, coltype in additions:
                try:
                    if column in _existing_columns(conn, table):
                        continue
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
                    conn.commit()
                    print(f"[DB] Добавлена колонка {table}.{column}")
                except Exception as exc:
                    print(f"[DB] Не удалось добавить колонку {table}.{column}: {exc}")
                    conn.rollback()
    except Exception as exc:
        print(f"[DB] Ошибка _ensure_columns: {exc}")


def _backfill_referral_codes() -> None:
    """Выдаёт реферальный код каждому аккаунту, у которого его пока нет."""
    import random
    import re
    import string

    if not SessionLocal:
        return

    from app.models.user import User

    db = SessionLocal()
    try:
        users = db.query(User).filter(
            (User.referral_code.is_(None)) | (User.referral_code == "")
        ).all()
        if not users:
            return

        existing_codes = {
            row[0]
            for row in db.query(User.referral_code).filter(User.referral_code.isnot(None)).all()
        }

        for user in users:
            base = re.sub(r"[^A-Za-z0-9]", "", user.username or "USER").upper()[:10] or "USER"
            code = base
            attempts = 0
            while code in existing_codes:
                attempts += 1
                if attempts > 20:
                    code = f"{base}{random.randint(100000, 999999)}"[:20]
                    break
                suffix = "".join(random.choices(string.digits, k=4))
                code = f"{base}{suffix}"[:20]
            existing_codes.add(code)
            user.referral_code = code

        db.commit()
        print(f"[DB] Реферальные коды выданы {len(users)} аккаунтам")
    except Exception as exc:
        print(f"[DB] Ошибка _backfill_referral_codes: {exc}")
        db.rollback()
    finally:
        db.close()


def init_db() -> bool:
    if not engine:
        print("[DB] Engine не инициализирован")
        return False
    try:
        from app import models
        Base.metadata.create_all(bind=engine)
        _ensure_columns()
        _backfill_referral_codes()
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
