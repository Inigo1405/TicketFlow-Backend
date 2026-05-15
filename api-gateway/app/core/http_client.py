"""
Cliente HTTP asíncrono compartido (httpx) para el gateway.
Un cliente por servicio mantiene activos los pools de conexiones.
"""
import httpx
from app.core.config import settings

# Timeouts: 5s connect, 30s read
_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)

auth_client = httpx.AsyncClient(base_url=settings.AUTH_SERVICE_URL, timeout=_TIMEOUT)
ticket_client = httpx.AsyncClient(base_url=settings.TICKET_SERVICE_URL, timeout=_TIMEOUT)
notification_client = httpx.AsyncClient(base_url=settings.NOTIFICATION_SERVICE_URL, timeout=_TIMEOUT)


async def close_clients():
    await auth_client.aclose()
    await ticket_client.aclose()
    await notification_client.aclose()
