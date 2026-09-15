# 🪟 Windows Setup - Полная инструкция

## ШАГИ ДЛЯ WINDOWS

### ШАГ 1: Что ты скачал
У тебя должны быть эти файлы и папки:

```
carspot_project/
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
│   │   └── rating.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── users.py
│   │   ├── events.py
│   │   └── ratings.py
│   └── utils/
│       ├── __init__.py
│       └── auth.py
├── CarSpot-iOS/
│   ├── ContentView.swift
│   ├── Models/
│   │   └── Models.swift
│   ├── Services/
│   │   ├── APIService.swift
│   │   └── AuthManager.swift
│   └── Views/
│       ├── AuthenticationView.swift
│       ├── MapView.swift
│       ├── EventsListView.swift
│       └── ProfileView.swift
├── requirements.txt
├── docker-compose.yml
├── .env
├── Dockerfile
└── INSTALLATION.md
```

### ШАГ 2: Проверь что установлено

Открой **Command Prompt** (нажми Win+R, введи `cmd`, нажми Enter)

```bash
python --version
# Должно вывести: Python 3.11.x или выше

docker --version
# Должно вывести: Docker version 20.10.x или выше
```

Если один из них не работает - вернись к этапу установки выше!

---

## ЭТАП 3: ЗАПУСК БЭКЕНДА

### ШАГ 3: Откройи Command Prompt в папке проекта

1. Открой File Explorer (Проводник)
2. Перейди в папку `C:\Users\YourUsername\CarSpot`
3. Нажми в адресной строке и замени путь на полный путь папки
4. Нажми Ctrl+L (выделит адресную строку)
5. Введи: `cmd`
6. Нажми Enter

**ИЛИ:**
1. Нажми Win+R
2. Введи: `cmd C:\Users\YourUsername\CarSpot`
3. Нажми Enter

---

### ШАГ 4: Запусти Docker Compose

В Command Prompt (в папке CarSpot) введи:

```bash
docker-compose up
```

**Ты увидишь много текста, это нормально!**

Жди пока не увидишь:
```
✅ Database initialized
✅ Uvicorn running on http://0.0.0.0:8000
```

---

### ШАГ 5: Проверь что бэкенд работает

Открой браузер и перейди на:

**http://localhost:8000/docs**

Если видишь красивую документацию API с кнопочками - ✅ **Всё работает!**

Оставь этот терминал открытым (не закрывай его)!

---

## ЭТАП 4: ЗАПУСК iOS ПРИЛОЖЕНИЯ

### ШАГ 6: Установи Xcode (только если у тебя Mac) ⚠️

**НА WINDOWS iOS ПРИЛОЖЕНИЕ НЕ ЗАПУСТИШЬ!**

Для тестирования на Windows используй:
- **Вариант 1:** Использовать соседский Mac
- **Вариант 2:** Запустить на реальном iPhone через облако
- **Вариант 3:** Использовать Android вместо iOS (можем переделать)

**Но ты можешь тестировать бэкенд полностью на Windows!**

---

## ЭТАП 5: ТЕСТИРОВАНИЕ БЭКЕНДА

### Тест 1: Регистрация пользователя

В браузере откройся на http://localhost:8000/docs

Нажми на **POST /api/users/register**

Нажми кнопку **"Try it out"**

Вставь этот текст в окно:
```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "test123456",
  "full_name": "Test User",
  "country": "Georgia",
  "city": "Tbilisi"
}
```

Нажми **Execute**

Ты должен увидеть ответ 200 с данными пользователя! ✅

---

### Тест 2: Вход в аккаунт

Найди **POST /api/users/login**

Нажми **"Try it out"**

Вставь:
```json
{
  "email": "test@example.com",
  "password": "test123456"
}
```

Нажми **Execute**

Ты получишь **access_token** - это твой токен доступа! ✅

---

### Тест 3: Создание события

