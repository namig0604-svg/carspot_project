"""
Полный сброс схемы базы данных.

Удаляет ВСЕ таблицы CarSpot и создаёт их заново по текущим моделям.
Нужен один раз после перехода на новую версию — старые таблицы
(с другими колонками) сами не переделаются.

ВНИМАНИЕ: все данные будут удалены.

Запуск локально:
    python reset_db.py

Запуск против Railway (публичная строка подключения из вкладки
Postgres -> Variables -> DATABASE_PUBLIC_URL):
    Windows CMD:
        set DATABASE_URL=postgresql://... && python reset_db.py
    PowerShell:
        $env:DATABASE_URL="postgresql://..."; python reset_db.py
"""
import sys

from sqlalchemy import inspect, text

from app.database import Base, engine
from app import models  # noqa: F401  — регистрирует все таблицы в Base

# Таблицы из прошлых версий проекта, которых больше нет в моделях
LEGACY_TABLES = [
    "photos_v2",
    "stories",
    "event_participants_old",
]


def main() -> int:
    url = str(engine.url)
    # Прячем пароль при выводе
    safe_url = url
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            creds, host = rest.split("@", 1)
            user = creds.split(":")[0]
            safe_url = f"{scheme}://{user}:***@{host}"

    print(f"База данных: {safe_url}")
    answer = input("Удалить все таблицы и создать заново? Введите 'yes': ").strip().lower()
    if answer != "yes":
        print("Отменено.")
        return 1

    print("\nУдаляю таблицы...")
    Base.metadata.drop_all(bind=engine)

    # Чистим таблицы, оставшиеся от старых версий
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in LEGACY_TABLES:
            if table in existing:
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                print(f"  удалена устаревшая таблица: {table}")

    print("Создаю таблицы заново...")
    Base.metadata.create_all(bind=engine)

    created = sorted(inspect(engine).get_table_names())
    print(f"\nГотово. Таблиц в базе: {len(created)}")
    for name in created:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
