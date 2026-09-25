"""
CarSpot Coins — внутренняя валюта. Журнал начислений и списаний монет:
нужен пользователю для истории операций и серверу — для идемпотентности
покупок (уникальный purchase_token не даёт зачислить один и тот же чек
из Google Play дважды).
"""
from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base
from app.models.base import new_id, utcnow


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"

    id = Column(String(36), primary_key=True, default=new_id)
    user_id = Column(String(36), index=True, nullable=False)

    # Положительное — начисление (покупка, бонус), отрицательное — списание (буст).
    amount = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)

    # "purchase" | "boost_event" | "boost_business" | "admin_grant" ...
    type = Column(String(30), nullable=False)
    reference_id = Column(String(36), nullable=True)  # id сходки/автосервиса/платежа

    # Только для type="purchase" через Google Play — уникален, чтобы один и
    # тот же чек нельзя было прислать повторно и получить монеты дважды.
    purchase_token = Column(String(300), unique=True, index=True, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
