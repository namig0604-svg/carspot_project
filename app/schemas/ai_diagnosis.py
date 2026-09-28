from typing import List, Optional

from pydantic import BaseModel, Field


class DiagnosisMessage(BaseModel):
    """Одно сообщение в переписке с ИИ. role: 'user' | 'assistant'."""

    role: str
    content: str = Field(..., max_length=4000)


class DiagnosisRequest(BaseModel):
    # Клиент хранит всю историю чата локально и присылает её целиком —
    # бэкенд ничего не сохраняет (нет отдельной таблицы под переписку).
    messages: List[DiagnosisMessage] = Field(..., min_length=1, max_length=40)
    car_id: Optional[str] = None


class DiagnosisResponse(BaseModel):
    reply: str
    # Одна из BUSINESS_CATEGORIES (service/tuning/detailing/body_shop/tire/
    # car_wash/electric/parts) — если ИИ достаточно уверен, чтобы предложить
    # конкретный тип автосервиса. None, если пока рано (мало данных) или ИИ
    # не смог однозначно определить категорию.
    suggested_category: Optional[str] = None
