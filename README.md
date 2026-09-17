# CarSpot API

Бэкенд приложения для автомобильных сходок в странах СНГ.

FastAPI + PostgreSQL + JWT. 52 эндпоинта, 14 таблиц, WebSocket-чаты.

---

## Возможности

| Раздел | Что умеет |
|---|---|
| **Авторизация** | Регистрация, вход по логину или email, JWT-токены, смена пароля |
| **Профиль** | Био, аватар, город, Instagram, рейтинг, статистика, поиск людей |
| **Мой Гараж** | До 10 машин с полными характеристиками, основная машина в профиле |
| **Сходки** | Создание, редактирование, отмена, фильтры, поиск, сортировки |
| **Карта** | Метки в границах экрана, поиск по радиусу с расчётом расстояния |
| **Участники** | Запись на сходку с выбором машины, лимиты, список участников |
| **Клубы** | Открытые и закрытые, заявки, роли, передача владения, события клуба |
| **Чаты** | Личные + автоматические чаты сходок и клубов, WebSocket в реальном времени |
| **Рейтинги** | Оценки сходок, пользователей и спотов, сводки с разбивкой по звёздам |
| **Фото** | Загрузка к сходкам и машинам, лайки, проверка формата и размера |

---

## Быстрый старт локально

```bash
# 1. Зависимости
pip install -r requirements.txt

# 2. Запуск (по умолчанию SQLite — база создастся сама)
uvicorn app.main:app --reload

# 3. Демо-данные (необязательно, но удобно для теста)
python seed_demo.py
```

Открыть: **http://localhost:8000/docs**

Демо-аккаунты после `seed_demo.py`: `namig`, `dato`, `aysel`, `giorgi` — пароль `Demo12345`.

### Через Docker

```bash
docker compose up --build
```

Поднимет PostgreSQL и API на порту 8000.

---

## Деплой на Railway

### Шаг 1. Переменные окружения

Сервис → **Variables**. Обязательные:

| Переменная | Значение |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `SECRET_KEY` | длинная случайная строка |

`DATABASE_URL` пишется **именно так, со скобками** — Railway сам подставит настоящую строку подключения. Если вписать её вручную, при пересоздании базы всё сломается.

Если сервис PostgreSQL называется не `Postgres`, подставьте его имя: `${{ИмяСервиса.DATABASE_URL}}`.

Необязательные: `ACCESS_TOKEN_EXPIRE_MINUTES`, `ALLOWED_ORIGINS`, `MAX_UPLOAD_SIZE`, `DEBUG`.

Переменную `PORT` задавать **не нужно** — Railway передаёт её сам.

### Шаг 2. Сброс старых таблиц

Если база уже использовалась прошлой версией проекта, в ней лежат таблицы с другими колонками. Автоматически они не переделаются — нужно один раз сбросить схему.

Скопируйте `DATABASE_PUBLIC_URL` из сервиса Postgres (вкладка Variables) и выполните локально:

```cmd
set DATABASE_URL=postgresql://postgres:ПАРОЛЬ@ХОСТ:ПОРТ/railway
python reset_db.py
```

PowerShell:

```powershell
$env:DATABASE_URL="postgresql://postgres:ПАРОЛЬ@ХОСТ:ПОРТ/railway"
python reset_db.py
```

Скрипт спросит подтверждение и пересоздаст все таблицы.

### Шаг 3. Деплой

```bash
git add -A
git commit -m "CarSpot API v1.0"
git push
```

Railway соберёт образ и запустит сервис. Проверка: `https://ваш-домен/health` должен вернуть

```json
{"status": "ok", "database": "ok", "version": "1.0.0"}
```

---

## Как авторизоваться в Swagger

1. `POST /api/auth/register` или `POST /api/auth/login`
2. Скопировать `access_token` из ответа
3. Кнопка **Authorize** вверху справа → вставить токен
4. Все защищённые эндпоинты станут доступны

Либо нажать **Authorize** сразу и ввести логин/пароль — форма `/api/auth/token` работает по стандарту OAuth2.

---

## Справочник API

Базовый адрес: `https://ваш-домен`

### Авторизация — `/api/auth`

