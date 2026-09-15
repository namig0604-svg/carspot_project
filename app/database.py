import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Получаем DATABASE_URL из окружения Railway
db_url = os.getenv("DATABASE_URL")

if not db_url:
    db_url = "postgresql://localhost/carspot_db"

# Конвертируем для psycopg2
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

print(f"[DB] Connecting to: {db_url[:50]}...")

engine = create_engine(db_url, pool_pre_ping=True)
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
        print("[DB] ✅ Database initialized")
    except Exception as e:
        print(f"[DB] ⚠️ Init error: {e}")