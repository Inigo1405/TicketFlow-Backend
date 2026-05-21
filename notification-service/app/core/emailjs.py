"""
Cliente EmailJS para notification-service.
Envía correos usando la REST API de EmailJS.
Falla silenciosamente — un error de email nunca bloquea la persistencia de notificaciones.
"""
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_EMAILJS_API = "https://api.emailjs.com/api/v1.0/email/send"

_TYPE_LABELS: dict[str, str] = {
    "ticket_created":  "Ticket creado",
    "ticket_resolved": "Ticket resuelto",
    "ticket_closed":   "Ticket cerrado",
    "new_reply":       "Nueva respuesta",
}


async def send_notification_email(user_info: dict, event) -> None:
    """
    Envía un correo de notificación al usuario vía EmailJS REST API.

    Args:
        user_info: dict con keys 'email' y 'name'
        event: NotificationEvent
    """
    if not all([settings.EMAILJS_SERVICE_ID, settings.EMAILJS_TEMPLATE_ID, settings.EMAILJS_PUBLIC_KEY]):
        logger.debug("[EmailJS] Credenciales no configuradas, email omitido")
        return

    if not settings.EMAILJS_PRIVATE_KEY:
        logger.warning("[EmailJS] EMAILJS_PRIVATE_KEY no configurada — requerida para llamadas server-side")
        return
    to_email = user_info.get("email")
    if not to_email:
        return

    type_label = _TYPE_LABELS.get(event.type, event.type)
    ticket_url = f"{settings.FRONTEND_URL}/my-tickets"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _EMAILJS_API,
                json={
                    "service_id":   settings.EMAILJS_SERVICE_ID,
                    "template_id":  settings.EMAILJS_TEMPLATE_ID,
                    "user_id":      settings.EMAILJS_PUBLIC_KEY,
                    "accessToken":  settings.EMAILJS_PRIVATE_KEY,
                    "template_params": {
                        "to_name":   user_info.get("name", "Usuario"),
                        "to_email":  to_email,
                        "subject":   event.title,
                        "message":   event.message,
                        "ticket_id": str(event.ticket_id or ""),
                        "type_label": type_label,
                        "ticket_url": ticket_url,
                    },
                },
            )
        if resp.status_code == 200:
            logger.info("[EmailJS] Email enviado a %s (%s)", to_email, event.type)
        else:
            logger.warning("[EmailJS] Respuesta %d para %s: %s", resp.status_code, to_email, resp.text)
    except Exception as exc:
        logger.warning("[EmailJS] Error enviando email a %s: %s", to_email, exc)
