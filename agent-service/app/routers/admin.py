"""
GET  /agent/admin/stats   — system stats for the admin panel (SQL counts + Qdrant)
GET  /agent/admin/memory  — all client memories across all clients
POST /agent/admin/chat    — privileged admin chat with TICBot
"""
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenUser, require_admin
from app.db.database import get_db
from app.db.vector_db import get_vector_client
from app.core.config import settings
from app.models.agent import ClientMemory, KnowledgeBase, QAEntry
from app.schemas.agent import ClientMemoryOut
from app.agent.graph import run_admin_chat

router = APIRouter()


# ── Stats ──────────────────────────────────────────────────────────────────────

class QdrantCollectionInfo(BaseModel):
    name: str
    vectors_count: int
    status: str


class AdminStats(BaseModel):
    knowledge_count: int
    qa_count: int
    memory_count: int
    qdrant: List[QdrantCollectionInfo]


@router.get("/admin/stats", response_model=AdminStats)
async def get_admin_stats(
    _: TokenUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    kb_count = (await db.execute(select(func.count()).select_from(KnowledgeBase))).scalar() or 0
    qa_count = (await db.execute(select(func.count()).select_from(QAEntry))).scalar() or 0
    mem_count = (await db.execute(select(func.count()).select_from(ClientMemory))).scalar() or 0

    qdrant = await get_vector_client()
    qdrant_info = []
    for name in [settings.COLLECTION_KNOWLEDGE, settings.COLLECTION_QA, settings.COLLECTION_CLIENTS]:
        try:
            info = await qdrant.get_collection(name)
            qdrant_info.append(QdrantCollectionInfo(
                name=name,
                vectors_count=info.points_count or 0,
                status=str(getattr(info, "status", "ok")).replace("CollectionStatus.", "").lower(),
            ))
        except Exception:
            qdrant_info.append(QdrantCollectionInfo(name=name, vectors_count=0, status="error"))

    return AdminStats(
        knowledge_count=kb_count,
        qa_count=qa_count,
        memory_count=mem_count,
        qdrant=qdrant_info,
    )


# ── All client memories ────────────────────────────────────────────────────────

@router.get("/admin/memory", response_model=List[ClientMemoryOut])
async def get_all_memories(
    _: TokenUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClientMemory)
        .order_by(ClientMemory.frequency.desc(), ClientMemory.last_seen.desc())
    )
    return result.scalars().all()


# ── Admin chat ─────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class AdminChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


class AdminChatResponse(BaseModel):
    reply: str


@router.post("/admin/chat", response_model=AdminChatResponse)
async def admin_chat(
    body: AdminChatRequest,
    _: TokenUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    reply = await run_admin_chat(
        message=body.message,
        history=[{"role": h.role, "content": h.content} for h in body.history],
        db=db,
    )
    return AdminChatResponse(reply=reply)
