"""
Клиент Trybit (бывший CryptoCloud) — крипто-эквайринг, работает в РФ и
других странах СНГ, в отличие от Stripe/PayPal.

Ключи берутся из переменных окружения Railway (settings.TRYBIT_*) — сюда
их вставлять не нужно и не стоит: если тут пусто, create_invoice() просто
поднимет понятную ошибку, а не тихо отправит платёж в никуда.
"""
import requests

from app.config import settings

TRYBIT_API_URL = "https://api.trybit.com/v2/invoice/create"


class TrybitError(Exception):
    pass


def create_invoice(*, order_id: str, amount_usd: float, email: str = None) -> dict:
    if not settings.TRYBIT_SHOP_ID or not settings.TRYBIT_API_KEY:
        raise TrybitError(
            "Trybit не настроен: задайте TRYBIT_SHOP_ID и TRYBIT_API_KEY "
            "в переменных окружения Railway"
        )

    payload = {
        "shop_id": settings.TRYBIT_SHOP_ID,
        "amount": amount_usd,
        "currency": "USD",
        "order_id": order_id,
    }
    if email:
        payload["email"] = email

    try:
        response = requests.post(
            TRYBIT_API_URL,
            json=payload,
            headers={"Authorization": f"Token {settings.TRYBIT_API_KEY}"},
            timeout=15,
        )
    except requests.RequestException as e:
        raise TrybitError(f"Не удалось связаться с Trybit: {e}") from e

    if response.status_code >= 400:
        raise TrybitError(f"Trybit вернул ошибку {response.status_code}: {response.text}")

    data = response.json()
    result = data.get("result")
    if not result or not result.get("link"):
        raise TrybitError(f"Неожиданный ответ Trybit: {data}")

    return result


def verify_postback_token(token: str) -> dict:
    """Postback от Trybit присылает JWT (HS256), подписанный секретным ключом
    магазина — так проверяем, что уведомление реально от Trybit, а не подделка."""
    import jwt as pyjwt

    if not settings.TRYBIT_SECRET_KEY:
        raise TrybitError("TRYBIT_SECRET_KEY не задан")

    try:
        payload = pyjwt.decode(token, settings.TRYBIT_SECRET_KEY, algorithms=["HS256"])
    except pyjwt.PyJWTError as e:
        raise TrybitError(f"Неверная подпись postback: {e}") from e

    return payload
