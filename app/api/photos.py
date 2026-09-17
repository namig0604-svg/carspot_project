"""
Фотографии: загрузка к сходкам и машинам, лайки.

Файлы кладутся в локальную папку uploads/. На Railway диск эфемерный —
после передеплоя файлы пропадают. Для продакшена подключите S3/Cloudinary:
достаточно заменить функцию _save_file().
"""
import os
import uuid
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import Pagination, get_current_active_user
from app.models.car import Car
from app.models.event import Event
from app.models.photo import Photo, PhotoLike
from app.models.user import User
from app.schemas.rating import PhotoListResponse, PhotoOut

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _save_file(contents: bytes, filename: str) -> str:
    """Сохраняет файл и возвращает имя. Здесь подключается S3, если нужно."""
    extension = (filename.rsplit(".", 1)[-1] if "." in filename else "jpg").lower()
    if extension not in ("jpg", "jpeg", "png", "webp", "heic"):
        extension = "jpg"

    key = f"{uuid.uuid4().hex}.{extension}"
    path = os.path.join(UPLOAD_DIR, key)
    with open(path, "wb") as f:
        f.write(contents)
    return key


@router.post(
    "/upload",
    response_model=PhotoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить фото",
)
async def upload_photo(
    file: UploadFile = File(..., description="Изображение"),
    event_id: Optional[str] = Form(None),
    car_id: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not event_id and not car_id:
        raise HTTPException(status_code=400, detail="Укажите event_id или car_id")

    if file.content_type and file.content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат: {file.content_type}",
        )

    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. Максимум {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} МБ",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="Файл пустой")

    event = None
    if event_id:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Событие не найдено")

    if car_id:
        car = db.query(Car).filter(Car.id == car_id).first()
        if not car:
            raise HTTPException(status_code=404, detail="Машина не найдена")
        if car.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Это не ваша машина")

    key = _save_file(contents, file.filename or "photo.jpg")

    photo = Photo(
        event_id=event_id,
        car_id=car_id,
        user_id=current_user.id,
        photo_url=f"/uploads/{key}",
        photo_key=key,
        mime_type=file.content_type,
        size_bytes=len(contents),
        caption=caption,
    )
    db.add(photo)

    if event:
        event.photos_count = (event.photos_count or 0) + 1

    db.commit()
    db.refresh(photo)
    return photo


@router.get(
    "/event/{event_id}",
    response_model=PhotoListResponse,
    summary="Фото сходки",
)
def event_photos(
    event_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    query = db.query(Photo).filter(
        Photo.event_id == event_id, Photo.is_approved.is_(True)
    )
    total = query.count()
    items = (
        query.order_by(Photo.is_featured.desc(), Photo.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    return PhotoListResponse(total=total, items=[PhotoOut.model_validate(p) for p in items])


@router.get(
    "/car/{car_id}",
    response_model=PhotoListResponse,
    summary="Фото машины",
)
def car_photos(car_id: str, db: Session = Depends(get_db)):
    items = (
        db.query(Photo)
        .filter(Photo.car_id == car_id, Photo.is_approved.is_(True))
        .order_by(Photo.created_at.desc())
        .all()
    )
    return PhotoListResponse(total=len(items), items=[PhotoOut.model_validate(p) for p in items])


@router.post("/{photo_id}/like", summary="Лайк / снять лайк")
def toggle_like(
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    existing = (
        db.query(PhotoLike)
        .filter(PhotoLike.photo_id == photo_id, PhotoLike.user_id == current_user.id)
        .first()
    )

    if existing:
        db.delete(existing)
        photo.likes_count = max(0, (photo.likes_count or 1) - 1)
        liked = False
    else:
        db.add(PhotoLike(photo_id=photo_id, user_id=current_user.id))
        photo.likes_count = (photo.likes_count or 0) + 1
        liked = True

    db.commit()
    db.refresh(photo)
    return {"liked": liked, "likes_count": photo.likes_count}


@router.delete("/{photo_id}", summary="Удалить фото")
def delete_photo(
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")
    if photo.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Это не ваше фото")

    # Файл с диска
    if photo.photo_key:
        try:
            os.remove(os.path.join(UPLOAD_DIR, photo.photo_key))
        except OSError:
            pass  # файла может уже не быть — не критично

    if photo.event_id:
        event = db.query(Event).filter(Event.id == photo.event_id).first()
        if event:
            event.photos_count = max(0, (event.photos_count or 1) - 1)

    db.query(PhotoLike).filter(PhotoLike.photo_id == photo_id).delete(synchronize_session=False)
    db.delete(photo)
    db.commit()
    return {"message": "Фото удалено", "photo_id": photo_id}
