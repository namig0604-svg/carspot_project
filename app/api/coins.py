"""
CarSpot Coins — внутренняя валюта. Покупается за реальные деньги через
Google Play Billing (consumable-товары) и тратится на:
  - бусты сходок и автосервисов (см. /api/events/{id}/boost-with-coins,
    /api/businesses/{id}/boost-with-coins) — Premium даёт то же самое бесплатно;
  - буст самого профиля в топ поиска (/profile/boost);
  - временный XP-бустер, ускоряющий рост уровня (/profile/xp-boost);
  - косметику профиля — рамки аватара, значки, цвет имени
    (/cosmetics/catalog, /cosmetics/buy, /cosmetics/equip, /cosmetics/unequip).
"""
import math
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import premium_tiers
from app.config import settings
from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.google_play_client import (
    GooglePlayError,
    GooglePlayNotConfiguredError,
    consume_product_purchase,
    verify_product_purchase,
)
from app.models.base import utcnow
from app.models.coin_transaction import CoinTransaction
from app.models.user import User
from app.models.user_cosmetic import UserCosmetic
from app.schemas.coin import (
    CoinBalanceOut,
    CoinPackageOut,
    CoinPurchaseOut,
    CoinPurchaseVerifyRequest,
    CoinTransactionOut,
    CosmeticActionRequest,
    CosmeticOut,
    CosmeticUnequipRequest,
    ProfileStatusOut,
)
from app.schemas.user import UserMe
from app.services import InsufficientCoinsError, grant_coins, spend_coins

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

# Косметика профиля: рамка аватара, значок рядом с именем, цвет имени.
# Рендерится на фронтенде чисто средствами Flutter (без картинок-ассетов) —
# id здесь совпадает с тем, что ожидает фронтенд для выбора цвета/иконки.
COSMETICS_CATALOG = [
    # --- Рамки аватара ---
    {"id": "frame_bronze", "type": "frame", "title": "Бронзовая рамка", "cost": 100},
    {"id": "frame_silver", "type": "frame", "title": "Серебряная рамка", "cost": 250},
    {"id": "frame_gold", "type": "frame", "title": "Золотая рамка", "cost": 500},
    {"id": "frame_neon", "type": "frame", "title": "Неоновая рамка", "cost": 800},
    {"id": "frame_emerald", "type": "frame", "title": "Изумрудная рамка", "cost": 350},
    {"id": "frame_sapphire", "type": "frame", "title": "Сапфировая рамка", "cost": 350},
    {"id": "frame_ruby", "type": "frame", "title": "Рубиновая рамка", "cost": 350},
    {"id": "frame_carbon", "type": "frame", "title": "Карбоновая рамка", "cost": 300},
    {"id": "frame_chrome", "type": "frame", "title": "Хромовая рамка", "cost": 300},
    {"id": "frame_diamond", "type": "frame", "title": "Алмазная рамка", "cost": 1200},
    # --- Значки ---
    {"id": "badge_wrench", "type": "badge", "title": "Механик", "cost": 150},
    {"id": "badge_flame", "type": "badge", "title": "Огонь", "cost": 150},
    {"id": "badge_star", "type": "badge", "title": "Звезда", "cost": 300},
    {"id": "badge_crown", "type": "badge", "title": "Корона", "cost": 400},
    {"id": "badge_bolt", "type": "badge", "title": "Молния", "cost": 150},
    {"id": "badge_heart", "type": "badge", "title": "Любимец", "cost": 150},
    {"id": "badge_trophy", "type": "badge", "title": "Чемпион", "cost": 350},
    {"id": "badge_target", "type": "badge", "title": "Снайпер", "cost": 200},
    {"id": "badge_rocket", "type": "badge", "title": "Ракета", "cost": 250},
    {"id": "badge_diamond", "type": "badge", "title": "Бриллиант", "cost": 600},
    # --- Цвет имени ---
    {"id": "color_red", "type": "name_color", "title": "Красный", "cost": 100},
    {"id": "color_blue", "type": "name_color", "title": "Синий", "cost": 100},
    {"id": "color_purple", "type": "name_color", "title": "Фиолетовый", "cost": 150},
    {"id": "color_gold", "type": "name_color", "title": "Золотой", "cost": 200},
    {"id": "color_green", "type": "name_color", "title": "Зелёный", "cost": 100},
    {"id": "color_cyan", "type": "name_color", "title": "Бирюзовый", "cost": 100},
    {"id": "color_pink", "type": "name_color", "title": "Розовый", "cost": 150},
    {"id": "color_orange", "type": "name_color", "title": "Оранжевый", "cost": 100},
    {"id": "color_teal", "type": "name_color", "title": "Тёмная бирюза", "cost": 120},
    {"id": "color_lime", "type": "name_color", "title": "Лайм", "cost": 120},
    # --- Эксклюзив CarSpot Premium: не покупается за монеты, доступен
    # бесплатно подписчикам нужного тарифа и выше (см. premium_tier_required
    # и premium_tiers.meets_tier — Max автоматически получает и Pro-эксклюзивы). ---
    {"id": "frame_pro_exclusive", "type": "frame", "title": "Рамка Pro", "cost": 900, "premium_tier_required": "pro"},
    {"id": "badge_pro_exclusive", "type": "badge", "title": "Знак Pro", "cost": 700, "premium_tier_required": "pro"},
    {"id": "frame_max_exclusive", "type": "frame", "title": "Рамка Max", "cost": 1500, "premium_tier_required": "max"},
    {"id": "badge_max_exclusive", "type": "badge", "title": "Икона Max", "cost": 1300, "premium_tier_required": "max"},
    {"id": "color_max_exclusive", "type": "name_color", "title": "Цвет Max", "cost": 900, "premium_tier_required": "max"},
]
_COSMETICS_BY_ID = {c["id"]: c for c in COSMETICS_CATALOG}
_COSMETIC_SLOT_FIELD = {
    "frame": "equipped_frame",
    "badge": "equipped_badge",
    "name_color": "equipped_name_color",
}


