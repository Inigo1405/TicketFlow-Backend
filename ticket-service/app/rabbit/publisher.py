"""
Publisher ligero de RabbitMQ para ticket-service.
Publica eventos de notificación de forma asíncrona y sin bloquear.
Los errores de conexión son no fatales: se loguean y se ignoran.
"""
import json
import logging

import aio_pika

from app.core.config import settings

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "ticketflow"
ROUTING_KEY = "notification.event"


async def publish_notification(payload: dict) -> None:
    """
    Publica un NotificationEvent en RabbitMQ.

    payload debe cumplir el schema NotificationEvent del notification-service:
    {
        "user_ids": [int, ...],
        "type": str,          # ver NotificationType
        "title": str,
        "message": str,
        "ticket_id": int | None
    }
    """
    try:
        conn = await aio_pika.connect_robust(settings.RABBITMQ_URL, timeout=5)
        async with conn:
            channel = await conn.channel()
            exchange = await channel.declare_exchange(
                EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
            )
            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps(payload).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=ROUTING_KEY,
            )
            logger.info(
                "[Publisher] Notificación '%s' publicada para %d usuario(s)",
                payload.get("type"),
                len(payload.get("user_ids", [])),
            )
    except Exception as exc:
        # Las notificaciones son best-effort: nunca deben bloquear la operación principal
        logger.warning("[Publisher] No se pudo publicar notificación en RabbitMQ: %s", exc)
