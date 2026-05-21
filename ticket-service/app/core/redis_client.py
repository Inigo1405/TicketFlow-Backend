"""
Redis client for ticket-service.
Provides ticket list and detail caching.
Fails open — if Redis is unavailable operations are skipped gracefully.
"""
import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None

TTL_TICKET = 10   # seconds — individual ticket detail
TTL_LIST   = 10   # seconds — ticket list

LIST_KEY = "tickets:list"


def _ticket_key(ticket_id: int, variant: str) -> str:
    return f"ticket:{ticket_id}:{variant}"


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def init_redis() -> None:
    global _redis
    try:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("[Redis] Connected to %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("[Redis] Could not connect, caching disabled: %s", exc)
        _redis = None


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ── Low-level helpers ─────────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[str]:
    if _redis is None:
        return None
    try:
        return await _redis.get(key)
    except Exception as exc:
        logger.warning("[Redis] cache_get error: %s", exc)
        return None


async def cache_set(key: str, value: str, ttl: int) -> None:
    if _redis is None:
        return
    try:
        await _redis.setex(key, ttl, value)
    except Exception as exc:
        logger.warning("[Redis] cache_set error: %s", exc)


async def cache_delete(*keys: str) -> None:
    if _redis is None:
        return
    try:
        await _redis.delete(*keys)
    except Exception as exc:
        logger.warning("[Redis] cache_delete error: %s", exc)


# ── Invalidation helpers ──────────────────────────────────────────────────────

async def invalidate_ticket(ticket_id: int) -> None:
    """Invalidate detail cache (both variants) + list cache."""
    await cache_delete(
        _ticket_key(ticket_id, "full"),
        _ticket_key(ticket_id, "public"),
        LIST_KEY,
    )


async def invalidate_reply(ticket_id: int) -> None:
    """Invalidate only the detail cache (replies changed, list unaffected)."""
    await cache_delete(
        _ticket_key(ticket_id, "full"),
        _ticket_key(ticket_id, "public"),
    )


async def invalidate_list() -> None:
    """Invalidate only the ticket list cache."""
    await cache_delete(LIST_KEY)
