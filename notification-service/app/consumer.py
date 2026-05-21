"""
RabbitMQ consumer para notification-service.

Escucha la cola 'notifications' y por cada mensaje:
  1. Resuelve notify_roles → IDs de usuario llamando a auth-service.
  2. Persiste una fila en `notifications` por destinatario.
  3. Si send_email=True, envía correo a los user_ids vía EmailJS.
"""
import json
import logging

import aio_pika
import httpx

from app.core.config import settings
from app.core.emailjs import send_notification_email
from app.core.redis_client import email_setnx
from app.db.database import AsyncSessionLocal
from app.models.notification import Notification
from app.schemas.notification import NotificationEvent

logger = logging.getLogger(__name__)

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None

QUEUE_NAME    = "notifications"
EXCHANGE_NAME = "ticketflow"


# ── Helpers para consultar auth-service ──────────────────────────────────────

async def _fetch_users_by_role(role: str) -> list[dict]:
    """Devuelve lista de {id, email, name} para todos los usuarios con el rol dado."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.AUTH_SERVICE_URL}/users/internal/by-role/{role}")
            if r.status_code == 200:
                return r.json()
    except Exception as exc:
        logger.warning("[NotifService] No se pudo obtener usuarios rol '%s': %s", role, exc)
    return []


async def _fetch_user_info(user_id: int) -> dict | None:
    """Devuelve {id, email, name} de un usuario o None si no existe."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.AUTH_SERVICE_URL}/users/internal/{user_id}")
            if r.status_code == 200:
                return r.json()
    except Exception as exc:
        logger.warning("[NotifService] No se pudo obtener usuario %d: %s", user_id, exc)
    return None


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def start_consumer() -> None:
    """Conecta a RabbitMQ con reintentos y arranca el consumer en background."""
    global _connection, _channel
    import asyncio
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL, timeout=10)
            _channel    = await _connection.channel()
            await _channel.set_qos(prefetch_count=10)

            exchange = await _channel.declare_exchange(
                EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
            )
            queue = await _channel.declare_queue(QUEUE_NAME, durable=True)
            await queue.bind(exchange, routing_key="notification.#")

            await queue.consume(_on_message)
            logger.info("[NotifService] Consumer RabbitMQ iniciado — escuchando '%s'", QUEUE_NAME)
            return
        except Exception as exc:
            logger.warning(
                "[NotifService] Intento %d/%d — No se pudo conectar a RabbitMQ: %s",
                attempt, max_retries, exc,
            )
            if attempt < max_retries:
                await asyncio.sleep(3)
    logger.error("[NotifService] No se pudo conectar a RabbitMQ después de %d intentos", max_retries)


async def stop_consumer() -> None:
    global _connection
    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("[NotifService] Conexión RabbitMQ cerrada")


# ── Message handler ───────────────────────────────────────────────────────────

async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        try:
            payload = NotificationEvent(**json.loads(message.body))
        except Exception as exc:
            logger.error("[NotifService] Mensaje inválido ignorado: %s | body: %s", exc, message.body)
            return

        # ── 1. Resolver notify_roles → IDs adicionales ────────────────────────
        role_user_ids: list[int] = []
        if payload.notify_roles:
            for role in payload.notify_roles:
                users = await _fetch_users_by_role(role)
                for u in users:
                    if u["id"] not in payload.user_ids and u["id"] not in role_user_ids:
                        role_user_ids.append(u["id"])

        all_user_ids = list(payload.user_ids) + role_user_ids

        if not all_user_ids:
            logger.warning("[NotifService] Notificación '%s' sin destinatarios, ignorada", payload.type)
            return

        # ── 2. Persistir notificaciones ───────────────────────────────────────
        async with AsyncSessionLocal() as db:
            try:
                for user_id in all_user_ids:
                    db.add(
                        Notification(
                            user_id=user_id,
                            type=payload.type,
                            title=payload.title,
                            message=payload.message,
                            ticket_id=payload.ticket_id,
                        )
                    )
                await db.commit()
                logger.info(
                    "[NotifService] '%s' persistida para %d destinatario(s) | ticket #%s",
                    payload.type, len(all_user_ids), payload.ticket_id,
                )
            except Exception as exc:
                await db.rollback()
                logger.error("[NotifService] Error persistiendo notificación: %s", exc)
                return

        # ── 3. Enviar emails a user_ids (no a role_user_ids) ─────────────────
        if payload.send_email and payload.user_ids:
            for user_id in payload.user_ids:
                first_time = await email_setnx(user_id, payload.ticket_id, payload.type)
                if not first_time:
                    logger.info(
                        "[NotifService] Email deduplicado para user %d ticket #%s tipo '%s'",
                        user_id, payload.ticket_id, payload.type,
                    )
                    continue
                user_info = await _fetch_user_info(user_id)
                if user_info:
                    await send_notification_email(user_info, payload)

