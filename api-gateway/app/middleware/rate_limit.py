"""
IP-based rate limiting middleware using Redis fixed windows (per minute).
Fails open when Redis is unavailable so requests are never blocked by a Redis outage.
"""
import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

_WINDOW = 60  # seconds

# Stricter limits for sensitive endpoints (path → requests/window)
_LIMITS: dict[str, int] = {
    "/api/auth/login": 10,
}
_DEFAULT_LIMIT = 100


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        redis = get_redis()
        if redis is None:
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        path = request.url.path
        limit = _LIMITS.get(path, _DEFAULT_LIMIT)
        window = int(time.time() // _WINDOW)
        key = f"rate:{ip}:{path}:{window}"

        try:
            count = await redis.incr(key)
            if count == 1:
                # TTL = 2 windows to avoid race on window boundary
                await redis.expire(key, _WINDOW * 2)
            if count > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Demasiadas solicitudes. Intenta más tarde."},
                    headers={"Retry-After": str(_WINDOW)},
                )
        except Exception as exc:
            logger.warning("[RateLimit] Redis error, skipping check: %s", exc)

        return await call_next(request)
