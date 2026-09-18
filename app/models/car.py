from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text

from app.database import Base
from app.models.base import new_id, utcnow


class Car(Base):
    """Автомобиль в гараже пользователя."""

    __tablename__ = "cars"

    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), index=True, nullable=False)

    # --- Основное ---
    make = Column(String(50), nullable=False)          # Nissan
    model = Column(String(50), nullable=False)         # Silvia S15
    year = Column(Integer, nullable=True)              # 1999
    generation = Column(String(50), nullable=True)     # S15
    body_type = Column(String(30), nullable=True)      # coupe / sedan / suv

    # --- Характеристики ---
    engine = Column(String(100), nullable=True)        # SR20DET 2.0 turbo
    engine_volume = Column(String(20), nullable=True)  # 2.0
    power_hp = Column(Integer, nullable=True)          # 450
    torque_nm = Column(Integer, nullable=True)         # 520
    drivetrain = Column(String(20), nullable=True)     # RWD / FWD / AWD
    transmission = Column(String(30), nullable=True)   # manual / automatic
    fuel_type = Column(String(20), nullable=True)      # petrol / diesel / electric
    weight_kg = Column(Integer, nullable=True)
    zero_to_hundred = Column(String(20), nullable=True)  # 4.2

    # --- Внешний вид и тюнинг ---
    color = Column(String(50), nullable=True)
    license_plate = Column(String(20), nullable=True)  # госномер
    mods = Column(Text, nullable=True)                 # список доработок текстом
    description = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=True)     # главное фото
    photos = Column(Text, nullable=True)               # доп. фото: URL через запятую

    # --- Флаги ---
    is_primary = Column(Boolean, default=False, nullable=False)   # показывается в профиле
    is_for_sale = Column(Boolean, default=False, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


Index("ix_cars_user_primary", Car.user_id, Car.is_primary)
