import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.http_client import close_clients
from app.core.redis_client import init_redis, close_redis
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import auth, tickets, notifications, agent


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield
    # Al finalizar el ciclo de vida de la aplicación, cerramos los clientes HTTP para liberar recursos.
    await close_clients()
    await close_redis()



app = FastAPI(
    title="TicketFlow API Gateway",
    version="1.0.0",
    description="Punto de entrada único — enruta al auth-service, ticket-service y notification-service.",
    lifespan=lifespan,
)


# ── Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # En producción, restringir a los dominios frontend específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware)



# ── Routers — all under /api ──
app.include_router(auth.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(agent.router, prefix="/api")



@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}
