"""
Истории — фото, видимое 24 часа. Загрузка похожа на /api/photos/upload,
лента — по друзьям (+ свои же истории всегда видны себе).
"""
import os
import uuid
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_active_user
from app.models.base import utcnow
from app.models.friendship import Friendship
from app.models.story import STORY_LIFETIME_HOURS, Story, StoryView
from app.models.user import User
from app.schemas.story import StoryFeedResponse, StoryOut, StoryRingOut
from app.schemas.user import UserPublic
from app.services import users_by_ids

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _save_file(contents: bytes, filename: str) -> str:
    extension = (filename.rsplit(".", 1)[-1] if "." in filename else "jpg").lower()
    if extension not in ("jpg", "jpeg", "png", "webp", "heic"):
        extension = "jpg"
    key = f"{uuid.uuid4().hex}.{extension}"
    path = os.path.join(UPLOAD_DIR, key)
    with open(path, "wb") as f:
        f.write(contents)
    return key


def _not_expired_filter():
    cutoff = utcnow() - timedelta(hours=STORY_LIFETIME_HOURS)
    return Story.created_at >= cutoff


def _friend_ids(db: Session, user_id: str) -> List[str]:
    rows = (
        db.query(Friendship)
        .filter(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        )
        .all()
    )
    return [
        r.addressee_id if r.requester_id == user_id else r.requester_id
        for r in rows
    ]


def _story_to_out(story: Story, current_user_id: str, viewed_ids: set) -> StoryOut:
    out = StoryOut.model_validate(story)
    out.expires_at = story.created_at + timedelta(hours=STORY_LIFETIME_HOURS)
    out.is_mine = story.user_id == current_user_id
    out.is_viewed = story.id in viewed_ids
    return out


@router.post(
    "/upload",
    response_model=StoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Опубликовать историю",
)
async def upload_story(
    file: UploadFile = File(..., description="Изображение"),
    caption: Optional[str] = Form(None),
    event_id: Optional[str] = Form(None),
    car_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if file.content_type and file.content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый формат: {file.content_type}")

    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. Максимум {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} МБ",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="Файл пустой")

    key = _save_file(contents, file.filename or "story.jpg")

    story = Story(
        user_id=current_user.id,
        image_url=f"/uploads/{key}",
        image_key=key,
        caption=caption,
        event_id=event_id,
        car_id=car_id,
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    return _story_to_out(story, current_user.id, set())


@router.get("/feed", response_model=StoryFeedResponse, summary="Лента историй (друзья + свои)")
def stories_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    author_ids = list({current_user.id, *_friend_ids(db, current_user.id)})

    stories = (
        db.query(Story)
        .filter(Story.user_id.in_(author_ids), _not_expired_filter())
        .order_by(Story.created_at.desc())
        .all()
    )
    if not stories:
        return StoryFeedResponse(items=[])

    viewed_ids = {
        row[0]
        for row in db.query(StoryView.story_id)
        .filter(
            StoryView.viewer_id == current_user.id,
            StoryView.story_id.in_([s.id for s in stories]),
        )
        .all()
    }

    grouped: dict = {}
    for story in stories:
        bucket = grouped.setdefault(story.user_id, {"count": 0, "unseen": False, "latest": story.created_at})
        bucket["count"] += 1
        if story.id not in viewed_ids and story.user_id != current_user.id:
            bucket["unseen"] = True
        if story.created_at > bucket["latest"]:
            bucket["latest"] = story.created_at

    user_map = users_by_ids(db, list(grouped.keys()))

    items = [
        StoryRingOut(
            user=UserPublic.model_validate(user_map[uid]),
            stories_count=data["count"],
            has_unseen=data["unseen"],
            latest_created_at=data["latest"],
        )
        for uid, data in grouped.items()
        if uid in user_map
    ]

    # Свои истории — всегда первые, иначе непросмотренные вперёд остальных.
    items.sort(key=lambda r: (r.user.id != current_user.id, not r.has_unseen, -r.latest_created_at.timestamp()))
    return StoryFeedResponse(items=items)


@router.get("/user/{user_id}", response_model=List[StoryOut], summary="Истории пользователя")
def user_stories(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    stories = (
        db.query(Story)
        .filter(Story.user_id == user_id, _not_expired_filter())
        .order_by(Story.created_at.asc())
        .all()
    )
    if not stories:
        return []

    existing_views = {
        row[0]
        for row in db.query(StoryView.story_id)
        .filter(
            StoryView.viewer_id == current_user.id,
            StoryView.story_id.in_([s.id for s in stories]),
        )
        .all()
    }

    # Просматривая чужие истории — отмечаем как просмотренные и считаем уникальный просмотр.
    viewed_now = set(existing_views)
    if user_id != current_user.id:
        for story in stories:
            if story.id not in existing_views:
                db.add(StoryView(story_id=story.id, viewer_id=current_user.id))
                story.views_count = (story.views_count or 0) + 1
                viewed_now.add(story.id)
        db.commit()

    return [_story_to_out(s, current_user.id, viewed_now) for s in stories]


@router.delete("/{story_id}", summary="Удалить историю")
def delete_story(
    story_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail="История не найдена")
    if story.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Это не ваша история")

    if story.image_key:
        try:
            os.remove(os.path.join(UPLOAD_DIR, story.image_key))
        except OSError:
            pass

    db.query(StoryView).filter(StoryView.story_id == story_id).delete(synchronize_session=False)
    db.delete(story)
    db.commit()
    return {"message": "История удалена"}
