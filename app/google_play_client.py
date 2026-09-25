"""
Проверка покупок Google Play (подписки CarSpot Premium через Google Play
Billing). Ключи берутся из переменных окружения Railway
(settings.GOOGLE_PLAY_PACKAGE_NAME / GOOGLE_PLAY_SERVICE_ACCOUNT_JSON) —
сюда их выставлять не нужно и не стоит. Тот же приём, что и в
app/push_client.py: сами подписываем self-signed JWT и меняем его на
access_token, без тяжёлой библиотеки google-auth.

Как настроить (сделать один раз в Google Play Console, когда дойдёт дело
до публикации):
1. Play Console -> Настройка -> Доступ к API -> привязать проект Google Cloud.
2. В этом проекте Google Cloud создать сервисный аккаунт -> скачать JSON-ключ.
3. В Play Console дать этому сервисному аккаунту права на просмотр
   финансовых данных / управление заказами (роль Finance).
4. Задать на Railway:
   GOOGLE_PLAY_PACKAGE_NAME=com.carspot.app
   GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=<содержимое скачанного файла целиком>
"""
import json
import time
from datetime import datetime, timezone
from typing import Optional

import jwt as pyjwt
import requests

from app.config import settings

_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_API_BASE = "https://androidpublisher.googleapis.com/androidpublisher/v3"

# Кэш access_token в памяти процесса — не запрашиваем новый на каждую проверку,
# он живёт ~1 час (как и в push_client.py).
_cached_token: Optional[str] = None
_cached_token_expires_at: float = 0.0


class GooglePlayError(Exception):
    pass


class GooglePlayNotConfiguredError(GooglePlayError):
    """Google Play Billing ещё не подключён (нет GOOGLE_PLAY_SERVICE_ACCOUNT_JSON /
    GOOGLE_PLAY_PACKAGE_NAME) — ожидаемое состояние, пока не сделана
    настройка в Play Console, а не сбой сервера."""


def _service_account() -> dict:
    raw = settings.GOOGLE_PLAY_SERVICE_ACCOUNT_JSON
    if not raw or not settings.GOOGLE_PLAY_PACKAGE_NAME:
        raise GooglePlayNotConfiguredError("Оплата через Google Play пока не настроена")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise GooglePlayError(f"GOOGLE_PLAY_SERVICE_ACCOUNT_JSON повреждён (не валидный JSON): {e}") from e


def _get_access_token() -> str:
    """OAuth2 access_token для Android Publisher API через self-signed JWT
    (grant_type=jwt-bearer) — без сторонней google-auth."""
    global _cached_token, _cached_token_expires_at

    if _cached_token and time.time() < _cached_token_expires_at - 60:
        return _cached_token

    account = _service_account()
    now = int(time.time())
    try:
        assertion = pyjwt.encode(
            {
                "iss": account["client_email"],
                "scope": _SCOPE,
                "aud": _TOKEN_URL,
                "iat": now,
                "exp": now + 3600,
            },
            account["private_key"],
            algorithm="RS256",
        )
    except KeyError as e:
        raise GooglePlayError(f"В GOOGLE_PLAY_SERVICE_ACCOUNT_JSON нет поля {e}") from e

    try:
        response = requests.post(
            _TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            timeout=10,
        )
    except requests.RequestException as e:
        raise GooglePlayError(f"Не удалось получить токен Google: {e}") from e

    if response.status_code >= 400:
        raise GooglePlayError(f"Google OAuth вернул ошибку {response.status_code}: {response.text}")

    data = response.json()
    _cached_token = data["access_token"]
    _cached_token_expires_at = time.time() + data.get("expires_in", 3600)
    return _cached_token


def verify_subscription(product_id: str, purchase_token: str) -> dict:
    """
    Проверяет подписку через Play Developer API (subscriptionsv2) и
    возвращает {"active": bool, "expiry": datetime|None, "order_id": str|None,
    "state": str}.
    """
    access_token = _get_access_token()
    package_name = settings.GOOGLE_PLAY_PACKAGE_NAME

    url = f"{_API_BASE}/applications/{package_name}/purchases/subscriptionsv2/tokens/{purchase_token}"
    try:
        response = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    except requests.RequestException as e:
        raise GooglePlayError(f"Не удалось проверить покупку: {e}") from e

    if response.status_code >= 400:
        raise GooglePlayError(f"Google Play вернул ошибку {response.status_code}: {response.text}")

    data = response.json()
    state = data.get("subscriptionState", "")
    line_items = data.get("lineItems") or []

    matched_item = next((li for li in line_items if li.get("productId") == product_id), None)
    item = matched_item or (line_items[0] if line_items else None)

    expiry = None
    if item and item.get("expiryTime"):
        expiry = datetime.fromisoformat(item["expiryTime"].replace("Z", "+00:00")).astimezone(timezone.utc)

    active = state in ("SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD")

    return {
        "active": active,
        "expiry": expiry,
        "order_id": data.get("latestOrderId"),
        "state": state,
    }


def acknowledge_subscription(product_id: str, purchase_token: str) -> None:
    """
    Обязательно вызывается после первой успешной проверки новой подписки —
    иначе Google Play автоматически вернёт покупателю деньги через 3 дня
    (это требование политики Google Play Billing, не наша прихоть).
    """
    access_token = _get_access_token()
    package_name = settings.GOOGLE_PLAY_PACKAGE_NAME
    url = (
        f"{_API_BASE}/applications/{package_name}/purchases/subscriptions/"
        f"{product_id}/tokens/{purchase_token}:acknowledge"
    )
    try:
        response = requests.post(url, headers={"Authorization": f"Bearer {access_token}"}, json={}, timeout=10)
    except requests.RequestException as e:
        raise GooglePlayError(f"Не удалось подтвердить покупку: {e}") from e

    # 400 здесь часто означает "уже подтверждено ранее" — не фатально.
    if response.status_code >= 400 and "already" not in response.text.lower():
        raise GooglePlayError(
            f"Google Play вернул ошибку при подтверждении {response.status_code}: {response.text}"
        )


def verify_product_purchase(product_id: str, purchase_token: str) -> dict:
    """
    Проверяет разовую покупку (consumable-товар, напр. пакет монет CarSpot
    Coins) через Play Developer API. purchaseState: 0=куплено, 1=отменено,
    2=ожидает; consumptionState: 0=не потрачено, 1=уже потрачено.
    """
    access_token = _get_access_token()
    package_name = settings.GOOGLE_PLAY_PACKAGE_NAME

    url = f"{_API_BASE}/applications/{package_name}/purchases/products/{product_id}/tokens/{purchase_token}"
    try:
        response = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    except requests.RequestException as e:
        raise GooglePlayError(f"Не удалось проверить покупку: {e}") from e

    if response.status_code >= 400:
        raise GooglePlayError(f"Google Play вернул ошибку {response.status_code}: {response.text}")

    data = response.json()
    return {
        "purchased": data.get("purchaseState") == 0,
        "consumed": data.get("consumptionState") == 1,
        "order_id": data.get("orderId"),
    }


def consume_product_purchase(product_id: str, purchase_token: str) -> None:
    """
    Помечает разовую покупку "потреблённой" — обязательный шаг для
    consumable-товаров (пакеты монет), иначе Google Play не даст купить тот
    же товар повторно и через некоторое время автоматически вернёт деньги.
    """
    access_token = _get_access_token()
    package_name = settings.GOOGLE_PLAY_PACKAGE_NAME
    url = (
        f"{_API_BASE}/applications/{package_name}/purchases/products/"
        f"{product_id}/tokens/{purchase_token}:consume"
    )
    try:
        response = requests.post(url, headers={"Authorization": f"Bearer {access_token}"}, json={}, timeout=10)
    except requests.RequestException as e:
        raise GooglePlayError(f"Не удалось подтвердить потребление покупки: {e}") from e

    if response.status_code >= 400 and "already" not in response.text.lower():
        raise GooglePlayError(
            f"Google Play вернул ошибку при потреблении {response.status_code}: {response.text}"
        )
