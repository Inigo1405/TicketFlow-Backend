from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.db.database import engine
from app.models import user as user_model
from app.routers import auth, users
from app.core.redis_client import init_redis, close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crea las tablas en la base de datos al iniciar la aplicación. En producción, esto se haría con migraciones.
    async with engine.begin() as conn:
        await conn.run_sync(user_model.Base.metadata.create_all)
    await init_redis()
    yield
    await close_redis()


app = FastAPI(title="Auth Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-service"}
