"""
Оплата Premium через Trybit. Пользователь выбирает план -> получает ссылку
на оплату -> Trybit шлёт нам postback, когда оплата прошла -> продлеваем Premium.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.base import new_id, utcnow
from app.models.payment import PremiumPayment
from app.models.user import User
from app.schemas.payment import CheckoutOut, CheckoutRequest, PaymentStatusOut, PremiumPlanOut
from app.services import extend_premium
from app.trybit_client import TrybitError, create_invoice, verify_postback_token

router = APIRouter()

PREMIUM_PLANS = {
    "month": {"title": "Premium на месяц", "days": 30, "amount_usd": 4.99},
    "year": {"title": "Premium на год", "days": 365, "amount_usd": 39.99},
}


@router.get("/plans", response_model=List[PremiumPlanOut], summary="Доступные планы Premium")
def list_plans():
    return [
        PremiumPlanOut(id=plan_id, title=data["title"], days=data["days"], amount_usd=data["amount_usd"])
        for plan_id, data in PREMIUM_PLANS.items()
    ]


@router.post("/checkout", response_model=CheckoutOut, summary="Создать платёж и получить ссылку на оплату")
def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = PREMIUM_PLANS.get(payload.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Неизвестный план: {payload.plan}")

    order_id = new_id()
    payment = PremiumPayment(
        user_id=current_user.id,
        plan=payload.plan,
        amount_usd=plan["amount_usd"],
        days=plan["days"],
        order_id=order_id,
    )
    db.add(payment)
    db.flush()

    try:
        result = create_invoice(order_id=order_id, amount_usd=plan["amount_usd"], email=current_user.email)
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
            extend_premium(user, payment.days)

        db.commit()

    return {"message": "ok"}
