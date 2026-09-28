"""
ИИ-диагностика по симптомам неисправности — CarSpot Premium.

Чат со звеном на Anthropic Claude API: владелец описывает симптомы своими
словами, ИИ задаёт уточняющие вопросы и в конце предлагает вероятную причину
+ тип автосервиса из BUSINESS_CATEGORIES, чтобы фронтенд мог сразу открыть
список подходящих сервисов (businesses_list_screen с initialCategory).

Переписка не сохраняется на бэкенде — клиент держит историю сообщений в
памяти экрана и присылает её целиком в каждом запросе (нет отдельной
таблицы/миграции ради MVP). Без ANTHROPIC_API_KEY на Railway фича отдаёт
понятную ошибку 503 вместо падения — см. app/config.py.
"""
import re

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import premium_tiers
from app.config import settings
from app.database import get_db
from app.deps import get_current_active_user
from app.models.business import BUSINESS_CATEGORIES
from app.models.car import Car
from app.models.user import User
from app.schemas.ai_diagnosis import DiagnosisRequest, DiagnosisResponse

router = APIRouter()

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"

_VALID_CATEGORIES = [c for c in BUSINESS_CATEGORIES if c != "other"]

_CATEGORY_TAG_RE = re.compile(r"\n?КАТЕГОРИЯ:\s*([a-z_]+)\s*$", re.IGNORECASE)

_SYSTEM_PROMPT = (
    "Ты — ИИ-помощник автомеханик в приложении CarSpot. Владелец машины "
    "описывает симптомы неисправности своими словами. Твоя задача:\n"
    "1. Если информации мало — задай ОДИН короткий уточняющий вопрос за раз "
    "(например: когда именно проявляется, на какой скорости, есть ли звук/запах/"
    "индикатор на панели). Не задавай больше одного вопроса в сообщении.\n"
    "2. Как только данных достаточно — дай короткий предварительный вывод "
    "простым языком (не более 5-6 предложений): вероятная причина, насколько "
    "это срочно (можно ехать дальше / нужно в сервис в ближайшие дни / "
    "остановиться и не ехать), и что делать. Если симптом касается тормозов, "
    "рулевого управления, дыма/огня или потери управления — всегда советуй "
    "немедленно прекратить движение и обратиться к специалисту.\n"
    "3. Обязательно уточни, что это предварительное предположение по описанию, "
    "а не диагноз, и точную причину определит только очный осмотр в сервисе.\n"
    "4. Когда даёшь вывод (шаг 2) — ОБЯЗАТЕЛЬНО заверши ответ отдельной строкой "
    "в формате 'КАТЕГОРИЯ: <значение>', где <значение> — ОДНО из: "
    + ", ".join(_VALID_CATEGORIES)
    + ". Если ещё рано (шаг 1, задаёшь вопрос) — эту строку НЕ добавляй.\n"
    "Отвечай на русском языке, дружелюбно и по делу, без markdown-разметки."
)


def _strip_category_tag(text: str) -> tuple[str, str | None]:
    match = _CATEGORY_TAG_RE.search(text.strip())
    if not match:
        return text.strip(), None
    category = match.group(1).lower()
    if category not in _VALID_CATEGORIES:
        category = None
    cleaned = _CATEGORY_TAG_RE.sub("", text.strip()).strip()
    return cleaned, category


@router.post("", response_model=DiagnosisResponse, summary="Сообщение в чат ИИ-диагностики")
def diagnose(
    payload: DiagnosisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not premium_tiers.can_use_ai_diagnosis(current_user) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ИИ-диагностика доступна только с CarSpot Premium",
        )

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ИИ-диагностика временно недоступна: не настроен ключ на сервере",
        )

    car_context = ""
    if payload.car_id:
        car = db.query(Car).filter(Car.id == payload.car_id, Car.user_id == current_user.id).first()
        if car:
            parts = [str(car.make), str(car.model)]
            if car.year:
                parts.append(str(car.year))
            if car.engine:
                parts.append(str(car.engine))
            car_context = f"\n\nАвтомобиль владельца: {' '.join(parts)}."

    try:
        response = requests.post(
            _ANTHROPIC_URL,
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": _ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": settings.ANTHROPIC_MODEL,
                "max_tokens": 700,
                "system": _SYSTEM_PROMPT + car_context,
                "messages": [{"role": m.role, "content": m.content} for m in payload.messages],
            },
            timeout=25,
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось связаться с ИИ-сервисом, попробуйте ещё раз",
        )

    if response.status_code != 200:
        # Не отдаём тело ответа провайдера наружу (может содержать детали ключа/лимитов).
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ИИ-сервис сейчас недоступен, попробуйте чуть позже",
        )

    data = response.json()
    try:
        raw_text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        )
    except (AttributeError, TypeError):
        raw_text = ""

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ИИ-сервис вернул пустой ответ, попробуйте переформулировать",
        )

    reply, category = _strip_category_tag(raw_text)
    return DiagnosisResponse(reply=reply, suggested_category=category)
