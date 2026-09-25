"""
CarSpot Coins — внутренняя валюта. Покупается за реальные деньги через
Google Play Billing (consumable-товары) и тратится на бусты сходок и
автосервисов (см. /api/events/{id}/boost-with-coins,
/api/businesses/{id}/boost-with-coins). Подписчикам Premium буст по-прежнему
доступен бесплатно через обычный /boost — монеты нужны в первую очередь тем,
у кого Premium нет, либо тем, кто хочет продвинуть сразу несколько сходок.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.google_play_client import (
    GooglePlayError,
    GooglePlayNotConfiguredError,
    consume_product_purchase,
    verify_product_purchase,
)
from app.models.coin_transaction import CoinTransaction
from app.models.user import User
from app.schemas.coin import (
    CoinBalanceOut,
    CoinPackageOut,
    CoinPurchaseOut,
    CoinPurchaseVerifyRequest,
    CoinTransactionOut,
)
from app.services import grant_coins

router = APIRouter()

# Пакеты монет, доступные к покупке. product_id должен быть заведён в Play
# Console как consumable in-app product с точно таким же id.
COIN_PACKAGES = [
    {"product_id": "carspot_coins_100", "coins": 100, "bonus_coins": 0, "price_usd": 0.99},
    {"product_id": "carspot_coins_550", "coins": 500, "bonus_coins": 50, "price_usd": 4.99},
    {"product_id": "carspot_coins_1200", "coins": 1000, "bonus_coins": 200, "price_usd": 9.99},
    {"product_id": "carspot_coins_2600", "coins": 2000, "bonus_coins": 600, "price_usd": 19.99},
]
_COIN_PACKAGES_BY_ID = {p["product_id"]: p for p in COIN_PACKAGES}


@router.get("/balance", response_model=CoinBalanceOut, summary="Баланс монет текущего пользователя")
def get_balance(current_user: User = Depends(get_current_active_user)):
    return CoinBalanceOut(balance=current_user.coin_balance or 0)


@router.get("/packages", response_model=List[CoinPackageOut], summary="Доступные пакеты монет для покупки")
def list_packages():
    return [
        CoinPackageOut(
            product_id=p["product_id"],
            coins=p["coins"],
            bonus_coins=p["bonus_coins"],
            total_coins=p["coins"] + p["bonus_coins"],
            price_usd=p["price_usd"],
            title=f'{p["coins"] + p["bonus_coins"]} монет CarSpot Coins',
        )
        for p in COIN_PACKAGES
    ]


@router.post(
    "/google-play/verify",
    response_model=CoinPurchaseOut,
    summary="Подтвердить покупку пакета монет из Google Play и зачислить их",
)
def verify_google_play_coin_purchase(
    payload: CoinPurchaseVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    package = _COIN_PACKAGES_BY_ID.get(payload.product_id)
    if not package:
        raise HTTPException(status_code=400, detail=f"Неизвестный пакет монет: {payload.product_id}")

    # Тот же purchase_token не должен зачислять монеты дважды (повтор запроса,
    # обрыв связи после ответа и т.п.) — если уже обработан, просто отдаём
    # текущий баланс, ничего не начисляя повторно.
    existing = db.query(CoinTransaction).filter(CoinTransaction.purchase_token == payload.purchase_token).first()
    if existing:
        return CoinPurchaseOut(balance=current_user.coin_balance or 0, credited=0)

    try:
        result = verify_product_purchase(payload.product_id, payload.purchase_token)
    except GooglePlayNotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GooglePlayError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not result["purchased"]:
        raise HTTPException(status_code=400, detail="Покупка не подтверждена Google Play (проверьте статус оплаты)")

    total_coins = package["coins"] + package["bonus_coins"]
    grant_coins(
        db,
        current_user,
        total_coins,
        tx_type="purchase",
        purchase_token=payload.purchase_token,
    )
    db.commit()
    db.refresh(current_user)

    if not result["consumed"]:
        try:
            consume_product_purchase(payload.product_id, payload.purchase_token)
        except GooglePlayError:
            # Монеты уже зачислены — не ломаем ответ пользователю. Если
            # consume не пройдёт, повторная покупка этого товара будет
            # недоступна в Google Play, пока это не устранится вручную.
            pass

    return CoinPurchaseOut(balance=current_user.coin_balance or 0, credited=total_coins)


@router.get("/transactions", response_model=List[CoinTransactionOut], summary="История операций с монетами")
def list_transactions(
    pagination: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = (
        db.query(CoinTransaction)
        .filter(CoinTransaction.user_id == current_user.id)
        .order_by(CoinTransaction.created_at.desc())
    )
    return query.offset(pagination.offset).limit(pagination.limit).all()
