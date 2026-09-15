import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Используем переменную окружения DATABASE_URL (от Railway)
# Если не установлена - используем локальный PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://carspot_user:carspot_password@localhost:5432/carspot_db"
)

# Для Railway - заменяем postgresql:// на postgresql+psycopg2://
if "postgresql://" in DATABASE_URL and "postgresql+psycopg2://" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")

engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Создать все таблицы"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized")