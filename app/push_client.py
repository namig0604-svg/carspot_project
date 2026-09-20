"""
Отправка push-уведомлений через Firebase Cloud Messaging (HTTP v1 API).

Ключи берутся из переменных окружения Railway (settings.FIREBASE_*) — суда
их выставлять не нужно и не стоит: если push не отпущен настроен, send_push()
поднимает PushNotConfiguredError, а не тихо отпровтит push в никуда. Сборка
без сторонних SDK (firebase-admin/google-auth) — по тому же принципу, что
и app/trybit_client.py: self-signed JWT своевременно создаём сами + requests.
"""
import json
import time
from typing import Optional

import jwt as pyjwt
import requests

from app.config import settings

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Кэш access_token в памяти процесса — не запрашиваем новый на каждый push,
# он живёт ~1 час.
_cached_token: Optional[str] = None
_cached_token_expires_at: float = 0.0


class PushError(Exception):
    pass


class PushNotConfiguredError(PushError):
    """Firebase ещё не подключён (нет FIREBASE_PROJECT_ID / _SERVICE_ACCOUNT_JSON).

    Ожидаемое состояние, пока пользователь не заполнил переклект — push
    вернутся к обычной ленте уведомлений, а не роняют запрос."""


def _service_account() -> dict:
    raw = settings.FIREBASE_SERVICE_ACCOUNT_JSON
    if not raw or not settings.FIREBASE_PROJECT_ID:
        raise PushNotConfiguredError("Push-уведомления пока не настроены")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise PushError(f"FIREBASE_SERVICE_ACCOUNT_JSON повреждён (не валидный JSON): {e}") from e


def _get_access_token() -> str:
    """OAuth2 access_token для FCM HTTP v1 через self-signed JWT
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
                "scope": _FCM_SCOPE,
                "aud": _TOKEN_URL,
                "iat": now,
                "exp": now + 3600,
            },
            account["private_key"],
            algorithm="RS256",
        )
    except KeyError as e:
        raise PushError(f"В FIREBASE_SERVICE_ACCOUNT_JSON нет поля {e}") from e

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
        raise PushError(f"Не удалось получить токен Firebase: {e}") from e

    if response.status_code >= 400:
        raise PushError(f"Firebase OAuth вернул ошибку {response.status_code}: {response.text}")

    data = response.json()
    _cached_token = data["access_token"]
    _cached_token_expires_at = time.time() + data.get("expires_in", 3600)
    return _cached_token


def send_push(token: str, title: str, body: str, data: Optional[dict] = None) -> None:
    """Шлёт одно push-сообщение на одно device-токен.

    Бросает PushNotConfiguredError / PushError — вызывающий код (см.
    services._send_push_to_user) сам решает, что с этим делать: обычно
    тихо игнорировать или почистить протухший токен."""
    access_token = _get_access_token()

    message: dict = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
        }
    }
    if data:
        message["message"]["data"] = {k: str(v) for k, v in data.items()}

    try:
        response = requests.post(
            f"https://fcm.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/messages:send",
            json=message,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
    except requests.RequestException as e:
        raise PushError(f"Не удалось отправить push: {e}") from e

    if response.status_code >= 400:
        raise PushError(f"FCM вернул ошибку {response.status_code}: {response.text}")
