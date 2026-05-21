import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.database import engine, AsyncSessionLocal
from app.models import user as user_model
from app.models.user import User
from app.routers import auth, users
from app.core.redis_client import init_redis, close_redis
from app.core.security import hash_password
from seed import USERS


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


async def seed_if_empty() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.id).limit(1))
        if result.scalar_one_or_none() is not None:
            logging.info("Seed skip: users table not empty.")
            return
        for u in USERS:
            session.add(User(
                name=u["name"],
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
                area=u["area"],
            ))
            try:
                await session.commit()
                logging.info("Seeded user: %s", u["email"])
            except IntegrityError:
                await session.rollback()
                logging.info("Seed skip: %s already exists.", u["email"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crea las tablas en la base de datos al iniciar la aplicación. En producción, esto se haría con migraciones.
    async with engine.begin() as conn:
        await conn.run_sync(user_model.Base.metadata.create_all)
    await seed_if_empty()
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
