"""
GET    /agent/memory/{client_id}  — list client memory entries
DELETE /agent/memory/{client_id}  — clear all memory for a client
"""
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.auth import TokenUser, require_agent_or_admin
from app.db.database import get_db
from app.models.agent import ClientMemory
from app.schemas.agent import ClientMemoryOut

router = APIRouter()


@router.get("/memory/{client_id}", response_model=List[ClientMemoryOut])
async def get_client_memory(
    client_id: int,
    _: TokenUser = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClientMemory)
        .where(ClientMemory.client_id == client_id)
        .order_by(ClientMemory.frequency.desc())
    )
    return result.scalars().all()


@router.delete("/memory/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_client_memory(
    client_id: int,
    _: TokenUser = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(ClientMemory).where(ClientMemory.client_id == client_id))
    await db.flush()
