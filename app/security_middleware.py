"""
Практическое усиление безопасности API — три лёгких middleware без внешних
зависимостей (Redis и т.п. не нужен, приложение однопроцессное на Railway,
поэтому обычный dict в памяти процесса работает надёжно):

  1. RateLimitMiddleware — троттлинг по IP. Отдельный, гораздо более строгий
     лимит на "чувствительные" ручки (/api/auth/login, /register, /token,
     /forgot-password, /reset-password) — защита от перебора паролей и
     спама регистраций/писем. Общий, более мягкий лимит на все остальные
     ручки — базовая защита от простого флуда одним клиентом (не настоящий
     анти-DDoS, для этого нужна защита на уровне инфраструктуры — см. отчёт
     SECURITY_AUDIT.md, но отсекает дешёвые/автоматизированные перегрузки).

  2. SecurityHeadersMiddleware — стандартные защитные HTTP-заголовки на
     каждом ответе (X-Content-Type-Options, X-Frame-Options, HSTS и т.д.).

  3. MaxBodySizeMiddleware — отклоняет запросы с телом больше разумного
     предела ДО того, как оно будет прочитано целиком — защита от простого
     "залить огромный JSON" DoS (отдельно от MAX_UPLOAD_SIZE — там лимит на
     сами файлы, свои проверки в app/api/photos.py и т.п.).
"""
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


def _client_ip(request: Request) -> str:
    """
    Railway (как и большинство PaaS) стоит за обратным прокси — реальный IP
    клиента приходит в X-Forwarded-For (первый адрес в списке), а
    request.client.host был бы адресом самого прокси. Если заголовка нет
    (локальный запуск, тесты) — используем request.client.host как есть.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# path -> (макс. запросов, окно в секундах). Проверяется точным совпадением
# request.url.path (без query-параметров).
_STRICT_LIMITS = {
    "/api/auth/login": (10, 300),
    "/api/auth/token": (10, 300),
    "/api/auth/register": (8, 600),
    "/api/auth/forgot-password": (5, 600),
    "/api/auth/reset-password": (10, 600),
}
# Общий лимит на всё остальное — щедрый, чтобы не мешать обычному
# использованию приложения (лента, карта, чаты и т.п. дают много запросов).
_GENERAL_LIMIT = (300, 300)

# Сколько последних окон храним в памяти на один ключ (IP+путь) — старые
# записи вычищаются лениво, при каждом обращении к этому же ключу, поэтому
# отдельный фоновый cleanup-цикл не нужен.
_MAX_TRACKED_KEYS = 50_000


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        limit, window = _STRICT_LIMITS.get(path, _GENERAL_LIMIT)
        ip = _client_ip(request)
        key = f"{ip}:{path}" if path in _STRICT_LIMITS else f"{ip}:*"

        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = max(1, int(window - (now - hits[0])))
            return JSONResponse(
                status_code=429,
                content={"detail": "Слишком много запросов, попробуйте позже"},
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)

        # Грубая защита от неограниченного роста словаря, если кто-то будет
        # слать запросы с огромного числа разных IP/путей одновременно.
        if len(self._hits) > _MAX_TRACKED_KEYS:
            cutoff = now - max(window for _, window in _STRICT_LIMITS.values()) - _GENERAL_LIMIT[1]
            for k in list(self._hits.keys()):
                dq = self._hits[k]
                if not dq or dq[-1] < cutoff:
                    del self._hits[k]

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        # HSTS: Railway отдаёт HTTPS "из коробки", браузерам/клиентам говорим
        # год не пытаться ходить по http:// вообще.
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """
    Отклоняет запрос по Content-Length ДО чтения тела — если заголовка нет
    (chunked upload), пропускаем: реальный лимит на файлы всё равно
    проверяется отдельно в местах загрузки (app/api/photos.py и т.п.), а тут
    нужна была бы обёртка над ASGI receive() для честного стриминга — лишняя
    сложность ради редкого кейса без Content-Length.
    """

    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Тело запроса слишком большое"},
                    )
            except ValueError:
                pass
        return await call_next(request)
