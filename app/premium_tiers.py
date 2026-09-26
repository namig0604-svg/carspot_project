"""
Уровни CarSpot Premium: Basic, Pro и Max.

User.is_premium (bool) остаётся как есть — "подписка активна вообще"
(premium_until в будущем), полученная пробным периодом, рефералами или
покупкой. User.premium_tier — необязательное уточнение "какой именно план
активен" ("basic" | "pro" | "max"), которое трогают только настоящие
покупки (см. app/services.py::extend_premium). Пробный период и награда за
рефералов НЕ трогают premium_tier — поэтому если у пользователя нет явно
купленного плана, "эффективный" уровень считается Pro (щедрее, никого не
понижает задним числом, когда добавили тарифы).

Примечание про имена настроек: тариф называется "Max", но в Python-именах
настроек используется префикс ULTRA (settings.PREMIUM_ULTRA_*), чтобы не
путать с уже существующим PREMIUM_MAX_CARS_PER_USER ("максимум машин для
Pro" — это имя осталось от одноуровневого Premium и трогать его рискованно,
он завязан на переменные окружения на Railway).
"""
from app.config import settings

TIER_BASIC = "basic"
TIER_PRO = "pro"
TIER_MAX = "max"
ALL_TIERS = (TIER_BASIC, TIER_PRO, TIER_MAX)

TIER_TITLES_RU = {
    TIER_BASIC: "CarSpot Basic",
    TIER_PRO: "CarSpot Pro",
    TIER_MAX: "CarSpot Max",
}


def effective_tier(user) -> str | None:
    """None — обычный пользователь без Premium вообще."""
    if not getattr(user, "is_premium", False):
        return None
    return getattr(user, "premium_tier", None) or TIER_PRO


def car_limit(user) -> int:
    tier = effective_tier(user)
    if tier == TIER_MAX:
        return settings.PREMIUM_ULTRA_MAX_CARS_PER_USER
    if tier == TIER_PRO:
        return settings.PREMIUM_MAX_CARS_PER_USER
    if tier == TIER_BASIC:
        return settings.PREMIUM_BASIC_MAX_CARS_PER_USER
    return settings.MAX_CARS_PER_USER


def insights_limit(user) -> int:
    """Сколько строк отдавать в 'кто лайкнул' / 'кто смотрел профиль'. 0 = нет доступа."""
    tier = effective_tier(user)
    if tier == TIER_MAX:
        return settings.PREMIUM_ULTRA_INSIGHTS_LIMIT
    if tier == TIER_PRO:
        return settings.PREMIUM_INSIGHTS_LIMIT
    if tier == TIER_BASIC:
        return settings.PREMIUM_BASIC_INSIGHTS_LIMIT
    return 0


def can_view_insights(user) -> bool:
    return effective_tier(user) is not None


def can_pin_photo(user) -> bool:
    """Закрепление фото в начало галереи — Pro и Max."""
    return effective_tier(user) in (TIER_PRO, TIER_MAX)


def can_create_business(user) -> bool:
    return effective_tier(user) is not None


def max_businesses(user) -> int:
    tier = effective_tier(user)
    if tier == TIER_MAX:
        return settings.PREMIUM_ULTRA_MAX_BUSINESSES
    if tier == TIER_PRO:
        return settings.PREMIUM_PRO_MAX_BUSINESSES
    if tier == TIER_BASIC:
        return settings.PREMIUM_BASIC_MAX_BUSINESSES
    return 0


def gets_free_boost(user) -> bool:
    """Бесплатный буст сходки/автосервиса/профиля в топ — Pro и Max."""
    return effective_tier(user) in (TIER_PRO, TIER_MAX)


def boost_duration_hours(user) -> int:
    """Сколько часов держится буст — у Max вдвое дольше, чем у остальных."""
    if effective_tier(user) == TIER_MAX:
        return settings.PREMIUM_ULTRA_BOOST_DURATION_HOURS
    return settings.BOOST_DURATION_HOURS


def purchase_bonus_xp_for_tier(tier: str | None) -> int:
    """Бонусный XP при оплате/продлении — растёт по тарифу (см. app/api/payments.py)."""
    if tier == TIER_MAX:
        return settings.PREMIUM_ULTRA_PURCHASE_BONUS_XP
    if tier == TIER_PRO:
        return settings.PREMIUM_PRO_PURCHASE_BONUS_XP
    if tier == TIER_BASIC:
        return settings.PREMIUM_BASIC_PURCHASE_BONUS_XP
    return 0


def purchase_bonus_coins_for_tier(tier: str | None) -> int:
    """Бонусные монеты CarSpot Coin при оплате/продлении — растут по тарифу."""
    if tier == TIER_MAX:
        return settings.PREMIUM_ULTRA_PURCHASE_BONUS_COINS
    if tier == TIER_PRO:
        return settings.PREMIUM_PRO_PURCHASE_BONUS_COINS
    if tier == TIER_BASIC:
        return settings.PREMIUM_BASIC_PURCHASE_BONUS_COINS
    return 0


def status_name_color_hex(tier: str | None) -> str | None:
    """
    Цвет ника в списках/чатах по тарифу — статусная плюшка, которую видят
    остальные пользователи (см. UserPublic.premium_tier). None — обычный
    пользователь, цвет не переопределяется на клиенте.
    """
    if tier == TIER_MAX:
        return "#8E24AA"  # фиолетовый — топ-уровень
    if tier == TIER_PRO:
        return "#F9A825"  # золотой
    if tier == TIER_BASIC:
        return "#42A5F5"  # голубой
    return None
