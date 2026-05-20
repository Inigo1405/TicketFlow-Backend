"""
GET    /agent/knowledge       — list knowledge base entries
POST   /agent/knowledge       — add entry (indexes in Qdrant)
DELETE /agent/knowledge/{id}  — remove entry
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import TokenUser, require_agent_or_admin
from app.db.database import get_db
from app.db.vector_db import get_vector_client
from app.agent.knowledge import index_knowledge
from app.core.config import settings
from app.models.agent import KnowledgeBase
from app.schemas.agent import KnowledgeCreate, KnowledgeOut

router = APIRouter()


@router.get("/knowledge", response_model=List[KnowledgeOut])
async def list_knowledge(
    _: TokenUser = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()))
    return result.scalars().all()


@router.post("/knowledge", response_model=KnowledgeOut, status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    body: KnowledgeCreate,
    _: TokenUser = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    entry = KnowledgeBase(title=body.title, content=body.content, category=body.category)
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    point_id = await index_knowledge(entry)
    entry.vector_id = point_id
    await db.flush()
    return entry


@router.delete("/knowledge/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge(
    entry_id: int,
    _: TokenUser = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrada no encontrada")

    # Remove from Qdrant if indexed
    if entry.vector_id:
        try:
            qdrant = await get_vector_client()
            await qdrant.delete(
                collection_name=settings.COLLECTION_KNOWLEDGE,
                points_selector=[entry.vector_id],
            )
        except Exception:
            pass

    await db.delete(entry)
    await db.flush()
