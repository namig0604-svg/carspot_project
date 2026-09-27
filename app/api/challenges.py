"""
Сезонные челленджи: список активных + прогресс текущего пользователя,
получение награды, создание/управление (администрация).
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_active_user, require_rank
from app.models.base import utcnow
from app.models.challenge import Challenge, ChallengeProgress
from app.models.user import User
from app.ranks import RANK_ADMINISTRATOR
from app.schemas.challenge import (
    ChallengeClaimResponse,
    ChallengeCreate,
    ChallengeListResponse,
    ChallengeOut,
    ChallengeUpdate,
)
from app.services import grant_coins

router = APIRouter()


def _to_out(challenge: Challenge, progress: ChallengeProgress | None) -> ChallengeOut:
    out = ChallengeOut.model_validate(challenge)
    if progress:
        out.progress = min(progress.progress, challenge.target)
        out.completed_at = progress.completed_at
        out.reward_claimed_at = progress.reward_claimed_at
    return out


@router.get("/active", response_model=ChallengeListResponse, summary="Активные сезонные челленджи")
def list_active_challenges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    now = utcnow()
    challenges = (
        db.query(Challenge)
        .filter(
            Challenge.is_active.is_(True),
            Challenge.starts_at <= now,
            Challenge.ends_at >= now,
        )
        .order_by(Challenge.ends_at.asc())
        .all()
    )
    if not challenges:
        return ChallengeListResponse(items=[])

    challenge_ids = [c.id for c in challenges]
    progress_rows = (
        db.query(ChallengeProgress)
        .filter(
            ChallengeProgress.challenge_id.in_(challenge_ids),
            ChallengeProgress.user_id == current_user.id,
        )
        .all()
    )
    progress_by_challenge = {p.challenge_id: p for p in progress_rows}

    return ChallengeListResponse(
        items=[_to_out(c, progress_by_challenge.get(c.id)) for c in challenges]
    )


@router.post(
    "/{challenge_id}/claim",
    response_model=ChallengeClaimResponse,
    summary="Забрать награду за выполненный челлендж",
)
def claim_challenge_reward(
    challenge_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Челлендж не найден")

    progress = (
        db.query(ChallengeProgress)
        .filter(
            ChallengeProgress.challenge_id == challenge_id,
            ChallengeProgress.user_id == current_user.id,
        )
        .first()
    )
    if not progress or not progress.completed_at:
        raise HTTPException(status_code=400, detail="Челлендж ещё не выполнен")
    if progress.reward_claimed_at:
        raise HTTPException(status_code=400, detail="Награда уже получена")

    if challenge.xp_reward:
        current_user.xp = (current_user.xp or 0) + challenge.xp_reward
    if challenge.coin_reward:
        grant_coins(
            db,
            current_user,
            challenge.coin_reward,
            tx_type="challenge_reward",
            reference_id=challenge.id,
        )
    if challenge.badge_key:
        # badge_key — id из каталога COSMETICS_CATALOG (app/api/coins.py):
        # челлендж просто выдаёт предмет в собственность бесплатно, так же,
        # как обычная покупка за монеты (см. app.models.user_cosmetic).
        # Экипировка (equipped_frame/badge/name_color) — отдельное действие
        # пользователя в профиле, как и для купленной косметики.
        from app.models.user_cosmetic import UserCosmetic

        exists = (
            db.query(UserCosmetic)
            .filter(
                UserCosmetic.user_id == current_user.id,
                UserCosmetic.cosmetic_id == challenge.badge_key,
            )
            .first()
        )
        if not exists:
            db.add(
                UserCosmetic(
                    user_id=current_user.id,
                    cosmetic_id=challenge.badge_key,
                )
            )

    progress.reward_claimed_at = utcnow()
    db.commit()

    return ChallengeClaimResponse(
        message="Награда начислена",
        xp_reward=challenge.xp_reward,
        coin_reward=challenge.coin_reward,
        badge_key=challenge.badge_key,
        new_xp=current_user.xp or 0,
        new_coin_balance=current_user.coin_balance or 0,
    )


@router.post(
    "",
    response_model=ChallengeOut,
    summary="Создать сезонный челлендж (администрация)",
)
def create_challenge(
    payload: ChallengeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_rank(RANK_ADMINISTRATOR)),
):
    challenge = Challenge(created_by=admin.id, **payload.model_dump())
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return _to_out(challenge, None)


@router.get(
    "",
    response_model=List[ChallengeOut],
    summary="Список всех челленджей, включая неактивные/прошедшие (администрация)",
)
def list_all_challenges(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_rank(RANK_ADMINISTRATOR)),
):
    challenges = db.query(Challenge).order_by(Challenge.created_at.desc()).all()
    return [_to_out(c, None) for c in challenges]


@router.patch(
    "/{challenge_id}",
    response_model=ChallengeOut,
    summary="Изменить челлендж — например, досрочно снять с публикации (администрация)",
)
def update_challenge(
    challenge_id: str,
    payload: ChallengeUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_rank(RANK_ADMINISTRATOR)),
):
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Челлендж не найден")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(challenge, field, value)

    db.commit()
    db.refresh(challenge)
    return _to_out(challenge, None)
