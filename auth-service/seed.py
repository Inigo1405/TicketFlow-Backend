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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        result = await session.execute(select(User).where(User.email == "admin@ticketflow.com"))
        if result.scalar_one_or_none():
            print("Admin ya existe.")
            return

        admin = User(
            name="Administrador",
            email="admin@ticketflow.com",
            hashed_password=hash_password("admin1234"),
            role="Admin",
        )
        session.add(admin)
        await session.commit()
        print("Admin creado: admin@ticketflow.com / admin1234")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
