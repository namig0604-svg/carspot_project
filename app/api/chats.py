"""
Чаты: личные, чаты сходок и клубов.
REST — история и отправка, WebSocket — реальное время.
"""
import os
import uuid
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.deps import Pagination, get_current_active_user
from app.models.base import utcnow
from app.models.chat import ChatMember, ChatMessage, ChatRoom
from app.models.user import User
from app.schemas.chat import (
    ChatImageUploadOut,
    DirectChatCreate,
    MessageCreate,
    MessageListResponse,
    MessageOut,
    RoomDetail,
    RoomOut,
)
from app.schemas.user import UserPublic
from app.security import decode_access_token
from app.services import (
    get_or_create_direct_room,
    is_room_member,
    touch_room,
    users_by_ids,
)
from app.ws_manager import manager

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_room_or_404(db: Session, room_id: str) -> ChatRoom:
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Чат не найден")
    return room


def _require_member(db: Session, room_id: str, user_id: str) -> None:
    if not is_room_member(db, room_id, user_id):
        raise HTTPException(status_code=403, detail="Вы не участник этого чата")


def _save_chat_image(contents: bytes, filename: str) -> str:
    """Сохраняет картинку чата и возвращает публичный URL. Как в photos.py —
    на Railway диск эфемерный, для продакшена стоит подключить S3/Cloudinary."""
    extension = (filename.rsplit(".", 1)[-1] if "." in filename else "jpg").lower()
    if extension not in ("jpg", "jpeg", "png", "webp", "heic"):
        extension = "jpg"
    key = f"{uuid.uuid4().hex}.{extension}"
    path = os.path.join(UPLOAD_DIR, key)
    with open(path, "wb") as f:
        f.write(contents)
    return f"/uploads/{key}"


@router.get("/", response_model=List[RoomOut], summary="Мои чаты")
def my_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    my_memberships = (
        db.query(ChatMember)
        .filter(ChatMember.user_id == current_user.id)
        .all()
    )
    if not my_memberships:
        return []

    my_membership_by_room = {m.room_id: m for m in my_memberships}
    room_ids = list(my_membership_by_room.keys())

    rooms = (
        db.query(ChatRoom)
        .filter(ChatRoom.id.in_(room_ids), ChatRoom.is_active.is_(True))
        .order_by(ChatRoom.last_message_at.desc())
        .all()
    )
    if not rooms:
        return []

    # Все участники всех этих чатов — одним запросом, чтобы не дёргать БД в цикле.
    all_members = (
        db.query(ChatMember)
        .filter(ChatMember.room_id.in_([r.id for r in rooms]))
        .all()
    )
    members_by_room: dict = {}
    for m in all_members:
        members_by_room.setdefault(m.room_id, []).append(m)

    other_user_ids = {
        m.user_id for m in all_members if m.user_id != current_user.id
    }
    online_ids = set()
    if other_user_ids:
        online_ids = {
            u.id
            for u in db.query(User).filter(User.id.in_(other_user_ids)).all()
            if u.is_online
        }

    items = []
    for room in rooms:
        room_members = members_by_room.get(room.id, [])
        my_member = my_membership_by_room.get(room.id)

        unread = 0
        if my_member:
            unread_query = db.query(ChatMessage).filter(
                ChatMessage.room_id == room.id,
                ChatMessage.is_deleted.is_(False),
                ChatMessage.user_id != current_user.id,
            )
            if my_member.last_read_at:
                unread_query = unread_query.filter(ChatMessage.created_at > my_member.last_read_at)
            unread = unread_query.count()

        other_online = sum(
            1 for m in room_members if m.user_id != current_user.id and m.user_id in online_ids
        )

        item = RoomOut.model_validate(room)
        item.unread_count = unread
        item.members_count = len(room_members)
        item.other_online_count = other_online
        items.append(item)

    return items


@router.post("/direct", response_model=RoomOut, summary="Открыть личный чат")
def open_direct_chat(
    payload: DirectChatCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя написать самому себе")

    other = db.query(User).filter(User.id == payload.user_id).first()
    if not other:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    room = get_or_create_direct_room(db, current_user.id, other.id)
    if not room.title:
        room.title = other.username

    db.commit()
    db.refresh(room)
    return room


@router.get("/{room_id}", response_model=RoomDetail, summary="Информация о чате")
def get_room(
    room_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    room = _get_room_or_404(db, room_id)
    _require_member(db, room_id, current_user.id)

    member_rows = db.query(ChatMember).filter(ChatMember.room_id == room_id).all()
    user_map = users_by_ids(db, [m.user_id for m in member_rows])

    me = next((m for m in member_rows if m.user_id == current_user.id), None)
    unread = 0
    if me and me.last_read_at:
        unread = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.room_id == room_id,
                ChatMessage.created_at > me.last_read_at,
                ChatMessage.user_id != current_user.id,
                ChatMessage.is_deleted.is_(False),
            )
            .count()
        )

    other_online = sum(
        1
        for m in member_rows
        if m.user_id != current_user.id and user_map.get(m.user_id) and user_map[m.user_id].is_online
    )

    detail = RoomDetail.model_validate(room)
    detail.members = [UserPublic.model_validate(u) for u in user_map.values()]
    detail.unread_count = unread
    detail.members_count = len(member_rows)
    detail.other_online_count = other_online
    return detail


