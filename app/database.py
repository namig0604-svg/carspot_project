import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Получаем DATABASE_URL из переменных окружения Railway
database_url = os.getenv("DATABASE_URL")

if database_url:
    # Railway использует postgresql://, конвертируем в postgresql+psycopg2://
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
else:
    # Fallback для локального
    database_url = "postgresql+psycopg2://postgres:postgres@localhost:5432/carspot_db"

try:
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False
    )
except Exception as e:
    print(f"ERROR: Cannot create engine: {e}")
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️ Database init error: {e}")