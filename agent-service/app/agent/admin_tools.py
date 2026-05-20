"""
Admin-only LangChain tools for TICBot's privileged chat mode.
All tools are created via a factory bound to the current db session.
"""
from langchain_core.tools import tool
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.vector_db import get_vector_client
from app.core.config import settings
from app.models.agent import ClientMemory, KnowledgeBase, QAEntry
from app.agent.knowledge import index_knowledge


def make_admin_tools(db: AsyncSession) -> list:
    """Factory: returns DB inspection tools bound to the current AsyncSession."""

    @tool
    async def get_db_stats() -> str:
        """Get a complete overview of TICBot's databases: SQL record counts and Qdrant vector index stats per collection."""
        kb_count = (await db.execute(select(func.count()).select_from(KnowledgeBase))).scalar() or 0
        qa_count = (await db.execute(select(func.count()).select_from(QAEntry))).scalar() or 0
        mem_count = (await db.execute(select(func.count()).select_from(ClientMemory))).scalar() or 0

        qdrant = await get_vector_client()
        qdrant_lines = []
        for name in [settings.COLLECTION_KNOWLEDGE, settings.COLLECTION_QA, settings.COLLECTION_CLIENTS]:
            try:
                info = await qdrant.get_collection(name)
                points = info.points_count or 0
                qdrant_status = str(getattr(info, "status", "ok")).replace("CollectionStatus.", "").lower()
                qdrant_lines.append(f"  • {name}: {points} vectores ({qdrant_status})")
            except Exception as exc:
                qdrant_lines.append(f"  • {name}: error — {exc}")

        return (
            "=== Estado de las Bases de Datos TICBot ===\n\n"
            "SQL (PostgreSQL):\n"
            f"  • Base de conocimiento : {kb_count} documentos\n"
            f"  • Entradas QA          : {qa_count} pares problema/solución\n"
            f"  • Memorias de clientes : {mem_count} registros\n\n"
            "Qdrant (Vector DB):\n" + "\n".join(qdrant_lines)
        )

    @tool
    async def get_knowledge_entries(limit: int = 20) -> str:
        """List the most recent entries in the internal TIC knowledge base (procedures, policies, guides). Returns title, category and a content preview."""
        result = await db.execute(
            select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()).limit(limit)
        )
        entries = result.scalars().all()
        if not entries:
            return "La base de conocimiento está vacía."
        lines = [f"Base de conocimiento ({len(entries)} documentos mostrados):"]
        for e in entries:
            cat = e.category or "sin categoría"
            preview = e.content[:200].replace("\n", " ")
            lines.append(f"\n  [{e.id}] [{cat}] **{e.title}**\n  {preview}...")
        return "\n".join(lines)

    @tool
    async def get_qa_entries(limit: int = 20) -> str:
        """List the most recent QA problem-solution pairs saved by agents or auto-generated from resolved tickets."""
        result = await db.execute(
            select(QAEntry).order_by(QAEntry.created_at.desc()).limit(limit)
        )
        entries = result.scalars().all()
        if not entries:
            return "No hay entradas QA registradas."
        lines = [f"Entradas QA ({len(entries)} pares mostrados):"]
        for e in entries:
            area = e.tic_area or "sin área"
            ref = f" (Ticket #{e.source_ticket_id})" if e.source_ticket_id else ""
            lines.append(
                f"\n  [{e.id}] [{area}]{ref}\n"
                f"  Problema : {e.problem[:200]}\n"
                f"  Solución : {e.solution[:200]}"
            )
        return "\n".join(lines)

    @tool
    async def get_client_memories(client_id: int = 0, limit: int = 30) -> str:
        """List client memory records. Use client_id > 0 to filter by one client. Use client_id=0 (default) to see all clients sorted by problem frequency."""
        query = select(ClientMemory).order_by(ClientMemory.frequency.desc()).limit(limit)
        if client_id > 0:
            query = query.where(ClientMemory.client_id == client_id)
        result = await db.execute(query)
        memories = result.scalars().all()
        if not memories:
            label = f"cliente #{client_id}" if client_id > 0 else "ningún cliente"
            return f"No hay memorias registradas para {label}."
        label = f"cliente #{client_id}" if client_id > 0 else "todos los clientes"
        lines = [f"Memorias de {label} ({len(memories)} registros):"]
        for m in memories:
            area = m.tic_area or "sin área"
            res = (m.resolution_summary or "sin resolución")[:180]
            lines.append(
                f"\n  [Cliente #{m.client_id}] [{area}] visto {m.frequency}x\n"
                f"  Problema   : {m.problem_summary[:180]}\n"
                f"  Resolución : {res}"
            )
        return "\n".join(lines)

    @tool
    async def save_company_knowledge(title: str, content: str, category: str = "") -> str:
        """Save a new company/TIC knowledge document to the knowledge base and index it in Qdrant for semantic search.
        Use this when the admin provides procedures, policies, or technical guides that TICBot should know.
        Parameters: title (short descriptive name), content (full document text), category (optional, e.g. 'VPN', 'Seguridad', 'Redes')."""
        entry = KnowledgeBase(
            title=title,
            content=content,
            category=category or None,
        )
        db.add(entry)
        await db.flush()
        await db.refresh(entry)
        point_id = await index_knowledge(entry)
        entry.vector_id = point_id
        await db.flush()
        return (
            f"Documento guardado correctamente.\n"
            f"  ID       : {entry.id}\n"
            f"  Título   : {entry.title}\n"
            f"  Categoría: {entry.category or 'sin categoría'}\n"
            f"  Vector ID: {point_id}"
        )

    return [get_db_stats, get_knowledge_entries, get_qa_entries, get_client_memories, save_company_knowledge]
