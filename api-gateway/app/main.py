from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.http_client import close_clients
from app.middleware.request_id import RequestIDMiddleware
from app.routers import auth, tickets, notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Al finalizar el ciclo de vida de la aplicación, cerramos los clientes HTTP para liberar recursos.
    await close_clients()


app = FastAPI(
    title="TicketFlow API Gateway",
    version="1.0.0",
    description="Punto de entrada único — enruta al auth-service, ticket-service y notification-service.",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # En producción, restringir a los dominios frontend específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

# ── Routers — all under /api ──────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}
