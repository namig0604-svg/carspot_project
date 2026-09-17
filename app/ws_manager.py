"""
Менеджер WebSocket-соединений для чатов в реальном времени.

Держит соединения в памяти процесса. Для одного инстанса на Railway этого
достаточно. При масштабировании на несколько инстансов сюда нужно добавить
Redis Pub/Sub — точка расширения помечена ниже.
"""
import asyncio
from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # room_id -> набор активных сокетов
        self._rooms: Dict[str, Set[WebSocket]] = {}
        # websocket -> user_id (чтобы знать, кто отправитель)
        self._users: Dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id: str, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms.setdefault(room_id, set()).add(websocket)
            self._users[websocket] = user_id

    async def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(room_id)
            if room:
                room.discard(websocket)
                if not room:
                    self._rooms.pop(room_id, None)
            self._users.pop(websocket, None)

    async def broadcast(self, room_id: str, payload: dict) -> None:
        """Рассылает JSON всем в комнате. Мёртвые соединения выбрасывает."""
        # TODO(масштабирование): здесь публиковать в Redis, а подписчик — рассылать
        async with self._lock:
            sockets = list(self._rooms.get(room_id, set()))

        dead = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)

        if dead:
            async with self._lock:
                room = self._rooms.get(room_id)
                for ws in dead:
                    if room:
                        room.discard(ws)
                    self._users.pop(ws, None)

    def online_count(self, room_id: str) -> int:
        return len(self._rooms.get(room_id, set()))


manager = ConnectionManager()
