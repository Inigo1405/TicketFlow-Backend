from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.consumer import start_consumer, stop_consumer
from app.routers import notifications

import logging
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    logger = logging.getLogger(__name__)
    logger.info("[NotifService] Iniciando startup...")
    await init_db()
    logger.info("[NotifService] DB lista, conectando a RabbitMQ...")
    await start_consumer()
    logger.info("[NotifService] Startup completo")
    yield
    await stop_consumer()


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
