"""
Сезонные челленджи — ограниченные по времени задания с наградой (XP/монеты/
косметический бейдж), поверх уже существующих счётчиков активности
(events_attended, events_created, cars_count, ratings_count — тех же, что
клиент использует для расчёта уровня в app/utils/gamification.dart).

Прогресс НЕ пересчитывается из истории задним числом — он инкрементируется
точечно в момент самого действия (см. increment_challenge_progress в
app/services.py и её вызовы в app/api/events.py, cars.py, ratings.py), как
и остальные счётчики в этом проекте (events_attended и т.п.).
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint

from app.database import Base
from app.models.base import new_id, utcnow

# Метрика, по которой считается прогресс. Каждому значению соответствует
# конкретный хук в API — см. increment_challenge_progress().
GOAL_TYPES = (
    "attend_events",
    "create_events",
    "add_cars",
    "rate_events",
)


class Challenge(Base):
    """Сезонный челлендж. Создаётся администрацией через POST /api/challenges."""

    __tablename__ = "challenges"

    id = Column(String(36), primary_key=True, default=new_id)

    title = Column(String(200), nullable=True)  # необязательный человеко-читаемый ярлык для админки

    goal_type = Column(String(30), nullable=False)
    target = Column(Integer, nullable=False)

    xp_reward = Column(Integer, nullable=False, default=0)
    coin_reward = Column(Integer, nullable=False, default=0)
    badge_key = Column(String(60), nullable=True)

    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)

    # Ручной выключатель — не завязан на даты, чтобы можно было досрочно
    # снять челлендж с публикации, не трогая уже сохранённый прогресс.
    is_active = Column(Boolean, default=True, nullable=False)

    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ChallengeProgress(Base):
    """Прогресс конкретного пользователя по конкретному челленджу."""

    __tablename__ = "challenge_progress"
    __table_args__ = (
        UniqueConstraint("challenge_id", "user_id", name="uq_challenge_progress"),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    challenge_id = Column(String(36), index=True, nullable=False)
    user_id = Column(String(36), index=True, nullable=False)

    progress = Column(Integer, nullable=False, default=0)
    completed_at = Column(DateTime, nullable=True)
    reward_claimed_at = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
