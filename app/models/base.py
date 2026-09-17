"""Общие помощники для моделей."""
import uuid
from datetime import datetime, timezone


def new_id() -> str:
    """Первичный ключ — UUID4 строкой (удобно для мобильных клиентов)."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Текущее время UTC без tzinfo (единообразно для SQLite и Postgres)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
