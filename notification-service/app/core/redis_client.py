"""
Cliente Redis para notification-service.
Se usa exclusivamente para deduplicar envíos de email.
"""
import logging
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None

EMAIL_DEDUP_TTL = 3600  # 1 hora — ventana dentro de la cual no se repite el email


async def init_redis() -> None:
    global _redis
    try:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("[Redis/NotifService] Conectado a %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("[Redis/NotifService] No disponible, dedup de email desactivado: %s", exc)
        _redis = None


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def email_setnx(user_id: int, ticket_id: int | None, event_type: str) -> bool:
    """
    Marca un email como 'ya enviado' usando SETNX + TTL.
    Devuelve True si es la primera vez (se debe enviar el email).
    Devuelve False si ya se envió recientemente (skip).
    Falla abierto (True) si Redis no está disponible.
    """
    if _redis is None:
        return True
    key = f"email_sent:{user_id}:{ticket_id or 'none'}:{event_type}"
    try:
        sent = await _redis.set(key, "1", nx=True, ex=EMAIL_DEDUP_TTL)
        return bool(sent)
    except Exception as exc:
        logger.warning("[Redis/NotifService] email_setnx error: %s", exc)
        return True  # fail open
