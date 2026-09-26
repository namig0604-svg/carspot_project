"""
Автоматическая верификация аккаунта (синяя галочка User.is_verified) —
без ручной проверки документов и без SMS-подтверждения номера. Критерии
чисто по активности внутри самого приложения:
  - аккаунт не совсем свежий (VERIFICATION_MIN_ACCOUNT_AGE_DAYS);
  - пользователь реально ходит на сходки (events_attended >= порога);
  - аккаунт не забанен;
  - на пользователя нет ни одной ПОДТВЕРЖДЁННОЙ (status="resolved")
    жалобы — dismissed-жалобы не считаются, это защита от накрутки
    ложными жалобами конкурентов/недоброжелателей.

Пересчитывается точечно в местах, которые двигают эти признаки (не
периодической задачей, чтобы не заводить отдельный scheduler):
  - создание/вступление/выход/отмена сходки — app/api/events.py;
  - бан/разбан, рассмотрение жалобы — app/api/admin.py.
Плюс лениво при чтении своего профиля (app/api/users.py), чтобы галочка
появлялась сама по себе, когда истёк VERIFICATION_MIN_ACCOUNT_AGE_DAYS —
это единственный из критериев, который не завязан ни на одно действие
пользователя.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.base import utcnow
from app.models.report import Report
from app.models.user import User


def should_be_verified(db: Session, user: User) -> bool:
    if not user.is_active:
        return False

    if (user.events_attended or 0) < settings.VERIFICATION_MIN_EVENTS_ATTENDED:
        return False

    if not user.created_at:
        return False
    age_days = (utcnow() - user.created_at).days
    if age_days < settings.VERIFICATION_MIN_ACCOUNT_AGE_DAYS:
        return False

    has_upheld_report = (
        db.query(Report.id)
        .filter(
            Report.target_type == "user",
            Report.target_id == user.id,
            Report.status == "resolved",
        )
        .first()
        is not None
    )
    if has_upheld_report:
        return False

    return True


def recompute_is_verified(db: Session, user: Optional[User]) -> None:
    """
    Пересчитывает user.is_verified и молча правит его при расхождении —
    может как выдать галочку, так и снять её (например, если подтвердили
    жалобу на уже верифицированного пользователя, или его забанили).
    Не делает commit — вызывающий код в местах, откуда это вызывается,
    и так коммитит следом в рамках своей транзакции.
    """
    if not user:
        return
    # should_be_verified запрашивает Report отдельным SELECT — сессия здесь
    # всюду с autoflush=False (см. app/database.py), поэтому только что
    # изменённый в этой же транзакции report.status ("resolved" при
    # рассмотрении жалобы) иначе не будет виден этому запросу, пока не
    # случится commit. flush() делает его видимым сразу, не коммитя
    # транзакцию целиком раньше времени.
    db.flush()
    new_value = should_be_verified(db, user)
    if user.is_verified != new_value:
        user.is_verified = new_value