| Метод | Путь | Описание |
|---|---|---|
| POST | `/register` | Регистрация, сразу возвращает токен |
| POST | `/login` | Вход по username или email (JSON) |
| POST | `/token` | Вход form-data, для кнопки Authorize |
| GET | `/me` | Мой профиль |
| POST | `/change-password` | Смена пароля |

### Пользователи — `/api/users`

| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | Поиск: `?q=&country=&city=` |
| PATCH | `/me` | Обновить свой профиль |
| GET | `/{user_id}` | Публичный профиль |
| GET | `/{user_id}/cars` | Гараж пользователя |
| GET | `/{user_id}/events` | Созданные сходки |
| GET | `/{user_id}/attending` | Куда идёт |

### Мой Гараж — `/api/cars`

| Метод | Путь | Описание |
|---|---|---|
| GET | `/my` | Мой гараж |
| POST | `/` | Добавить машину |
| GET | `/{car_id}` | Карточка машины |
| PATCH | `/{car_id}` | Изменить |
| POST | `/{car_id}/primary` | Сделать основной |
| DELETE | `/{car_id}` | Удалить |

Поля машины: `make`, `model`, `year`, `generation`, `body_type`, `engine`, `engine_volume`, `power_hp`, `torque_nm`, `drivetrain`, `transmission`, `fuel_type`, `weight_kg`, `zero_to_hundred`, `color`, `mods`, `description`, `photo_url`, `is_primary`, `is_for_sale`.

### Сходки — `/api/events`

| Метод | Путь | Описание |
|---|---|---|
| POST | `/` | Создать |
| GET | `/` | Список: `?event_type=&city=&country=&club_id=&search=&sort=&limit=&offset=` |
| GET | `/map` | Метки карты: `?min_lat=&max_lat=&min_lon=&max_lon=` |
| GET | `/nearby` | Рядом: `?latitude=&longitude=&radius_km=` |
| GET | `/{event_id}` | Карточка |
| PATCH | `/{event_id}` | Изменить (только создатель) |
| DELETE | `/{event_id}` | Отменить |
| POST | `/{event_id}/join` | Пойду (можно указать `car_id`) |
| POST | `/{event_id}/leave` | Не пойду |
| GET | `/{event_id}/participants` | Участники |

Типы сходок: `meetup`, `racing`, `drift`, `drag`, `offroad`, `show`, `cruise`, `track_day`, `charity`, `other`.

Сортировка `sort`: `date` (по умолчанию), `popular`, `rating`, `new`.

### Клубы — `/api/clubs`

| Метод | Путь | Описание |
|---|---|---|
| POST | `/` | Создать |
| GET | `/` | Список: `?q=&country=&city=` |
| GET | `/my` | Мои клубы |
| GET | `/{club_id}` | Карточка |
| PATCH | `/{club_id}` | Изменить (owner/admin) |
| POST | `/{club_id}/join` | Вступить или подать заявку |
| POST | `/{club_id}/leave` | Выйти |
| GET | `/{club_id}/members` | Участники: `?member_status=approved\|pending` |
| POST | `/{club_id}/members/{user_id}/approve` | Одобрить заявку |
| PATCH | `/{club_id}/members/{user_id}/role` | Сменить роль |
| DELETE | `/{club_id}/members/{user_id}` | Исключить |
| GET | `/{club_id}/events` | События клуба |

Закрытый клуб (`is_public: false`) принимает по заявкам. Владелец не может выйти — сначала передаёт владение через смену роли на `owner`.

### Чаты — `/api/chats`

| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | Мои чаты |
| POST | `/direct` | Открыть личный чат |
| GET | `/{room_id}` | Инфо о чате и участники |
| GET | `/{room_id}/messages` | История |
| POST | `/{room_id}/messages` | Отправить |
| DELETE | `/{room_id}/messages/{message_id}` | Удалить своё |
| POST | `/{room_id}/read` | Отметить прочитанным |
| WS | `/ws/{room_id}?token=JWT` | Реальное время |

Чаты сходок и клубов создаются автоматически. При записи на сходку пользователь добавляется в её чат, при выходе — удаляется.

**WebSocket.** Подключение: `wss://домен/api/chats/ws/{room_id}?token=ВАШ_JWT`

Отправка:
```json
{"text": "привет"}
{"type": "typing"}
{"type": "ping"}
```

