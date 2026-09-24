"""
Live-геолокация на карте: "поделиться позицией" + кто её видит.

Пользователь включает трансляцию своей метки и выбирает, кому она видна:
"everyone" (все), "friends" (только друзья) или "club" (только соклубники —
общий клуб с пользователем). REST-ручки — для настроек и разового снимка,
WebSocket — для обновления в реальном времени (как в app/api/chats.py).
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.deps import get_current_active_user
from app.models.base import utcnow
from app.models.club import ClubMember
from app.models.friendship import Friendship
from app.models.user import User
from app.security import decode_access_token
from app.services import pair_key_for

router = APIRouter()

LOCATION_VISIBILITY = ("everyone", "friends", "club")


class LocationShareIn(BaseModel):
    enabled: bool
    visibility: Optional[str] = Field(
        default=None, description="everyone / friends / club"
    )


class LocationShareOut(BaseModel):
    share_location: bool
    location_visibility: str


class LocationPeerOut(BaseModel):
    user_id: str
    username: str
    avatar_url: Optional[str] = None
    lat: float
    lng: float
    updated_at: str


def _is_friend(db: Session, a: str, b: str) -> bool:
    key = pair_key_for(a, b)
    fr = (
        db.query(Friendship)
        .filter(Friendship.pair_key == key, Friendship.status == "accepted")
        .first()
    )
    return fr is not None


def _shares_club(db: Session, a: str, b: str) -> bool:
    a_clubs = {
        row[0]
        for row in db.query(ClubMember.club_id)
        .filter(ClubMember.user_id == a, ClubMember.status == "approved")
        .all()
    }
    if not a_clubs:
        return False
    exists = (
        db.query(ClubMember.id)
        .filter(
            ClubMember.user_id == b,
            ClubMember.status == "approved",
            ClubMember.club_id.in_(a_clubs),
        )
        .first()
    )
    return exists is not None


def _visible_to(db: Session, viewer_id: str, target: User) -> bool:
    """Видна ли метка target'а пользователю viewer_id, по его настройке приватности."""
    if target.id == viewer_id:
        return True
    visibility = target.location_visibility or "everyone"
    if visibility == "everyone":
        return True
    if visibility == "friends":
        return _is_friend(db, viewer_id, target.id)
    if visibility == "club":
        return _shares_club(db, viewer_id, target.id)
    return False


def _peer_out(user: User) -> LocationPeerOut:
    return LocationPeerOut(
        user_id=user.id,
        username=user.username,
        avatar_url=user.avatar_url,
        lat=user.last_lat,
        lng=user.last_lng,
        updated_at=(user.location_updated_at or utcnow()).isoformat(),
    )


@router.post("/share", response_model=LocationShareOut, summary="Включить/выключить трансляцию геопозиции")
def set_sharing(
    payload: LocationShareIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.visibility is not None and payload.visibility not in LOCATION_VISIBILITY:
        raise HTTPException(status_code=400, detail="Некорректная настройка видимости")

    current_user.share_location = payload.enabled
    if payload.visibility is not None:
        current_user.location_visibility = payload.visibility
    if not payload.enabled:
        # Выключили — метка сразу пропадает у всех, не просто "замирает" на месте.
        current_user.last_lat = None
        current_user.last_lng = None
    db.commit()
    return LocationShareOut(
        share_location=current_user.share_location,
        location_visibility=current_user.location_visibility,
    )


@router.get("/settings", response_model=LocationShareOut, summary="Мои текущие настройки геолокации")
def get_settings(current_user: User = Depends(get_current_active_user)):
    return LocationShareOut(
        share_location=current_user.share_location,
        location_visibility=current_user.location_visibility,
    )


@router.get(
    "/nearby",
    response_model=List[LocationPeerOut],
    summary="Снимок: кто сейчас делится позицией и виден мне",
)
def list_nearby(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    candidates = (
        db.query(User)
        .filter(
            User.share_location.is_(True),
            User.last_lat.isnot(None),
            User.last_lng.isnot(None),
            User.id != current_user.id,
        )
        .all()
    )
    return [_peer_out(u) for u in candidates if _visible_to(db, current_user.id, u)]


# ─────────────────────────── WEBSOCKET ─────────────────────────
# Один общий "канал" (не комнаты, как в чатах) — карта живых меток общая
# для всего приложения, видимость фильтруется на сервере под каждого
# получателя отдельно.

_connections: Dict[str, WebSocket] = {}


async def _broadcast_position(db: Session, user: User) -> None:
    payload = {"type": "location", "data": _peer_out(user).model_dump()}
    for viewer_id, ws in list(_connections.items()):
        if viewer_id == user.id:
            continue
        if _visible_to(db, viewer_id, user):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001
                pass


async def _broadcast_offline(user_id: str) -> None:
    payload = {"type": "offline", "data": {"user_id": user_id}}
    for viewer_id, ws in list(_connections.items()):
        if viewer_id == user_id:
            continue
        try:
            await ws.send_json(payload)
        except Exception:  # noqa: BLE001
            pass


@router.websocket("/ws")
async def location_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT-токен"),
):
    """
    Реальное время для живых меток на карте.

    Подключение: wss://<домен>/api/location/ws?token=<JWT>

    Клиент шлёт {"lat":.., "lng":..} при каждом обновлении своей позиции —
    сервер сохраняет её (и автоматически включает share_location, если была
    выключена) и рассылает всем, кому она видна по настройке приватности.
    При подключении сервер сразу шлёт снепшот всех, кто сейчас виден.
    """
    user_id = decode_access_token(token) if token else None
    if not user_id:
        await websocket.close(code=4401)  # unauthorized
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.close(code=4403)
            return

        await websocket.accept()
        _connections[user_id] = websocket

        candidates = (
            db.query(User)
            .filter(
                User.share_location.is_(True),
                User.last_lat.isnot(None),
                User.id != user_id,
            )
            .all()
        )
        for peer in candidates:
            if _visible_to(db, user_id, peer):
                await websocket.send_json(
                    {"type": "location", "data": _peer_out(peer).model_dump()}
                )

        try:
            while True:
                data = await websocket.receive_json()

                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                lat = data.get("lat")
                lng = data.get("lng")
                if lat is None or lng is None:
                    continue

                user.last_lat = float(lat)
                user.last_lng = float(lng)
                user.location_updated_at = utcnow()
                if not user.share_location:
                    user.share_location = True
                db.commit()

                await _broadcast_position(db, user)
        except WebSocketDisconnect:
            pass
        except Exception:  # noqa: BLE001 — не роняем сервер из-за одного сокета
            pass
    finally:
        _connections.pop(user_id, None)
        db.close()
        await _broadcast_offline(user_id)
