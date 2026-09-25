"""
Оплата Premium через Trybit. Пользователь выбирает план -> получает ссылку
на оплату -> Trybit шлёт нам postback, когда оплата прошла -> продлеваем Premium.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.models.base import new_id, utcnow
from app.models.payment import PremiumPayment
from app.models.user import User
from app.schemas.payment import CheckoutOut, CheckoutRequest, GooglePlayVerifyRequest, PaymentStatusOut, PremiumPlanOut
from app.services import extend_premium
from app.trybit_client import TrybitError, TrybitNotConfiguredError, create_invoice, verify_postback_token
from app.google_play_client import (
    GooglePlayError,
    GooglePlayNotConfiguredError,
    acknowledge_subscription,
    verify_subscription,
)

router = APIRouter()

PREMIUM_PLANS = {
    # Pro — те же id/цены/товары Google Play, что были у единственного
    # плана Premium раньше, чтобы не ломать уже оформленные подписки.
    "pro_month": {
        "title": "CarSpot Pro на месяц",
        "tier": "pro",
        "days": 30,
        "amount_usd": 4.99,
        "google_play_product_id": "carspot_premium_month",
    },
    "pro_year": {
        "title": "CarSpot Pro на год",
        "tier": "pro",
        "days": 365,
        "amount_usd": 39.99,
        "google_play_product_id": "carspot_premium_year",
    },
    "basic_month": {
        "title": "CarSpot Basic на месяц",
        "tier": "basic",
        "days": 30,
        "amount_usd": 2.49,
        "google_play_product_id": "carspot_basic_month",
    },
    "basic_year": {
        "title": "CarSpot Basic на год",
        "tier": "basic",
        "days": 365,
        "amount_usd": 19.99,
        "google_play_product_id": "carspot_basic_year",
    },
    "max_month": {
        "title": "CarSpot Max на месяц",
        "tier": "max",
        "days": 30,
        "amount_usd": 9.99,
        "google_play_product_id": "carspot_max_month",
    },
    "max_year": {
        "title": "CarSpot Max на год",
        "tier": "max",
        "days": 365,
        "amount_usd": 89.99,
        "google_play_product_id": "carspot_max_year",
    },
}

# Старые id плана ("month"/"year") принимаем как алиасы Pro — чтобы уже
# опубликованные версии приложения, которые ещё шлют старые id, не сломались.
_LEGACY_PLAN_ALIASES = {"month": "pro_month", "year": "pro_year"}


def _resolve_plan_id(plan_id: str) -> str:
    return _LEGACY_PLAN_ALIASES.get(plan_id, plan_id)

# product_id в Play Console -> наш внутренний id плана. Строим один раз,
# используем чтобы не доверять клиенту, какой именно план он "купил" —
# сервер сам решает по product_id, что проверил Google.
_GOOGLE_PLAY_PRODUCT_TO_PLAN = {
    data["google_play_product_id"]: plan_id for plan_id, data in PREMIUM_PLANS.items()
}


@router.get("/plans", response_model=List[PremiumPlanOut], summary="Доступные планы Premium (Basic и Pro)")
def list_plans():
    return [
        PremiumPlanOut(
            id=plan_id,
            title=data["title"],
            tier=data["tier"],
            days=data["days"],
            amount_usd=data["amount_usd"],
        )
        for plan_id, data in PREMIUM_PLANS.items()
    ]


@router.post("/checkout", response_model=CheckoutOut, summary="Создать платёж и получить ссылку на оплату")
def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan_id = _resolve_plan_id(payload.plan)
    plan = PREMIUM_PLANS.get(plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Неизвестный план: {payload.plan}")

    order_id = new_id()
    payment = PremiumPayment(
        user_id=current_user.id,
        plan=plan_id,
        tier=plan["tier"],
        amount_usd=plan["amount_usd"],
        days=plan["days"],
        order_id=order_id,
    )
    db.add(payment)
    db.flush()

    try:
        result = create_invoice(order_id=order_id, amount_usd=plan["amount_usd"], email=current_user.email)
    except TrybitNotConfiguredError as e:
        # Ожидаемое состояние, пока не подключён мерчант-аккаунт — не 502,
        # чтобы не выглядело как сбой сервера.
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except TrybitError as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(e))

    payment.provider_invoice_id = result.get("uuid")
    payment.pay_url = result.get("link")
    db.commit()
    db.refresh(payment)

    return CheckoutOut(
        payment_id=payment.id,
        pay_url=payment.pay_url,
        status=payment.status,
        amount_usd=payment.amount_usd,
        plan=payment.plan,
        tier=payment.tier,
    )


@router.get("/history", response_model=List[PaymentStatusOut], summary="История платежей Premium текущего пользователя")
def payment_history(
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return (
        db.query(PremiumPayment)
        .filter(PremiumPayment.user_id == current_user.id)
        .order_by(PremiumPayment.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )


@router.get("/{payment_id}/status", response_model=PaymentStatusOut, summary="Статус платежа")
def payment_status(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    payment = db.query(PremiumPayment).filter(PremiumPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваш платёж")
    return payment


@router.post("/trybit/webhook", summary="Postback от Trybit (настраивается в кабинете Trybit)")
async def trybit_webhook(request: Request, db: Session = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    token = body.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Нет token в постбэке")

    try:
        data = verify_postback_token(token)
    except TrybitError as e:
        raise HTTPException(status_code=400, detail=str(e))

    order_id = data.get("order_id")
    status_value = data.get("status")

    payment = db.query(PremiumPayment).filter(PremiumPayment.order_id == order_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    if payment.status in ("paid", "overpaid"):
        return {"message": "Уже обработано"}

    if status_value in ("paid", "overpaid"):
        payment.status = status_value
        payment.paid_at = utcnow()

        user = db.query(User).filter(User.id == payment.user_id).first()
        if user:
            extend_premium(user, payment.days, tier=payment.tier)
            if payment.tier == "max":
                # Эксклюзив тарифа Max — бонусный XP при каждой настоящей
                # оплате (и продлении), поверх обычного уровня.
                user.xp = (user.xp or 0) + settings.PREMIUM_ULTRA_PURCHASE_BONUS_XP

        db.commit()

    return {"message": "ok"}



@router.post(
    "/google-play/verify",
    response_model=PaymentStatusOut,
    summary="Подтвердить покупку из Google Play и включить Premium",
)
def verify_google_play_purchase(
    payload: GooglePlayVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan_id = _GOOGLE_PLAY_PRODUCT_TO_PLAN.get(payload.product_id)
    if not plan_id:
        raise HTTPException(status_code=400, detail=f"Неизвестный товар Google Play: {payload.product_id}")
    plan = PREMIUM_PLANS[plan_id]

    # Один и тот же purchase_token не должен включать Premium дважды (повтор
    # запроса с клиента, восстановление покупок и т.п.) — если уже обработан,
    # просто отдаём его текущий статус.
    existing = db.query(PremiumPayment).filter(PremiumPayment.purchase_token == payload.purchase_token).first()
    if existing:
        return existing

    try:
        result = verify_subscription(payload.product_id, payload.purchase_token)
    except GooglePlayNotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GooglePlayError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not result["active"]:
        raise HTTPException(status_code=400, detail="Подписка не активна (проверьте статус оплаты в Google Play)")

    payment = PremiumPayment(
        user_id=current_user.id,
        plan=plan_id,
        tier=plan["tier"],
        amount_usd=plan["amount_usd"],
        days=plan["days"],
        order_id=new_id(),
        provider="google_play",
        provider_invoice_id=result.get("order_id"),
        purchase_token=payload.purchase_token,
        status="paid",
        paid_at=utcnow(),
    )
    db.add(payment)

    # Google Play сам управляет сроком подписки (продления, отмены) — он
    # источник правды по дате окончания, поэтому выставляем premium_until
    # ровно по присланному expiry, а не просто приплюсовываем дни плана.
    current_user.premium_tier = plan["tier"]
    if result["expiry"]:
        current_user.premium_until = result["expiry"].replace(tzinfo=None)
    else:
        extend_premium(current_user, plan["days"], tier=plan["tier"])
    if plan["tier"] == "max":
        current_user.xp = (current_user.xp or 0) + settings.PREMIUM_ULTRA_PURCHASE_BONUS_XP

    db.commit()
    db.refresh(payment)

    try:
        acknowledge_subscription(payload.product_id, payload.purchase_token)
    except GooglePlayError:
        # Premium уже включён — это не должно ломать ответ пользователю.
        # Если не подтвердится, Google Play через 3 дня автовозвратит деньги,
        # что стоит отслеживать отдельно (TODO: повторная попытка по cron).
        pass

    return payment
