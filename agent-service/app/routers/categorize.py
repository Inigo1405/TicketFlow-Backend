"""POST /agent/categorize/{ticket_id}"""
import logging
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.auth import TokenUser, require_agent_or_admin
from app.core.config import settings, create_service_token
from app.db.database import AsyncSessionLocal
from app.agent.graph import run_categorize, run_notes, run_interact
from app.agent.knowledge import search_knowledge, search_qa
from app.agent.memory import upsert_client_memory
from app.schemas.agent import CategorizeResult

router = APIRouter()
logger = logging.getLogger(__name__)


async def _run_post_categorize(ticket_id: int, updated_ticket: dict, client_id: int) -> None:
    """
    Background task: genera nota interna + respuesta al cliente después de categorizar.
    Corre tras enviar la respuesta HTTP para no bloquear al frontend.
    """
    token = create_service_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Pre-computar embeddings UNA sola vez y compartirlos entre run_notes y run_interact
    # para reducir llamadas a la API de embeddings a la mitad.
    try:
        knowledge_ctx = await search_knowledge(updated_ticket["description"])
        qa_ctx = await search_qa(updated_ticket["description"])
    except Exception as exc:
        logger.error("[TICBot] Error pre-computando embeddings para ticket #%s: %s", ticket_id, exc)
        knowledge_ctx = ""
        qa_ctx = ""

    async with httpx.AsyncClient(base_url=settings.TICKET_SERVICE_URL, timeout=120.0) as client:
        # Nota interna para el equipo TIC
        try:
            note = await run_notes(updated_ticket, knowledge_ctx=knowledge_ctx, qa_ctx=qa_ctx)
            await client.post(
                f"/tickets/{ticket_id}/replies",
                json={"text": f"[TICBot — Nota Interna]\n\n{note}", "is_internal": True},
                headers=headers,
            )
            logger.info("[TICBot] Nota interna posteada para ticket #%s", ticket_id)
        except Exception as exc:
            logger.error("[TICBot] Error en nota interna ticket #%s: %s", ticket_id, exc)

        # Respuesta al cliente
        try:
            async with AsyncSessionLocal() as db:
                agent_reply = await run_interact(
                    updated_ticket, client_id, db,
                    knowledge_ctx=knowledge_ctx, qa_ctx=qa_ctx,
                )
                await client.post(
                    f"/tickets/{ticket_id}/replies",
                    json={"text": agent_reply, "is_internal": False},
                    headers=headers,
                )
                await upsert_client_memory(
                    client_id=client_id,
                    problem_summary=updated_ticket["description"][:500],
                    resolution_summary=agent_reply[:500],
                    tic_area=updated_ticket.get("tic_area", "general_tech_support"),
                    db=db,
                )
            logger.info("[TICBot] Respuesta al cliente posteada para ticket #%s", ticket_id)
        except Exception as exc:
            logger.error("[TICBot] Error en respuesta al cliente ticket #%s: %s", ticket_id, exc)


@router.post("/categorize/{ticket_id}", response_model=CategorizeResult)
async def categorize_ticket(
    ticket_id: int,
    background_tasks: BackgroundTasks,
    _: TokenUser = Depends(require_agent_or_admin),
):
    """
    Paso 1 (síncrono, rápido): clasifica tic_area + prioridad y persiste.
    Paso 2 (background): nota interna TIC + respuesta inicial al cliente.
    """
    token = create_service_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=settings.TICKET_SERVICE_URL, timeout=30.0) as client:
        resp = await client.get(f"/tickets/{ticket_id}", headers=headers)
        if resp.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
        resp.raise_for_status()
        ticket = resp.json()

        result = await run_categorize(ticket)
        tic_area = result.get("tic_area", "general_tech_support")
        priority = result.get("priority", "medium")

        patch_resp = await client.patch(
            f"/tickets/{ticket_id}",
            json={"tic_area": tic_area, "priority": priority, "agent_processed": True},
            headers=headers,
        )
        patch_resp.raise_for_status()

    updated_ticket = {**ticket, "tic_area": tic_area, "priority": priority, "agent_processed": True}
    background_tasks.add_task(_run_post_categorize, ticket_id, updated_ticket, ticket["created_by"])

    return CategorizeResult(
        ticket_id=ticket_id,
        tic_area=tic_area,
        priority=priority,
        reasoning=result.get("reasoning", ""),
    )
