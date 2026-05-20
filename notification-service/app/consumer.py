"""
RabbitMQ consumer para notification-service.

Escucha la cola 'notifications' y por cada mensaje crea
una fila en la tabla notifications para cada user_id destinatario.

Los demás servicios publican en esta cola con el schema NotificationEvent.
"""
import json
import logging

import aio_pika

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models.notification import Notification
from app.schemas.notification import NotificationEvent

logger = logging.getLogger(__name__)

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None

QUEUE_NAME = "notifications"
EXCHANGE_NAME = "ticketflow"


async def start_consumer() -> None:
    """Conecta a RabbitMQ con reintentos y arranca el consumer en background."""
    global _connection, _channel
    import asyncio
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            _connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL,
                timeout=10,
            )
            _channel = await _connection.channel()
            await _channel.set_qos(prefetch_count=10)

            exchange = await _channel.declare_exchange(
                EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
            )
            queue = await _channel.declare_queue(QUEUE_NAME, durable=True)
            await queue.bind(exchange, routing_key="notification.#")

            await queue.consume(_on_message)
            logger.info("[NotifService] Consumer RabbitMQ iniciado — escuchando '%s'", QUEUE_NAME)
            return  # éxito, salir
        except Exception as exc:
            logger.warning(
                "[NotifService] Intento %d/%d — No se pudo conectar a RabbitMQ: %s",
                attempt, max_retries, exc,
            )
            if attempt < max_retries:
                await asyncio.sleep(3)

    logger.error("[NotifService] No se pudo conectar a RabbitMQ después de %d intentos", max_retries)


async def stop_consumer() -> None:
    # Cierra la conexión al apagar el servicio.
    global _connection
    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("[NotifService] Conexión RabbitMQ cerrada")


async def _on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    # Callback: persiste una notificación por cada destinatario en user_ids.
    async with message.process(requeue=False):
        try:
            payload = NotificationEvent(**json.loads(message.body))
        except Exception as exc:
            logger.error("[NotifService] Mensaje inválido ignorado: %s | body: %s", exc, message.body)
            return

        async with AsyncSessionLocal() as db:
            try:
                for user_id in payload.user_ids:
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
                    "[NotifService] Notificación '%s' persistida para %d usuario(s) | ticket #%s",
                    payload.type,
                    len(payload.user_ids),
                    payload.ticket_id,
                )
            except Exception as exc:
                await db.rollback()
                logger.error("[NotifService] Error persistiendo notificación: %s", exc)
