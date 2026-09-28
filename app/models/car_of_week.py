from sqlalchemy import Column, DateTime, Index, Integer, String, UniqueConstraint

from app.database import Base
from app.models.base import new_id, utcnow


def week_key(dt=None) -> str:
    """
    ISO-неделя в формате "2026-W39" — используется и как ключ группировки
    заявок, и как параметр week в GET-ручках (по умолчанию — текущая
    неделя). ISO-неделя начинается с понедельника, что не всегда совпадает
    с григорианским годом на стыке декабря/января — это ожидаемо и не
    страшно, ключ всё равно используется только для группировки.
    """
    d = dt or utcnow()
    iso = d.isocalendar()  # (year, week, weekday)
    return f"{iso[0]}-W{iso[1]:02d}"


class CarOfWeekEntry(Base):
    """
    Заявка на голосование «Машина недели» — одна машина пользователя,
    выставленная на голосование в конкретную неделю. Один пользователь
    может выставить не больше одной заявки за неделю (см.
    UniqueConstraint ниже), но может участвовать в разные недели.
    """

    __tablename__ = "car_of_week_entries"
    __table_args__ = (
        UniqueConstraint("week_key", "user_id", name="uq_car_of_week_entry_user_week"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    week_key = Column(String(10), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)
    car_id = Column(String(36), index=True, nullable=False)

    # Денормализованный счётчик — обновляется в момент голосования (см.
    # app/api/car_of_week.py), чтобы не считать COUNT(*) на каждый GET.
    votes_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)


Index("ix_car_of_week_entries_week_votes", CarOfWeekEntry.week_key, CarOfWeekEntry.votes_count)


class CarOfWeekVote(Base):
    """Голос пользователя за заявку — один голос на пользователя на заявку."""

    __tablename__ = "car_of_week_votes"
    __table_args__ = (
        UniqueConstraint("entry_id", "voter_id", name="uq_car_of_week_vote"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    entry_id = Column(String(36), index=True, nullable=False)
    voter_id = Column(String(36), index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
