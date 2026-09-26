"""
Настройки приложения.
Читаются из переменных окружения. Ничего не падает, если переменных нет —
используются значения по умолчанию (для локальной разработки).
"""
import os


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Settings:
    # --- Приложение ---
    APP_NAME: str = os.getenv("APP_NAME", "CarSpot API")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = _get_bool("DEBUG", False)

    # --- База данных ---
    # На Railway переменная DATABASE_URL должна быть задана как ${{Postgres.DATABASE_URL}}
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./carspot.db")

    # --- JWT ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production-please-32-chars-min")
    ALGORITHM: str = "HS256"
    # 7 дней по умолчанию — удобно для мобильного клиента
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7)

    # --- Загрузка файлов ---
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_UPLOAD_SIZE: int = _get_int("MAX_UPLOAD_SIZE", 10 * 1024 * 1024)  # 10 MB
    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}

    # --- CORS ---
    # "*" по умолчанию, чтобы iOS-приложение и Swagger работали сразу
    ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

    # --- Бизнес-лимиты ---
    MAX_CARS_PER_USER: int = _get_int("MAX_CARS_PER_USER", 10)
    DEFAULT_SEARCH_RADIUS_KM: float = float(os.getenv("DEFAULT_SEARCH_RADIUS_KM", "50"))

    # --- CarSpot Premium ---
    # Три уровня: Basic (дешевле, часть плюшек), Pro (был единственным
    # Premium раньше — тот же вход по цене, лимиты подняты) и Max (топ,
    # самые жирные лимиты + эксклюзивные плюшки). Существующие подписчики
    # Pro ничего не теряют — только выигрывают от поднятых лимитов.
    #
    # Лимиты по машинам/автосервисам сознательно НЕ огромные — реалистичные
    # числа (у людей не по 25-60 машин и не по 8-25 автосервисов на одном
    # аккаунте), это подстраховка от злоупотреблений, а не витрина Premium.
    # Основная ценность тарифов — ниже: бонус монет/XP при каждой оплате,
    # цветной статусный ник и приоритет в списке участников сходки.
    PREMIUM_MAX_CARS_PER_USER: int = _get_int("PREMIUM_MAX_CARS_PER_USER", 18)  # Pro
    PREMIUM_BASIC_MAX_CARS_PER_USER: int = _get_int("PREMIUM_BASIC_MAX_CARS_PER_USER", 12)
    PREMIUM_ULTRA_MAX_CARS_PER_USER: int = _get_int("PREMIUM_ULTRA_MAX_CARS_PER_USER", 25)  # тариф Max
    PREMIUM_TRIAL_DAYS: int = _get_int("PREMIUM_TRIAL_DAYS", 14)
    # За каждые REFERRALS_PER_PREMIUM_MONTH приглашённых друзей — PREMIUM_MONTH_DAYS Premium.
    REFERRALS_PER_PREMIUM_MONTH: int = _get_int("REFERRALS_PER_PREMIUM_MONTH", 10)
    PREMIUM_MONTH_DAYS: int = _get_int("PREMIUM_MONTH_DAYS", 30)
    # На сколько часов "буст" поднимает сходку/автосервис/профиль в топ. Для
    # Pro и Max бесплатно (см. app/premium_tiers.py::gets_free_boost) — у
    # Max ещё и вдвое дольше держится наверху.
    BOOST_DURATION_HOURS: int = _get_int("BOOST_DURATION_HOURS", 24)  # Pro
    PREMIUM_ULTRA_BOOST_DURATION_HOURS: int = _get_int("PREMIUM_ULTRA_BOOST_DURATION_HOURS", 48)  # Max
    # Сколько строк отдаём в списках "кто лайкнул" / "кто смотрел профиль".
    PREMIUM_INSIGHTS_LIMIT: int = _get_int("PREMIUM_INSIGHTS_LIMIT", 75)  # Pro (было 50)
    PREMIUM_BASIC_INSIGHTS_LIMIT: int = _get_int("PREMIUM_BASIC_INSIGHTS_LIMIT", 15)
    PREMIUM_ULTRA_INSIGHTS_LIMIT: int = _get_int("PREMIUM_ULTRA_INSIGHTS_LIMIT", 300)  # тариф Max
    # Сколько автосервисов/ателье может добавить один владелец — реалистично
    # мало (реальный бизнес редко держит больше 2-3 точек на одном аккаунте).
    PREMIUM_PRO_MAX_BUSINESSES: int = _get_int("PREMIUM_PRO_MAX_BUSINESSES", 2)
    PREMIUM_BASIC_MAX_BUSINESSES: int = _get_int("PREMIUM_BASIC_MAX_BUSINESSES", 1)
    PREMIUM_ULTRA_MAX_BUSINESSES: int = _get_int("PREMIUM_ULTRA_MAX_BUSINESSES", 3)  # тариф Max
    # Бонусный XP и монеты CarSpot Coin, которые начисляются при КАЖДОЙ
    # настоящей оплате/продлении тарифа (Trybit и Google Play — см.
    # app/api/payments.py), поверх обычного уровня, который считает фронтенд
    # (см. gamification.dart). Раньше был эксклюзивом тарифа Max — теперь
    # получают все три тарифа, суммы растут по тарифу.
    PREMIUM_BASIC_PURCHASE_BONUS_XP: int = _get_int("PREMIUM_BASIC_PURCHASE_BONUS_XP", 50)
    PREMIUM_PRO_PURCHASE_BONUS_XP: int = _get_int("PREMIUM_PRO_PURCHASE_BONUS_XP", 100)
    PREMIUM_ULTRA_PURCHASE_BONUS_XP: int = _get_int("PREMIUM_ULTRA_PURCHASE_BONUS_XP", 200)
    PREMIUM_BASIC_PURCHASE_BONUS_COINS: int = _get_int("PREMIUM_BASIC_PURCHASE_BONUS_COINS", 50)
    PREMIUM_PRO_PURCHASE_BONUS_COINS: int = _get_int("PREMIUM_PRO_PURCHASE_BONUS_COINS", 150)
    PREMIUM_ULTRA_PURCHASE_BONUS_COINS: int = _get_int("PREMIUM_ULTRA_PURCHASE_BONUS_COINS", 400)

    # --- Trybit (крипто-эквайринг для оплаты Premium, работает в СНГ) ---
    TRYBIT_SHOP_ID: str = os.getenv("TRYBIT_SHOP_ID", "")
    TRYBIT_API_KEY: str = os.getenv("TRYBIT_API_KEY", "")
    TRYBIT_SECRET_KEY: str = os.getenv("TRYBIT_SECRET_KEY", "")

    # --- Push-уведомления (Firebase Cloud Messaging) ---
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    # Весь JSON сервисного аккаунта одной строкой — Firebase Console →
    # Настройки проекта → Сервисные аккаунты → "Создать новый закрытый ключ",
    # содержимое скачанного файла целиком вставляем как значение
    # переменной окружения на Railway.
    FIREBASE_SERVICE_ACCOUNT_JSON: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")

    # --- Восстановление пароля (письмо с кодом через Gmail SMTP) ---
    # На Railway: включите двухфакторку на Gmail-аккаунте и создайте
    # "пароль приложения" (myaccount.google.com/apppasswords) — обычный
    # пароль от аккаунта тут не сработает. Если переменные не заданы,
    # письма просто не отправляются (не роняем приложение).
    GMAIL_ADDRESS: str = os.getenv("GMAIL_ADDRESS", "")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
    GMAIL_SENDER_NAME: str = os.getenv("GMAIL_SENDER_NAME", "CarSpot")
    PASSWORD_RESET_CODE_TTL_MINUTES: int = _get_int("PASSWORD_RESET_CODE_TTL_MINUTES", 30)

    # --- Импорт автосервисов из OpenStreetMap (Overpass API) ---
    OVERPASS_URL: str = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
    OVERPASS_TIMEOUT_SECONDS: int = _get_int("OVERPASS_TIMEOUT_SECONDS", 60)

    # --- Защита /docs и /redoc (Swagger/ReDoc) паролем ---
    # По умолчанию стоят значения ниже — поменяйте их в Railway
    # (переменные DOCS_USERNAME / DOCS_PASSWORD), иначе документация API
    # защищена, по сути, общеизвестным паролем.
    DOCS_USERNAME: str = os.getenv("DOCS_USERNAME", "carspot")
    DOCS_PASSWORD: str = os.getenv("DOCS_PASSWORD", "Kalicto300")

    # --- Google Play Billing (подписки CarSpot Premium через Play Store) ---
    # Настраивается в Google Play Console -> Настройка -> Доступ к API,
    # когда приложение туда попадёт (см. app/google_play_client.py).
    GOOGLE_PLAY_PACKAGE_NAME: str = os.getenv("GOOGLE_PLAY_PACKAGE_NAME", "com.carspot.app")
    GOOGLE_PLAY_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "")

    # --- CarSpot Coins (внутренняя валюта) ---
    # Сколько монет стоит поднять сходку/автосервис в топ, если у
    # пользователя нет CarSpot Premium (у Premium буст бесплатный, как и раньше).
    COIN_BOOST_COST_EVENT: int = _get_int("COIN_BOOST_COST_EVENT", 150)
    COIN_BOOST_COST_BUSINESS: int = _get_int("COIN_BOOST_COST_BUSINESS", 150)

    # --- Прокачка профиля за монеты: приоритет в поиске и бонусный XP ---
    # Буст поиска — та же механика, что у сходок/автосервисов (BOOST_DURATION_HOURS).
    COIN_COST_PROFILE_BOOST: int = _get_int("COIN_COST_PROFILE_BOOST", 150)
    # XP-бустер — разовая покупка: сразу даёт пачку опыта поверх уровня,
    # который приложение считает из реальной статистики (не таймер/множитель —
    # чтобы уровень не "откатывался" назад, когда действие боста заканчивается).
    COIN_COST_XP_BOOST: int = _get_int("COIN_COST_XP_BOOST", 200)
    XP_BOOST_GRANT_AMOUNT: int = _get_int("XP_BOOST_GRANT_AMOUNT", 300)
settings = Settings()
