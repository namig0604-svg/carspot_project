"""
Лента уведомлений: заявки в друзья, лайки профиля, кто присоединился
к твоей сходке, комментарии. Сами уведомления создаются в других роутерах
через services.notify() — здесь только чтение и отметка прочитанным.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.models.notification import DeviceToken, Notification
from app.models.user import User
from app.schemas.notification import (
    DeviceTokenIn,
    NotificationListResponse,
    NotificationOut,
    UnreadCountOut,
)
from app.schemas.user import UserPublic
from app.services import users_by_ids

router = APIRouter()


@router.get("/", response_model=NotificationListResponse, summary="Лента уведомлений")
def list_notifications(
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    total = query.count()
    unread_count = query.filter(Notification.is_read.is_(False)).count()

    rows = (
        query.order_by(Notification.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )

    actor_map = users_by_ids(db, [r.actor_id for r in rows if r.actor_id])
    items = []
    for r in rows:
        item = NotificationOut.model_validate(r)
        actor = actor_map.get(r.actor_id) if r.actor_id else None
        if actor:
            item.actor = UserPublic.model_validate(actor)
        items.append(item)

    return NotificationListResponse(
        total=total,
        unread_count=unread_count,
        limit=page.limit,
        offset=page.offset,
        items=items,
    )


@router.get("/unread-count", response_model=UnreadCountOut, summary="Сколько непрочитанных")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    count = (
        db.query(Notification.id)
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .count()
    )
    return UnreadCountOut(unread_count=count)


@router.post("/read-all", summary="Отметить все уведомления прочитанными")
def read_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read.is_(False)
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"message": "Все уведомления отмечены прочитанными"}


@router.post("/{notification_id}/read", summary="Отметить одно уведомление прочитанным")
def read_one(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not n:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")

    n.is_read = True
    db.commit()
    return {"message": "Отмечено прочитанным"}


# ──────────────────────────────────────────────── PUSH-ТОКЕНЫ УСТРОЙСТВ ────────────────────────────────────────────────

@router.post("/device-token", summary="Зарегистрировать токен устройства для push")
def register_device_token(
    payload: DeviceTokenIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Выызвается с клиента после логина и при обновлении FCM-токена
    (firebase_messaging сам присылает новый токен время от времени).
    Один и тот же токен переприсылаем на текущего пользователя — это
    покрывает случай выхода из одного аккаунта и входа в другой на том же
    устройстве.
    """
    existing = db.query(DeviceToken).filter(DeviceToken.token == payload.token).first()
    if existing:
        existing.user_id = current_user.id
        existing.platform = payload.platform
    else:
        db.add(DeviceToken(user_id=current_user.id, token=payload.token, platform=payload.platform))
    db.commit()
    return {"message": "Токен зарегистрирован"}


@router.delete("/device-token", summary="Удалить токен устройства (например, при выходе)")
def remove_device_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    db.query(DeviceToken).filter(
        DeviceToken.token == token, DeviceToken.user_id == current_user.id
    ).delete(synchronize_session=False)
    db.commit()
    return {"message": "Токен удалён"}
