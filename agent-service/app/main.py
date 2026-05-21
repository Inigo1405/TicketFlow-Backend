from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.db.vector_db import init_collections, close_vector_client
from app.routers import categorize, interact, notes, qa, knowledge, memory, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_collections()
    yield
    await close_vector_client()


app = FastAPI(
    title="TicketFlow Agent Service",
    version="1.0.0",
    description="TICBot — Agente inteligente con RAG para el departamento TIC.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All agent endpoints live under /agent
app.include_router(categorize.router, prefix="/agent", tags=["categorize"])
app.include_router(interact.router, prefix="/agent", tags=["interact"])
app.include_router(notes.router, prefix="/agent", tags=["notes"])
app.include_router(qa.router, prefix="/agent", tags=["qa"])
app.include_router(knowledge.router, prefix="/agent", tags=["knowledge"])
app.include_router(memory.router, prefix="/agent", tags=["memory"])
app.include_router(admin.router, prefix="/agent", tags=["admin"])


@app.get("/agent/health")
async def health():
    return {"status": "ok", "service": "agent-service"}
