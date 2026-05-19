"""
Knowledge base operations: index documents and semantic search via Qdrant.
"""
import uuid
from typing import Optional

from qdrant_client.http.models import PointStruct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agent.embeddings import embed_with_retry
from app.core.config import settings
from app.db.vector_db import get_vector_client
from app.models.agent import KnowledgeBase, QAEntry


# ── Generic semantic search ──────────────────────────────────────────────────

async def semantic_search(query: str, collection: str, limit: int = 5) -> list[dict]:
    """Return ranked results from a Qdrant collection."""
    vector = await embed_with_retry(query)
    client = await get_vector_client()
    response = await client.query_points(
        collection_name=collection,
        query=vector,
        limit=limit,
        with_payload=True,
    )
    return [{"score": round(r.score, 4), **r.payload} for r in response.points]


def _format_search_results(results: list[dict], label: str) -> str:
    if not results:
        return f"No se encontraron resultados en {label}."
    lines = [f"Resultados de {label}:"]
    for i, r in enumerate(results, 1):
        title = r.get("title", r.get("problem", "Sin título"))
        content = r.get("content", r.get("solution", ""))[:300]
        score = r.get("score", 0)
        lines.append(f"  {i}. [{score:.2f}] {title}\n     {content}")
    return "\n".join(lines)


# ── Knowledge Base ────────────────────────────────────────────────────────────

async def search_knowledge(query: str) -> str:
    results = await semantic_search(query, settings.COLLECTION_KNOWLEDGE)
    return _format_search_results(results, "base de conocimiento")


async def index_knowledge(entry: KnowledgeBase) -> str:
    """Embed and upsert a KnowledgeBase row into Qdrant. Returns the vector_id."""
    text = f"{entry.title}\n{entry.content}"
    vector = await embed_with_retry(text)
    point_id = str(uuid.uuid4())
    client = await get_vector_client()
    await client.upsert(
        collection_name=settings.COLLECTION_KNOWLEDGE,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "title": entry.title,
                    "content": entry.content,
                    "category": entry.category or "",
                    "db_id": entry.id,
                },
            )
        ],
    )
    return point_id


# ── QA entries ───────────────────────────────────────────────────────────────

async def search_qa(query: str) -> str:
    results = await semantic_search(query, settings.COLLECTION_QA)
    return _format_search_results(results, "base de QA")


async def index_qa_entry(entry: QAEntry) -> str:
    """Embed and upsert a QAEntry into Qdrant. Returns the vector_id."""
    text = f"Problema: {entry.problem}\nSolución: {entry.solution}"
    vector = await embed_with_retry(text)
    point_id = str(uuid.uuid4())
    client = await get_vector_client()
    await client.upsert(
        collection_name=settings.COLLECTION_QA,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "problem": entry.problem,
                    "solution": entry.solution,
                    "tic_area": entry.tic_area or "",
                    "source_ticket_id": entry.source_ticket_id,
                    "db_id": entry.id,
                },
            )
        ],
    )
    return point_id


async def save_qa_to_db(
    problem: str,
    solution: str,
    tic_area: Optional[str],
    source_ticket_id: Optional[int],
    db: AsyncSession,
) -> QAEntry:
    """Persist a QA entry to PostgreSQL and index it in Qdrant."""
    entry = QAEntry(
        problem=problem,
        solution=solution,
        tic_area=tic_area,
        source_ticket_id=source_ticket_id,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    point_id = await index_qa_entry(entry)
    entry.vector_id = point_id
    await db.flush()
    return entry


# ── Client profiles ───────────────────────────────────────────────────────────

async def index_client_memory(memory) -> None:
    """
    Embed a ClientMemory record and upsert it into the client_profiles Qdrant collection.
    Uses a deterministic UUID5 keyed on (client_id, tic_area) so repeated calls
    overwrite the same point instead of creating duplicates.
    """
    text = (
        f"Problema recurrente: {memory.problem_summary}\n"
        f"Cómo se resolvió: {memory.resolution_summary or 'sin resolución registrada'}"
    )
    vector = await embed_with_retry(text)
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{memory.client_id}:{memory.tic_area}"))
    client = await get_vector_client()
    await client.upsert(
        collection_name=settings.COLLECTION_CLIENTS,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "client_id": memory.client_id,
                    "tic_area": memory.tic_area or "",
                    "problem_summary": memory.problem_summary,
                    "resolution_summary": memory.resolution_summary or "",
                    "frequency": memory.frequency,
                },
            )
        ],
    )


async def search_client_profile(query: str) -> str:
    results = await semantic_search(query, settings.COLLECTION_CLIENTS)
    if not results:
        return "No se encontraron casos similares en el historial de clientes."
    lines = ["Casos similares resueltos con otros clientes:"]
    for i, r in enumerate(results, 1):
        area = r.get("tic_area", "sin área")
        problem = r.get("problem_summary", "")[:250]
        resolution = r.get("resolution_summary", "sin resolución")[:250]
        freq = r.get("frequency", 1)
        score = r.get("score", 0)
        lines.append(
            f"  {i}. [{score:.2f}] [{area}] (visto {freq}x)\n"
            f"     Problema: {problem}\n"
            f"     Resolución: {resolution}"
        )
    return "\n".join(lines)