@router.get("/balance", response_model=CoinBalanceOut, summary="Баланс монет текущего пользователя")
def get_balance(current_user: User = Depends(get_current_active_user)):
    return CoinBalanceOut(
        balance=current_user.coin_balance or 0,
        boost_cost_event=settings.COIN_BOOST_COST_EVENT,
        boost_cost_business=settings.COIN_BOOST_COST_BUSINESS,
    )


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

    base_coins = package["coins"] + package["bonus_coins"]
    # Premium-плюшка: Pro/Max получают за ту же покупку больше монет (см.
    # premium_tiers.coin_purchase_bonus_multiplier) — округляем в большую
    # сторону, чтобы бонус не терялся на маленьких пакетах.
    bonus_multiplier = premium_tiers.coin_purchase_bonus_multiplier(current_user)
    total_coins = math.ceil(base_coins * bonus_multiplier)
    premium_bonus_percent = round((bonus_multiplier - 1) * 100)
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

    return CoinPurchaseOut(
        balance=current_user.coin_balance or 0,
        credited=total_coins,
        premium_bonus_percent=premium_bonus_percent,
    )


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


@router.get(
    "/profile/status",
    response_model=ProfileStatusOut,
    summary="Цены и состояние бустов профиля — для экрана \"Прокачка профиля\"",
)
def get_profile_status(current_user: User = Depends(get_current_active_user)):
    return ProfileStatusOut(
        bonus_xp=current_user.xp or 0,
        xp_boost_cost=settings.COIN_COST_XP_BOOST,
        xp_boost_grant_amount=settings.XP_BOOST_GRANT_AMOUNT,
        profile_boosted_until=current_user.profile_boosted_until,
        profile_boost_cost=settings.COIN_COST_PROFILE_BOOST,
        profile_boost_is_free=premium_tiers.gets_free_boost(current_user),
        boost_duration_hours=settings.BOOST_DURATION_HOURS,
    )


# ─────────────────────── КОСМЕТИКА ПРОФИЛЯ ───────────────────────

@router.get(
    "/cosmetics/catalog",
    response_model=List[CosmeticOut],
    summary="Каталог косметики профиля (рамки, значки, цвет имени)",
)
def list_cosmetics_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    owned_ids = {
        row[0]
        for row in db.query(UserCosmetic.cosmetic_id).filter(UserCosmetic.user_id == current_user.id).all()
    }
    equipped_ids = {current_user.equipped_frame, current_user.equipped_badge, current_user.equipped_name_color}

    def _is_owned(c: dict) -> bool:
        if c["id"] in owned_ids:
            return True
        # Premium-эксклюзив — "куплен" автоматически, пока активен нужный
        # тариф (или выше), без записи в user_cosmetics и без траты монет.
        required_tier = c.get("premium_tier_required")
        return bool(required_tier) and premium_tiers.meets_tier(current_user, required_tier)

    return [
        CosmeticOut(
            id=c["id"],
            type=c["type"],
            title=c["title"],
            cost=c["cost"],
            owned=_is_owned(c),
            equipped=c["id"] in equipped_ids,
        )
        for c in COSMETICS_CATALOG
    ]


