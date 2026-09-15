from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import NullPool
from app.config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool if settings.DATABASE_URL.startswith("sqlite") else None
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ЕДИНЫЙ Base ДЛЯ ВСЕХ МОДЕЛЕЙ
Base = declarative_base()

def get_db() -> Session:
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database — create all tables"""
    # 1. Подключаем расширение pg_trgm (для PostgreSQL)
    if engine.url.drivername.startswith("postgresql"):
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            conn.commit()

    # 2. Импортируем все модели, чтобы SQLAlchemy зарегистрировала их в едином Base.metadata
    from app.models.user import User  # noqa
    from app.models.event import Event  # noqa
    from app.models.photo import Photo  # noqa
    from app.models.rating import EventRating, UserRating, SpotRating  # noqa

    # 3. Создаём все таблицы одним вызовом
    Base.metadata.create_all(bind=engine)
