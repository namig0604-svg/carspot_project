"""
Жалобы на пользователей и контент — базовая модерация.
Создаются пользователями через /api/reports, рассматриваются админом
через /api/admin (см. app.deps.require_admin).
"""
from sqlalchemy import Column, DateTime, String, Text

from app.database import Base
from app.models.base import new_id, utcnow

# На что можно пожаловаться.
REPORT_TARGET_TYPES = ("user", "event", "club", "business", "message", "photo")

# Причина жалобы.
REPORT_REASONS = ("spam", "abuse", "fake_profile", "inappropriate", "scam", "other")

# Статус рассмотрения.
REPORT_STATUSES = ("pending", "resolved", "dismissed")


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=new_id)

    reporter_id = Column(String(36), index=True, nullable=False)

    target_type = Column(String(20), index=True, nullable=False)
    target_id = Column(String(36), index=True, nullable=False)

    reason = Column(String(30), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(String(20), default="pending", nullable=False, index=True)
    resolved_by_id = Column(String(36), nullable=True)
    resolution_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