Приём:
```json
{"type": "message",  "data": {"id": "...", "user_id": "...", "username": "...", "text": "...", "created_at": "..."}}
{"type": "presence", "data": {"user_id": "...", "username": "...", "status": "online"}}
{"type": "typing",   "data": {"user_id": "...", "username": "..."}}
{"type": "pong"}
```

### Рейтинги — `/api/ratings`

| Метод | Путь | Описание |
|---|---|---|
| POST | `/events` | Оценить сходку (повторная оценка обновляет прежнюю) |
| GET | `/events/{event_id}` | Отзывы |
| GET | `/events/{event_id}/summary` | Средняя + разбивка по звёздам |
| POST | `/users` | Оценить пользователя |
| GET | `/users/{user_id}` | Отзывы о человеке |
| GET | `/users/{user_id}/summary` | Сводка |
| POST | `/spots` | Оценить место |
| GET | `/spots` | Оценки спотов: `?event_id=` |

Средние значения пересчитываются автоматически и попадают в карточки сходок и профили.

### Фото — `/api/photos`

| Метод | Путь | Описание |
|---|---|---|
| POST | `/upload` | Загрузить (multipart: `file`, `event_id` или `car_id`, `caption`) |
| GET | `/event/{event_id}` | Фото сходки |
| GET | `/car/{car_id}` | Фото машины |
| POST | `/{photo_id}/like` | Лайк / снять лайк |
| DELETE | `/{photo_id}` | Удалить своё |

Файлы отдаются по `/uploads/<имя>`. Форматы: JPEG, PNG, WebP, HEIC. Лимит 10 МБ.

> **Важно про фото на Railway.** Диск контейнера эфемерный: после передеплоя загруженные файлы пропадут. Для продакшена подключите S3 или Cloudinary — достаточно переписать функцию `_save_file()` в `app/api/photos.py`, остальной код менять не придётся.

---

## Структура проекта

```
app/
  main.py          точка входа, подключение роутеров
  config.py        настройки из переменных окружения
  database.py      движок, сессия, Base, init_db
  security.py      bcrypt и JWT
  deps.py          текущий пользователь, пагинация
  services.py      общая логика: чаты, пересчёт рейтингов
  ws_manager.py    менеджер WebSocket-соединений
  models/          таблицы SQLAlchemy
  schemas/         Pydantic-схемы запросов и ответов
  api/             роутеры
  utils/geo.py     гаверсинус и bounding box
tests/
  test_full_flow.py  сквозной тест (117 проверок)
reset_db.py        пересоздание схемы
seed_demo.py       демо-данные
```

---

## Тесты

```bash
python tests/test_full_flow.py
```

Прогоняет весь путь: регистрация → гараж → сходка → карта → участие → рейтинги → клубы → чаты → WebSocket → фото → удаление. Работает на отдельной базе `test_carspot.db`, ничего не ломает.

---

## Заметки для iOS

**Хранение токена.** `access_token` живёт 7 дней. Держите его в Keychain, добавляйте в каждый запрос заголовок `Authorization: Bearer <token>`. На `401` — отправляйте пользователя на экран входа.

**Карта.** При движении карты берите `region` и запрашивайте `/api/events/map` с границами:

```swift
let sw = mapView.region.southWest, ne = mapView.region.northEast
// GET /api/events/map?min_lat=&max_lat=&min_lon=&max_lon=
```

Для экрана «рядом со мной» — `/api/events/nearby` с координатами из CoreLocation, сервер вернёт `distance_km` и отсортирует по близости.

**Модели.** Все ответы — плоский JSON с `id` в виде строки UUID, даты в ISO 8601. Структуры `Codable` мапятся один в один со схемами из `/docs`.

**Чат.** `URLSessionWebSocketTask` на `/api/chats/ws/{room_id}?token=...`. Историю грузите через REST, новые сообщения — из сокета. Раз в 30 секунд шлите `{"type":"ping"}`, чтобы соединение не закрылось.

**Пагинация.** Везде `?limit=&offset=`, максимум 200 записей за раз.

---

## Что стоит добавить дальше

- Push-уведомления (APNs) на новые сообщения и напоминания о сходках
- Хранение фото в S3/Cloudinary вместо локального диска
- Refresh-токены вместо длинного access-токена
- Redis для WebSocket при масштабировании на несколько инстансов
- Модерация: жалобы на сходки, фото и пользователей