@router.post("/cosmetics/buy", response_model=CosmeticOut, summary="Купить предмет косметики за монеты")
def buy_cosmetic(
    payload: CosmeticActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = _COSMETICS_BY_ID.get(payload.cosmetic_id)
    if not item:
        raise HTTPException(status_code=400, detail=f"Неизвестный предмет: {payload.cosmetic_id}")

    required_tier = item.get("premium_tier_required")
    if required_tier:
        # Эксклюзив Premium не продаётся за монеты ни при каких условиях —
        # подписчик нужного тарифа получает его бесплатно (см.
        # list_cosmetics_catalog._is_owned), остальным сюда дороги нет.
        tier_title = premium_tiers.TIER_TITLES_RU.get(required_tier, required_tier)
        raise HTTPException(
            status_code=403,
            detail=f'«{item["title"]}» — эксклюзив подписки {tier_title} и выше, доступен бесплатно по подписке, а не за монеты',
        )

    already_owned = (
        db.query(UserCosmetic)
        .filter(UserCosmetic.user_id == current_user.id, UserCosmetic.cosmetic_id == item["id"])
        .first()
    )
    if already_owned:
        raise HTTPException(status_code=400, detail="Этот предмет уже куплен")

    try:
        spend_coins(db, current_user, item["cost"], "cosmetic_buy", reference_id=item["id"])
    except InsufficientCoinsError as e:
        raise HTTPException(status_code=402, detail=str(e))

    db.add(UserCosmetic(user_id=current_user.id, cosmetic_id=item["id"]))
    db.commit()

    return CosmeticOut(id=item["id"], type=item["type"], title=item["title"], cost=item["cost"], owned=True, equipped=False)


@router.post("/cosmetics/equip", response_model=UserMe, summary="Надеть купленный предмет косметики")
def equip_cosmetic(
    payload: CosmeticActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    item = _COSMETICS_BY_ID.get(payload.cosmetic_id)
    if not item:
        raise HTTPException(status_code=400, detail=f"Неизвестный предмет: {payload.cosmetic_id}")

    required_tier = item.get("premium_tier_required")
    if required_tier:
        if not premium_tiers.meets_tier(current_user, required_tier):
            tier_title = premium_tiers.TIER_TITLES_RU.get(required_tier, required_tier)
            raise HTTPException(
                status_code=403,
                detail=f'«{item["title"]}» доступен только подписчикам {tier_title} и выше',
            )
    else:
        owned = (
            db.query(UserCosmetic)
            .filter(UserCosmetic.user_id == current_user.id, UserCosmetic.cosmetic_id == item["id"])
            .first()
        )
        if not owned:
            raise HTTPException(status_code=403, detail="Сначала купите этот предмет")

    setattr(current_user, _COSMETIC_SLOT_FIELD[item["type"]], item["id"])
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/cosmetics/unequip", response_model=UserMe, summary="Снять предмет косметики с указанного слота")
def unequip_cosmetic(
    payload: CosmeticUnequipRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    field = _COSMETIC_SLOT_FIELD.get(payload.slot)
    if not field:
        raise HTTPException(status_code=400, detail=f"Неизвестный слот: {payload.slot}")

    setattr(current_user, field, None)
    db.commit()
    db.refresh(current_user)
    return current_user


# ─────────────────────── БУСТ ПРОФИЛЯ И XP-БУСТЕР ───────────────────────

@router.post(
    "/profile/boost",
    response_model=UserMe,
    summary=f"Поднять профиль в топ поиска на {settings.BOOST_DURATION_HOURS} ч. за {settings.COIN_COST_PROFILE_BOOST} монет",
)
def boost_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    now = utcnow()
    if current_user.profile_boosted_until and current_user.profile_boosted_until > now:
        raise HTTPException(
            status_code=400,
            detail=f"Буст профиля уже активен до {current_user.profile_boosted_until.isoformat()}",
        )

    # CarSpot Pro поднимает профиль в поиске бесплатно (как сходки и
    # автосервисы) — остальные платят монетами.
    if not premium_tiers.gets_free_boost(current_user):
        try:
            spend_coins(db, current_user, settings.COIN_COST_PROFILE_BOOST, "boost_profile")
        except InsufficientCoinsError as e:
            raise HTTPException(status_code=402, detail=str(e))

    current_user.profile_boosted_until = now + timedelta(hours=premium_tiers.boost_duration_hours(current_user))
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post(
    "/profile/xp-boost",
    response_model=UserMe,
    summary=f"Купить {settings.XP_BOOST_GRANT_AMOUNT} бонусного XP за {settings.COIN_COST_XP_BOOST} монет",
)
def boost_xp(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Разовая покупка — сразу прибавляет settings.XP_BOOST_GRANT_AMOUNT к
    current_user.xp (бонус поверх уровня, который фронтенд считает из живой
    статистики, см. models/user.py). Можно покупать сколько угодно раз
    подряд, в отличие от боста поиска/сходок — здесь нет "уже активен".
    """
    try:
        spend_coins(db, current_user, settings.COIN_COST_XP_BOOST, "xp_boost")
    except InsufficientCoinsError as e:
        raise HTTPException(status_code=402, detail=str(e))

    current_user.xp = (current_user.xp or 0) + settings.XP_BOOST_GRANT_AMOUNT
    db.commit()
    db.refresh(current_user)
    return current_user
