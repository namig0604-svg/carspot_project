"""
Админка: рассмотрение жалоб, блокировка пользователей.
Доступ — только пользователям с is_admin=True (см. app.deps.require_admin).
"""
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, require_admin
from app.models.base import utcnow
from app.models.business import Business
from app.models.report import REPORT_STATUSES, REPORT_TARGET_TYPES, Report
from app.models.user import User
from app.osm_import import element_to_business_fields, fetch_overpass_elements
from app.schemas.business import OsmImportResult
from app.schemas.report import (
    ReportListResponse,
    ReportOut,
    ReportResolve,
    UserBanPayload,
)
from app.schemas.user import UserAdminOut, UserPublic
from app.services import users_by_ids

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
        elements = fetch_overpass_elements(country)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Не удалось получить данные с Overpass API: {exc}",
        )

    created = 0
    updated = 0
    skipped = 0

    for el in elements:
        fields = element_to_business_fields(el)
        if not fields:
            skipped += 1
            continue

        osm_id = fields["osm_id"]
        existing = db.query(Business).filter(Business.osm_id == osm_id).first()

        if existing:
            if not dry_run:
                for key, value in fields.items():
                    if key == "osm_id":
                        continue
                    # Не затираем то, что владелец/админ мог вручную заполнить
                    # (описание, услуги, инста) — обновляем только "сырые" поля из OSM.
                    if key in ("description", "services", "instagram") and getattr(existing, key):
                        continue
                    setattr(existing, key, value)
            updated += 1
        else:
            if not dry_run:
                db.add(Business(owner_id=None, **fields))
            created += 1

    if not dry_run:
        db.commit()

    return OsmImportResult(
        found_in_osm=len(elements),
        created=created,
        updated=updated,
        skipped=skipped,
        dry_run=dry_run,
    )
