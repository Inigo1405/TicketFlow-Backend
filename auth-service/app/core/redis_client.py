"""
Redis client for auth-service.
Manages JWT blacklist for token revocation.
Fails open — if Redis is unavailable operations are skipped gracefully.
"""
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def init_redis() -> None:
    global _redis
    try:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("[Redis] Connected to %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("[Redis] Could not connect, blacklist disabled: %s", exc)
        _redis = None


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ── Blacklist helpers ─────────────────────────────────────────────────────────

async def blacklist_token(jti: str, ttl_seconds: int) -> None:
    """Store a token JTI in the blacklist with TTL = remaining token lifetime."""
    if _redis is None or ttl_seconds <= 0:
        return
    try:
        await _redis.setex(f"blacklist:{jti}", ttl_seconds, "1")
    except Exception as exc:
        logger.warning("[Redis] blacklist_token error: %s", exc)


async def is_blacklisted(jti: str) -> bool:
    """Return True if the JTI is in the blacklist (token revoked)."""
    if _redis is None:
        return False
    try:
        return await _redis.exists(f"blacklist:{jti}") > 0
    except Exception as exc:
        logger.warning("[Redis] is_blacklisted error: %s", exc)
        return False