Найди **POST /api/events/**

Нажми **"Try it out"**

Скопируй **access_token** из Теста 2

В Authentication (вверху страницы) выбери **Bearer Token**

Введи токен туда

Вставь в Request Body:
```json
{
  "title": "Friday Night Racing",
  "description": "Join us for an exciting racing event",
  "event_type": "racing",
  "country": "Georgia",
  "city": "Tbilisi",
  "location_name": "Tbilisi Center",
  "latitude": 41.7151,
  "longitude": 44.7671,
  "address": "Vake, Tbilisi",
  "event_date": "2024-12-20T20:00:00",
  "event_time": "20:00",
  "duration_minutes": 120
}
```

Нажми **Execute**

Ты создал событие! ✅

---

### Тест 4: Получение событий на карте

Найди **GET /api/events/map/nearby**

Нажми **"Try it out"**

Введи параметры:
- latitude: 41.7151
- longitude: 44.7671
- radius_km: 100
- country: Georgia

Нажми **Execute**

Увидишь событие которое создал! ✅

---

## КОМАНДЫ КОТОРЫЕ ПРИГОДЯТСЯ

### Остановить бэкенд
Нажми в Command Prompt: **Ctrl+C**

### Снова запустить
```bash
docker-compose up
```

### Очистить всё (если сломалось)
```bash
docker-compose down
docker system prune
docker-compose up --build
```

### Посмотреть логи бэкенда
Логи выводятся в тот же терминал где ты запустил `docker-compose up`

---

## СТРУКТУРА API

### Пользователи
```
POST   /api/users/register          Регистрация
POST   /api/users/login             Вход
GET    /api/users/me                Мой профиль
PUT    /api/users/me                Изменить профиль
GET    /api/users/{user_id}         Профиль другого юзера
```

### События
```
GET    /api/events/                 Список событий (с фильтрами)
POST   /api/events/                 Создать событие
GET    /api/events/{event_id}       Детали события
PUT    /api/events/{event_id}       Изменить событие
GET    /api/events/map/nearby       События на карте
POST   /api/events/{event_id}/join  Присоединиться
POST   /api/events/{event_id}/leave Покинуть
```

### Рейтинги
```
POST   /api/ratings/events          Оценить событие
GET    /api/ratings/events/{id}     Все оценки события
POST   /api/ratings/spots           Оценить место
GET    /api/ratings/spots/{id}      Все оценки места
POST   /api/ratings/users           Оценить пользователя
GET    /api/ratings/users/{id}      Все оценки пользователя
```

---

## ПРОБЛЕМЫ И РЕШЕНИЯ

### ❌ "Docker is not running"
**Решение:** Запусти Docker Desktop (поищи его в меню Start)

### ❌ "Port 5432 already in use"
**Решение:** 
```bash
docker ps
docker kill <container_id>
docker-compose up
```

### ❌ "Connection refused"
**Решение:** Убедись что бэкенд запущен (должен быть активный Command Prompt)

### ❌ "ModuleNotFoundError: No module named 'fastapi'"
**Решение:**
```bash
pip install -r requirements.txt
docker-compose up
```

### ❌ "ERROR: Couldn't connect to Docker daemon"
**Решение:** Запусти Docker Desktop и жди пока он полностью загрузится (2-3 минуты)

---

## СЛЕДУЮЩИЕ ШАГИ

После того как всё работает:

1. **Поиграйся с API** - создавай события, рейтинги, пользователей
2. **Понимай структуру** - смотри что возвращает каждый endpoint
3. **Добавляй функции:**
   - Загрузку фото
   - Систему платежей
   - WebSockets для real-time
4. **Деплой:**
   - Выложи на Railway.app (1 клик)
   - Или на AWS/DigitalOcean
5. **iOS:**
   - Попроси друга с Mac собрать приложение
   - Или переделаем на React Native для Windows/Android

---

**Готов начинать? Тогда идём на ШАГ 1!** 🚀
