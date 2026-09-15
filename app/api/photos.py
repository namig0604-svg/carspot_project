import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.photo import Photo
from app.models.user import User
from app.utils.auth import get_current_active_user

router = APIRouter()

UPLOAD_DIR = "uploads"

# Создаём папку если её нет
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_photo(
    event_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Загрузить фото к событию"""
    try:
        # Генерируем уникальное имя файла
        file_extension = file.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        
        # Сохраняем файл
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Создаём запись в БД
        new_photo = Photo(
            event_id=event_id,
            user_id=current_user.id,
            photo_url=f"/uploads/{file_name}",
            photo_key=file_name,
            mime_type=file.content_type,
            is_approved=True,
            is_featured=False
        )
        
        db.add(new_photo)
        db.commit()
        db.refresh(new_photo)
        
        return {
            "id": new_photo.id,
            "url": new_photo.photo_url,
            "event_id": event_id,
            "user_id": current_user.id,
            "created_at": new_photo.created_at
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/event/{event_id}")
def get_event_photos(event_id: str, db: Session = Depends(get_db)):
    """Получить все фото события"""
    photos = db.query(Photo).filter(Photo.event_id == event_id).all()
    return photos

@router.delete("/{photo_id}")
def delete_photo(
    photo_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Удалить фото"""
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    if photo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your photo")
    
    try:
        # Удаляем файл
        os.remove(os.path.join(UPLOAD_DIR, photo.photo_key))
        
        # Удаляем запись из БД
        db.delete(photo)
        db.commit()
        
        return {"message": "Photo deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{photo_id}/like")
def like_photo(
    photo_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Лайкнуть фото"""
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    photo.likes_count += 1
    db.commit()
    db.refresh(photo)
    
    return {"likes_count": photo.likes_count}