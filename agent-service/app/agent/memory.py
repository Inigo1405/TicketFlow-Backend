"""
Per-client memory: stores and retrieves the recurring problem patterns for each client.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import ClientMemory
from app.agent.knowledge import index_client_memory

logger = logging.getLogger(__name__)


async def get_client_memory_text(client_id: int, db: AsyncSession) -> str:
    """Return client memory formatted as plain text for injection into prompts."""
    result = await db.execute(
        select(ClientMemory)
        .where(ClientMemory.client_id == client_id)
        .order_by(ClientMemory.frequency.desc())
        .limit(10)
    )
    memories = result.scalars().all()

    if not memories:
        return "Sin historial previo registrado para este cliente."

    lines = ["Historial de problemas conocidos del cliente:"]
    for m in memories:
        area = m.tic_area or "sin área"
        resolution = m.resolution_summary or "sin resolución registrada"
        lines.append(
            f"  • [{area}] {m.problem_summary} "
            f"(veces: {m.frequency}, resolución: {resolution})"
        )
    return "\n".join(lines)


async def upsert_client_memory(
    client_id: int,
    problem_summary: str,
    resolution_summary: str,
    tic_area: str,
    db: AsyncSession,
) -> None:
    """Increment frequency if the client has a similar problem; otherwise create a new entry."""
    result = await db.execute(
        select(ClientMemory).where(
            ClientMemory.client_id == client_id,
            ClientMemory.tic_area == tic_area,
        )
    )
    existing = result.scalars().first()

    if existing:
        existing.frequency += 1
        existing.problem_summary = problem_summary
        existing.resolution_summary = resolution_summary
        existing.last_seen = datetime.now(timezone.utc)
        record = existing
    else:
        record = ClientMemory(
            client_id=client_id,
            tic_area=tic_area,
            problem_summary=problem_summary,
            resolution_summary=resolution_summary,
        )
        db.add(record)
    await db.flush()
    # Index in Qdrant so the profile is searchable by vector similarity.
    # Non-fatal: embedding failures must not break the main interaction flow.
    try:
        await index_client_memory(record)
    except Exception as exc:
        logger.warning("[TICBot] Error indexando perfil de cliente %s en Qdrant: %s", client_id, exc)
