# CarSpot - Приложение для автомобильных сходок

Приложение для отмечания и посещения автомобильных сходок в странах СНГ.

## Структура проекта

```
carspot-backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── event.py
│   │   ├── photo.py
│   │   └── rating.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── event.py
│   │   ├── photo.py
│   │   └── rating.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── users.py
│   │   ├── events.py
│   │   ├── photos.py
│   │   ├── ratings.py
│   │   └── map.py
│   └── utils/
│       ├── __init__.py
│       ├── auth.py
│       └── validators.py
├── requirements.txt
├── .env
└── docker-compose.yml

carspot-ios/
├── CarSpot/
│   ├── ContentView.swift
│   ├── Views/
│   ├── Models/
│   ├── Services/
│   └── Utils/
```

## Стек технологий

**Бэкенд:**
- Python 3.11+
- FastAPI
- PostgreSQL
- SQLAlchemy ORM
- JWT для аутентификации

**Фронтенд iOS:**
- Swift 5.9+
- SwiftUI
- MapKit / Яндекс.Карты SDK
- Networking с async/await

## Минимальный функционал MVP

✅ Карта со стилизацией (чёрный, синий, красный)
✅ Светлая и тёмная тема
✅ Отмечать место сходки, время, фотографии
✅ Оценки и описание к спотам
✅ Аутентификация пользователя

## Разработка

1. Установить зависимости
2. Настроить PostgreSQL
3. Запустить миграции
4. Запустить сервер
5. Запустить iOS приложение в Xcode

## Автор

CarSpot Team 2026