@router.get(
    "/{room_id}/messages",
    response_model=MessageListResponse,
    summary="История сообщений",
)
def list_messages(
    room_id: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_room_or_404(db, room_id)
    _require_member(db, room_id, current_user.id)

    query = db.query(ChatMessage).filter(
        ChatMessage.room_id == room_id, ChatMessage.is_deleted.is_(False)
    )
    total = query.count()

    messages = (
        query.order_by(ChatMessage.created_at.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    messages.reverse()  # клиенту удобнее от старых к новым

    user_map = users_by_ids(db, [m.user_id for m in messages])
    items = []
    for m in messages:
        item = MessageOut.model_validate(m)
        user = user_map.get(m.user_id)
        if user:
            item.user = UserPublic.model_validate(user)
        items.append(item)

    # отмечаем прочитанным
    me = (
        db.query(ChatMember)
        .filter(ChatMember.room_id == room_id, ChatMember.user_id == current_user.id)
        .first()
    )
    if me:
        me.last_read_at = utcnow()
        db.commit()

    return MessageListResponse(
        room_id=room_id,
        total=total,
        limit=page.limit,
        offset=page.offset,
        items=items,
    )


@router.post(
    "/{room_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить сообщение",
)
async def send_message(
    room_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_room_or_404(db, room_id)
    _require_member(db, room_id, current_user.id)

    if not payload.text and not payload.image_url:
        raise HTTPException(status_code=400, detail="Сообщение не может быть пустым")

    message = ChatMessage(
        room_id=room_id,
        user_id=current_user.id,
        text=payload.text,
        image_url=payload.image_url,
        message_type=payload.message_type or "text",
    )
    db.add(message)
    touch_room(db, room_id, payload.text or "[фото]")
    db.commit()
    db.refresh(message)

    out = MessageOut.model_validate(message)
    out.user = UserPublic.model_validate(current_user)

    # Рассылаем всем, кто сейчас в комнате по WebSocket
    await manager.broadcast(room_id, {"type": "message", "data": out.model_dump(mode="json")})

    return out


@router.post(
    "/{room_id}/upload-image",
    response_model=ChatImageUploadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить фото для сообщения в чат",
)
async def upload_chat_image(
    room_id: str,
    file: UploadFile = File(..., description="Изображение"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_room_or_404(db, room_id)
    _require_member(db, room_id, current_user.id)

    # Content-Type от клиента ненадёжен (Flutter/http шлёт application/octet-stream
    # по умолчанию, если не указать contentType явно) — проверяем по расширению файла,
    # как и при сохранении в _save_chat_image.
    filename = file.filename or ""
    extension = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if extension not in ("jpg", "jpeg", "png", "webp", "heic"):
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только изображения: jpg, png, webp, heic",
        )

    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. Максимум {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} МБ",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="Файл пустой")

    image_url = _save_chat_image(contents, file.filename or "photo.jpg")
    return ChatImageUploadOut(image_url=image_url)


@router.delete("/{room_id}/messages/{message_id}", summary="Удалить своё сообщение")
def delete_message(
    room_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    message = (
        db.query(ChatMessage)
        .filter(ChatMessage.id == message_id, ChatMessage.room_id == room_id)
        .first()
    )
    if not message:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    if message.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Это не ваше сообщение")

    message.is_deleted = True
    db.commit()
    return {"message": "Сообщение удалено", "message_id": message_id}


@router.post("/{room_id}/read", summary="Отметить чат прочитанным")
def mark_read(
    room_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    member = (
        db.query(ChatMember)
        .filter(ChatMember.room_id == room_id, ChatMember.user_id == current_user.id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="Вы не участник этого чата")

    member.last_read_at = utcnow()
    db.commit()
    return {"message": "Отмечено прочитанным"}


# ─────────────────────────── WEBSOCKET ───────────────────────────

@router.websocket("/ws/{room_id}")
async def chat_websocket(
    websocket: WebSocket,
    room_id: str,
    token: Optional[str] = Query(None, description="JWT-токен"),
):
    """
    Реальное время для чата.

    Подключение:  wss://<домен>/api/chats/ws/{room_id}?token=<JWT>

    Присланный JSON вида {"text": "привет"} сохраняется и рассылается
    всем участникам комнаты.
    """
    user_id = decode_access_token(token) if token else None
    if not user_id:
        await websocket.close(code=4401)  # unauthorized
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not is_room_member(db, room_id, user_id):
            await websocket.close(code=4403)  # forbidden
            return
        username = user.username
    finally:
        db.close()

    await manager.connect(room_id, user_id, websocket)
    await manager.broadcast(
        room_id,
        {"type": "presence", "data": {"user_id": user_id, "username": username, "status": "online"}},
    )

    try:
        while True:
            data = await websocket.receive_json()

            # Пинг для поддержания соединения
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # Индикатор «печатает»
            if data.get("type") == "typing":
                await manager.broadcast(
                    room_id,
                    {"type": "typing", "data": {"user_id": user_id, "username": username}},
                )
                continue

            text = (data.get("text") or "").strip()
            image_url = data.get("image_url")
            if not text and not image_url:
                continue

            session = SessionLocal()
            try:
                message = ChatMessage(
                    room_id=room_id,
                    user_id=user_id,
                    text=text or None,
                    image_url=image_url,
                    message_type="image" if image_url and not text else "text",
                )
                session.add(message)
                touch_room(session, room_id, text or "[фото]")
                session.commit()
                session.refresh(message)

                payload = {
                    "id": message.id,
                    "room_id": message.room_id,
                    "user_id": message.user_id,
                    "username": username,
                    "text": message.text,
                    "image_url": message.image_url,
                    "message_type": message.message_type,
                    "created_at": message.created_at.isoformat(),
                }
            finally:
                session.close()

            await manager.broadcast(room_id, {"type": "message", "data": payload})

    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001  — не роняем сервер из-за одного сокета
        pass
    finally:
        await manager.disconnect(room_id, websocket)
        await manager.broadcast(
            room_id,
            {
                "type": "presence",
                "data": {"user_id": user_id, "username": username, "status": "offline"},
            },
        )
