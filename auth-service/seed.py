"""
Script para crear el usuario Admin inicial.
Uso: python seed.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, Base


USERS = [
    {
        "name": "Admin Demo",
        "email": "admin@ticketflow.com",
        "password": "admin1234",
        "role": "Admin",
        "area": None,
    },
    {
        "name": "Agente Backend",
        "email": "agente@ticketflow.com",
        "password": "agente1234",
        "role": "Agente",
        "area": "backend_services",
    },
    {
        "name": "Usuario Demo",
        "email": "usuario@ticketflow.com",
        "password": "usuario1234",
        "role": "Cliente",
        "area": None,
    },
]


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        for u in USERS:
            result = await session.execute(select(User).where(User.email == u["email"]))
            if result.scalar_one_or_none():
                print(f"Ya existe: {u['email']}")
                continue
            session.add(User(
                name=u["name"],
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
                area=u["area"],
            ))
            await session.commit()
            print(f"Creado ({u['role']}): {u['email']} / {u['password']}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
