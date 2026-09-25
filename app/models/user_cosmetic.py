"""
Куплена ли косметика CarSpot Coins (рамки аватара, значки, цвета имени) —
предмет покупается один раз и остаётся у пользователя навсегда, а какой
из купленных предметов сейчас надет — хранится отдельно на User
(equipped_frame / equipped_badge / equipped_name_color), по одному предмету
на слот, чтобы не плодить отдельную таблицу "текущая экипировка".
"""
from sqlalchemy import Column, DateTime, String, UniqueConstraint

from app.database import Base
from app.models.base import new_id, utcnow


class UserCosmetic(Base):
    __tablename__ = "user_cosmetics"
    __table_args__ = (
        UniqueConstraint("user_id", "cosmetic_id", name="uq_user_cosmetic"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), index=True, nullable=False)
    cosmetic_id = Column(String(40), nullable=False)  # id из каталога в app/api/coins.py
    purchased_at = Column(DateTime, default=utcnow, nullable=False)
