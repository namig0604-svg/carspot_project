"""
Ежедневный вход (CarSpot Daily Login) — награда XP+монеты за каждый день
захода подряд, на 7-й день подряд — 7 дней CarSpot Basic в подарок.
Стрик считается по календарным дням (UTC): если между текущим и прошлым
claim прошёл ровно 1 календарный день — стрик продолжается, иначе (пропуск
дня или первый раз) — начинается заново с 1-го дня. См. extend_premium в
app/services.py — покупка/подарок Basic не понижает уже активный более
высокий тариф (Pro/Max), а дни всё равно добавляются.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user
from app.models.base import utcnow
from app.models.user import User
from app.premium_tiers import TIER_BASIC
from app.schemas.daily_login import DailyLoginClaimResponse, DailyLoginStatusResponse
from app.services import extend_premium, grant_coins

router = APIRouter()

# День стрика (1..7) -> (XP, монеты). 7-й день — самый крупный + подарок Basic.
DAILY_REWARDS = {
    1: (20, 10),
    2: (25, 12),
    3: (30, 15),
    4: (40, 20),
    5: (50, 25),
    6: (60, 30),
    7: (100, 50),
}
STREAK_BONUS_DAY = 7
STREAK_BONUS_PREMIUM_DAYS = 7


def _next_streak_day(user: User, now) -> int:
    """Какой день (1..7) будет засчитан, если забрать награду сейчас."""
    last = user.last_daily_claim_at
    if last is None:
        return 1
    days_gap = (now.date() - last.date()).days
    if days_gap != 1:
        # Уже забрано сегодня (gap == 0) или стрик прервался (gap > 1) —
        # в обоих случаях следующий claim начинает счёт заново с 1-го дня.
        # (can_claim отдельно решает, разрешён ли сам claim сейчас.)
        return 1
    prev = user.daily_streak_count or 0
    if prev >= STREAK_BONUS_DAY:
        return 1
    return prev + 1


def _can_claim(user: User, now) -> bool:
    last = user.last_daily_claim_at
    if last is None:
        return True
    return last.date() != now.date()


@router.get("/status", response_model=DailyLoginStatusResponse, summary="Статус стрика ежедневного входа")
def get_daily_login_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    now = utcnow()
    return DailyLoginStatusResponse(
        current_streak=current_user.daily_streak_count or 0,
        can_claim=_can_claim(current_user, now),
        next_day=_next_streak_day(current_user, now),
        last_claim_at=current_user.last_daily_claim_at,
    )


@router.post("/claim", response_model=DailyLoginClaimResponse, summary="Забрать награду за сегодняшний вход")
def claim_daily_login(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    now = utcnow()
    if not _can_claim(current_user, now):
        raise HTTPException(status_code=400, detail="Награда за сегодня уже получена — приходите завтра")

    day = _next_streak_day(current_user, now)
    xp_reward, coin_reward = DAILY_REWARDS[day]

    current_user.xp = (current_user.xp or 0) + xp_reward
    grant_coins(db, current_user, coin_reward, tx_type="daily_login", reference_id=str(day))

    bonus_premium_days = None
    bonus_premium_tier = None
    if day == STREAK_BONUS_DAY:
        extend_premium(current_user, STREAK_BONUS_PREMIUM_DAYS, tier=TIER_BASIC)
        bonus_premium_days = STREAK_BONUS_PREMIUM_DAYS
        bonus_premium_tier = TIER_BASIC

    current_user.daily_streak_count = day
    current_user.last_daily_claim_at = now
    db.commit()

    next_day = 1 if day >= STREAK_BONUS_DAY else day + 1

    return DailyLoginClaimResponse(
        message="Награда за вход начислена" if day < STREAK_BONUS_DAY else "7 дней подряд! Награда и Basic на неделю начислены",
        day=day,
        xp_reward=xp_reward,
        coin_reward=coin_reward,
        bonus_premium_days=bonus_premium_days,
        bonus_premium_tier=bonus_premium_tier,
        new_xp=current_user.xp or 0,
        new_coin_balance=current_user.coin_balance or 0,
        next_streak_day=next_day,
    )
