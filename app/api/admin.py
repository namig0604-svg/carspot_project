"""
Админка: рассмотрение жалоб, блокировка пользователей.
Доступ — только пользователям с is_admin=True (см. app.deps.require_admin).
"""
import time
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, require_admin, require_rank
from app.models.base import utcnow
from app.models.business import Business
from app.models.report import REPORT_STATUSES, REPORT_TARGET_TYPES, Report
from app.models.user import User
from app.geocoding import reverse_geocode_address
from app.ranks import ALL_RANKS, RANK_DEVELOPER, RANK_TECH_ADMIN
from app.osm_import import run_osm_import
from app.schemas.admin import (
    AdminGrantCoinsOut,
    AdminGrantCoinsRequest,
    AdminGrantPremiumOut,
    AdminGrantPremiumRequest,
    AdminRankOut,
    AdminSetRankRequest,
)
from app.schemas.business import OsmImportResult
from app.schemas.report import (
    ReportListResponse,
    ReportOut,
    ReportResolve,
    UserBanPayload,
)
from app.schemas.user import UserAdminOut, UserPublic
from app.services import extend_premium, grant_coins, users_by_ids

router = APIRouter()


@router.get("/reports", response_model=ReportListResponse, summary="Список жалоб")
def list_reports(
    status_filter: Optional[str] = Query(
        None, alias="status", description="pending / resolved / dismissed"
    ),
    target_type: Optional[str] = None,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    query = db.query(Report)

    if status_filter:
        if status_filter not in REPORT_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"status должен быть одним из: {', '.join(REPORT_STATUSES)}",
            )
        query = query.filter(Report.status == status_filter)

    if target_type:
        if target_type not in REPORT_TARGET_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"target_type должен быть одним из: {', '.join(REPORT_TARGET_TYPES)}",
            )
        query = query.filter(Report.target_type == target_type)

    total = query.count()
    reports = (
        query.order_by(Report.status.asc(), Report.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )

    # Одним запросом подгружаем всех авторов жалоб и, если жалоба на
    # пользователя, — самих этих пользователей (против N+1).
    reporter_map = users_by_ids(db, [r.reporter_id for r in reports])
    user_target_ids = [r.target_id for r in reports if r.target_type == "user"]
    target_user_map = users_by_ids(db, user_target_ids) if user_target_ids else {}

    items = []
    for r in reports:
        item = ReportOut.model_validate(r)
        reporter = reporter_map.get(r.reporter_id)
        if reporter:
            item.reporter = UserPublic.model_validate(reporter)
        if r.target_type == "user":
            target_user = target_user_map.get(r.target_id)
            if target_user:
                item.target_user = UserPublic.model_validate(target_user)
        items.append(item)

    return ReportListResponse(total=total, limit=page.limit, offset=page.offset, items=items)


@router.post(
    "/reports/{report_id}/resolve",
    response_model=ReportOut,
    summary="Рассмотреть жалобу",
)
def resolve_report(
    report_id: str,
    payload: ReportResolve,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Жалоба не найдена")

    report.status = payload.status
    report.resolution_note = payload.resolution_note
    report.resolved_by_id = admin.id
    report.resolved_at = utcnow()
    db.commit()
    db.refresh(report)
    return ReportOut.model_validate(report)


@router.get("/users", response_model=List[UserAdminOut], summary="Поиск пользователей (админ)")
def admin_search_users(
    q: Optional[str] = Query(None, description="Поиск по логину/имени/email"),
    banned_only: bool = Query(False),
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    query = db.query(User)
    if banned_only:
        query = query.filter(User.is_active.is_(False))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                User.username.ilike(pattern),
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
            )
        )
    return (
        query.order_by(User.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )


@router.post(
    "/users/{user_id}/ban",
    response_model=UserAdminOut,
    summary="Заблокировать пользователя",
)
def ban_user(
    user_id: str,
    payload: UserBanPayload,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать самого себя")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать администратора")

    user.is_active = False
    user.ban_reason = payload.reason
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/users/{user_id}/unban",
    response_model=UserAdminOut,
    summary="Разблокировать пользователя",
)
def unban_user(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.is_active = True
    user.ban_reason = None
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/import-osm-businesses",
    response_model=OsmImportResult,
    summary="Импорт автосервисов/тюнинг-ателье/шиномонтажей/магазинов запчастей из OpenStreetMap",
)
def import_osm_businesses(
    country: str = Query("GE", description="ISO 3166-1 alpha-2 код страны, напр. GE — Грузия"),
    dry_run: bool = Query(
        False,
        description="Если true — ничего не пишет в БД, только считает, сколько нашлось/добавилось бы/обновилось бы",
    ),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    Заявки на добавление заведения обычно шлют сами владельцы, но каталог
    полезнее, когда он не пустой с первого дня — поэтому админ может одной
    кнопкой подтянуть реальные автосервисы/тюнинг-ателье/шиномонтажи/
    магазины запчастей из OpenStreetMap (открытые данные, ODbL).

    Идемпотентно: каждое заведение из OSM хранит свой osm_id
    ("node/12345" / "way/12345"), повторный запуск обновит уже
    импортированные записи, а не создаст дубликаты. Заведения получают
    owner_id=NULL (как "системные" — их сможет забрать себе владелец через
    поддержку, если объявится).
    """
    try:
        result = run_osm_import(db, country, dry_run=dry_run)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Не удалось получить данные с Overpass API: {exc}",
        )

    return OsmImportResult(
        found_in_osm=result["found_in_osm"],
        created=result["created"],
        updated=result["updated"],
        skipped=result["skipped"],
        dry_run=dry_run,
    )


@router.post(
    "/geocode-business-addresses",
    summary="Заполнить точный адрес заведений через обратное геокодирование (Nominatim)",
)
def geocode_business_addresses(
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="Сколько заведений без адреса обработать за один вызов (Nominatim — не более 1 запроса/сек, поэтому большой limit — долгий вызов)",
    ),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    У части заведений (в первую очередь импортированных из OSM — см.
    /api/admin/import-osm-businesses) нет тегов адреса в исходных данных,
    поэтому поле address пустое. Эта ручка берёт до `limit` таких заведений
    (address IS NULL, но координаты есть) и заполняет адрес через обратное
    геокодирование по координатам (Nominatim, тот же источник, что и OSM).

    Вызывать можно многократно с небольшим limit, пока remaining не станет 0 —
    каждый вызов обрабатывает свою порцию, ничего не дублирует.
    """
    candidates = (
        db.query(Business)
        .filter(Business.address.is_(None))
        .filter(Business.latitude.isnot(None))
        .filter(Business.longitude.isnot(None))
        .order_by(Business.created_at)
        .limit(limit)
        .all()
    )

    updated = 0
    for i, business in enumerate(candidates):
        if i > 0:
            time.sleep(1.1)  # политика Nominatim: не более 1 запроса в секунду
        address = reverse_geocode_address(business.latitude, business.longitude)
        if address:
            business.address = address
            updated += 1

    db.commit()

    remaining = (
        db.query(Business)
        .filter(Business.address.is_(None))
        .filter(Business.latitude.isnot(None))
        .filter(Business.longitude.isnot(None))
        .count()
    )

    return {"processed": len(candidates), "updated": updated, "remaining": remaining}


# ─────────────────────── РАНГИ АДМИНИСТРАЦИИ И РУЧНАЯ ВЫДАЧА МОНЕТ ───────────────────────
# Отдельно от require_admin выше — см. подробный docstring в app/ranks.py.
# Назначать ранги может только разработчик; выдавать монеты вручную — только
# разработчик и тех.администратор.

@router.get(
    "/ranks",
    response_model=List[AdminRankOut],
    summary="Список пользователей с рангом администрации",
)
def list_admin_ranks(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_rank(RANK_TECH_ADMIN)),
):
    return db.query(User).filter(User.admin_rank.isnot(None)).all()


@router.post(
    "/ranks/{user_id}",
    response_model=AdminRankOut,
    summary="Назначить (или снять) ранг администрации — только разработчик",
)
def set_admin_rank(
    user_id: str,
    payload: AdminSetRankRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_rank(RANK_DEVELOPER)),
):
    if payload.rank is not None and payload.rank not in ALL_RANKS:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестный ранг: {payload.rank}. Допустимые: {', '.join(ALL_RANKS)}",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя менять свой собственный ранг через эту ручку")

    user.admin_rank = payload.rank
    # is_admin — общий флаг для старых ручек модерации выше (не трогаем их
    # логику): любой назначенный ранг администрации включает его автоматически,
    # снятие ранга — выключает.
    user.is_admin = payload.rank is not None
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/coins/grant/{user_id}",
    response_model=AdminGrantCoinsOut,
    summary="Выдать монеты пользователю вручную — только разработчик и тех.администратор",
)
def admin_grant_coins(
    user_id: str,
    payload: AdminGrantCoinsRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_rank(RANK_TECH_ADMIN)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    grant_coins(db, user, payload.amount, "admin_grant", reference_id=admin.id)
    db.commit()
    db.refresh(user)
    return AdminGrantCoinsOut(user_id=user.id, balance=user.coin_balance or 0, granted=payload.amount)


@router.post(
    "/premium/grant/{user_id}",
    response_model=AdminGrantPremiumOut,
    summary="Выдать CarSpot Premium (Basic/Pro/Max) пользователю вручную — только разработчик и тех.администратор",
)
def admin_grant_premium(
    user_id: str,
    payload: AdminGrantPremiumRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_rank(RANK_TECH_ADMIN)),
):
    if payload.tier not in ("basic", "pro", "max"):
        raise HTTPException(status_code=400, detail="tier должен быть basic, pro или max")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    extend_premium(user, payload.days, tier=payload.tier)
    db.commit()
    db.refresh(user)
    return AdminGrantPremiumOut(
        user_id=user.id,
        premium_until=user.premium_until.isoformat() if user.premium_until else None,
        premium_tier=user.effective_premium_tier,
    )
