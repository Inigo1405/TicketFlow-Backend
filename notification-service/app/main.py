from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.consumer import start_consumer, stop_consumer
from app.core.redis_client import init_redis, close_redis
from app.routers import notifications

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    logger = logging.getLogger(__name__)
    logger.info("[NotifService] Iniciando startup...")
    await init_db()
    logger.info("[NotifService] DB lista, conectando a Redis...")
    await init_redis()
    logger.info("[NotifService] Redis listo, conectando a RabbitMQ...")
    await start_consumer()
    logger.info("[NotifService] Startup completo")
    yield
    await stop_consumer()
    await close_redis()


app = FastAPI(
    title="Notification Service",
    version="1.0.0",
    description="Gestiona y entrega notificaciones en tiempo real para TicketFlow.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "notification-service"}
