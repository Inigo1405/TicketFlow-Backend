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


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        result = await session.execute(select(User).where(User.email == "usuario@ticketflow.com"))
        if result.scalar_one_or_none():
            print("Usuario ya existe.")
            return

        cliente = User(
            name="Usuario Demo",
            email="usuario@ticketflow.com",
            hashed_password=hash_password("usuario1234"),
            role="Cliente",
        )
        session.add(cliente)
        await session.commit()
        print("Cliente creado: usuario@ticketflow.com / usuario1234")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
