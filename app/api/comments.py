"""
Комментарии — общие для сходок и фото. Путь один для обоих типов:
target_type = "event" | "photo", target_id — id самой сходки/фото.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.models.comment import COMMENT_TARGET_TYPES, Comment
from app.models.event import Event
from app.models.photo import Photo
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentListResponse, CommentOut
from app.schemas.user import UserPublic
from app.services import notify, users_by_ids

router = APIRouter()


def _validate_target_type(target_type: str) -> None:
    if target_type not in COMMENT_TARGET_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"target_type должен быть одним из: {', '.join(COMMENT_TARGET_TYPES)}",
        )


def _resolve_owner_id(db: Session, target_type: str, target_id: str) -> str:
    """Проверяет, что объект существует, и возвращает id владельца (для уведомления)."""
    if target_type == "event":
        event = db.query(Event).filter(Event.id == target_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Сходка не найдена")
        return event.creator_id

    photo = db.query(Photo).filter(Photo.id == target_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")
    return photo.user_id


def _target_label(db: Session, target_type: str, target_id: str) -> str:
    if target_type == "event":
        event = db.query(Event).filter(Event.id == target_id).first()
        return f"твою сходку «{event.title}»" if event else "твою сходку"
    return "твоё фото"


@router.get(
    "/{target_type}/{target_id}",
    response_model=CommentListResponse,
    summary="Список комментариев",
)
def list_comments(
    target_type: str,
    target_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _validate_target_type(target_type)

    query = db.query(Comment).filter(
        Comment.target_type == target_type,
        Comment.target_id == target_id,
        Comment.is_deleted.is_(False),
    )
    total = query.count()
    rows = (
        query.order_by(Comment.created_at.asc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )

    user_map = users_by_ids(db, [r.user_id for r in rows])
    items = []
    for r in rows:
        item = CommentOut.model_validate(r)
        user = user_map.get(r.user_id)
        if user:
            item.user = UserPublic.model_validate(user)
        item.is_mine = r.user_id == current_user.id
        items.append(item)

    return CommentListResponse(total=total, limit=page.limit, offset=page.offset, items=items)


@router.post(
    "/{target_type}/{target_id}",
    response_model=CommentOut,
    status_code=201,
    summary="Оставить комментарий",
)
def create_comment(
    target_type: str,
    target_id: str,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _validate_target_type(target_type)
    owner_id = _resolve_owner_id(db, target_type, target_id)

    comment = Comment(
        target_type=target_type,
        target_id=target_id,
        user_id=current_user.id,
        text=payload.text,
    )
    db.add(comment)
    db.flush()

    notify(
        db,
        user_id=owner_id,
        type=f"comment_{target_type}",
        actor_id=current_user.id,
        target_type=target_type,
        target_id=target_id,
        message=f"{current_user.username} прокомментировал(а) {_target_label(db, target_type, target_id)}",
    )

    db.commit()
    db.refresh(comment)

    out = CommentOut.model_validate(comment)
    out.user = UserPublic.model_validate(current_user)
    out.is_mine = True
    return out


@router.delete("/{comment_id}", summary="Удалить комментарий")
def delete_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")
    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Это не ваш комментарий")

    comment.is_deleted = True
    db.commit()
    return {"message": "Комментарий удалён"}
