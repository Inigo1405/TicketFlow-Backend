import logging
from datetime import datetime, timezone, timedelta
from typing import List

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.ticket import Ticket, Reply
from app.schemas.ticket import (
    TicketCreate, TicketUpdate, TicketOut, TicketSummary, ReplyCreate, ReplyOut
)
from app.core.config import settings, create_service_token
from app.core.auth import get_current_user, require_agent_or_admin, TokenUser
from app.rabbit.publisher import publish_notification

logger = logging.getLogger(__name__)

router = APIRouter()


async def _trigger_categorize(ticket_id: int) -> None:
    """Background task: pide al agent-service que categorice el ticket."""
    try:
        token = create_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{settings.AGENT_SERVICE_URL}/agent/categorize/{ticket_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as exc:
        logger.warning("No se pudo disparar categorize para ticket #%s: %s", ticket_id, exc)


async def _trigger_interact(ticket_id: int) -> None:
    """Background task: pide al agent-service que responda al cliente."""
    try:
        token = create_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{settings.AGENT_SERVICE_URL}/agent/interact/{ticket_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as exc:
        logger.warning("No se pudo disparar interact para ticket #%s: %s", ticket_id, exc)


def _check_sla(ticket: Ticket) -> None:
    """Mark ticket as sla_breached if open/pending beyond SLA_HOURS."""
    if ticket.status in ("open", "pending") and not ticket.sla_breached:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.SLA_HOURS)
        created = ticket.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created < cutoff:
            ticket.sla_breached = True

async def _get_ticket_with_replies(ticket_id: int, db: AsyncSession) -> Ticket:
    result = await db.execute(
        select(Ticket).options(selectinload(Ticket.replies)).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    return ticket


# ── GET /tickets ──────────────────────────────────────────────────────────────
@router.get("/", response_model=List[TicketSummary])
async def list_tickets(
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    result = await db.execute(select(Ticket).order_by(Ticket.created_at.desc()))
    tickets = result.scalars().all()
    for t in tickets:
        _check_sla(t)
    return tickets


# ── GET /tickets/mine ─────────────────────────────────────────────────────────
@router.get("/mine", response_model=List[TicketSummary])
async def my_tickets(
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Ticket).where(Ticket.created_by == current_user.id).order_by(Ticket.created_at.desc())
    )
    tickets = result.scalars().all()
    for t in tickets:
        _check_sla(t)
    return tickets


# ── GET /tickets/:id ──────────────────────────────────────────────────────────
@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Ticket).options(selectinload(Ticket.replies)).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    _check_sla(ticket)
    # Clients cannot see internal replies.
    # IMPORTANT: convert to Pydantic first — mutating ticket.replies on the ORM object
    # would cascade-delete internal notes from the DB (delete-orphan cascade).
    if current_user.role == "Cliente":
        ticket_out = TicketOut.model_validate(ticket)
        ticket_out.replies = [r for r in ticket_out.replies if not r.is_internal]
        return ticket_out
    return ticket


# ── POST /tickets ─────────────────────────────────────────────────────────────
@router.post("/", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    ticket = Ticket(
        title=body.title,
        description=body.description,
        category=body.category,
        status=body.status,
        created_by=current_user.id,
    )
    db.add(ticket)
    await db.flush()
    # Re-fetch con replies cargados para evitar error de lazy-load
    ticket = await _get_ticket_with_replies(ticket.id, db)
    # Commit explícito antes de la background task: el agente necesita ver el ticket
    await db.commit()
    background_tasks.add_task(_trigger_categorize, ticket.id)
    await publish_notification({
        "user_ids": [current_user.id],
        "type": "ticket_created",
        "title": "Ticket creado",
        "message": f"Tu ticket '{ticket.title}' fue creado y está siendo procesado.",
        "ticket_id": ticket.id,
    })
    return ticket


# ── PATCH /tickets/:id ────────────────────────────────────────────────────────
@router.patch("/{ticket_id}", response_model=TicketOut)
async def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(require_agent_or_admin),
):
    result = await db.execute(
        select(Ticket).options(selectinload(Ticket.replies)).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    if body.priority is not None:
        ticket.priority = body.priority
    if body.notes is not None:
        ticket.notes = body.notes
    if body.tic_area is not None:
        ticket.tic_area = body.tic_area
    if body.agent_processed is not None:
        ticket.agent_processed = body.agent_processed

    await db.flush()
    await db.refresh(ticket)
    return ticket


# ── PATCH /tickets/:id/close ──────────────────────────────────────────────────
@router.patch("/{ticket_id}/close")
async def close_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(require_agent_or_admin),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    ticket.status = "closed"
    await db.flush()
    await publish_notification({
        "user_ids": [ticket.created_by],
        "type": "ticket_closed",
        "title": "Ticket cerrado",
        "message": f"El ticket '{ticket.title}' fue cerrado.",
        "ticket_id": ticket_id,
    })
    return {}


# ── PATCH /tickets/:id/resolve ────────────────────────────────────────────────
@router.patch("/{ticket_id}/resolve")
async def resolve_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(require_agent_or_admin),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    ticket.status = "resolved"
    await db.flush()
    await publish_notification({
        "user_ids": [ticket.created_by],
        "type": "ticket_resolved",
        "title": "Ticket resuelto",
        "message": f"El ticket '{ticket.title}' fue marcado como resuelto.",
        "ticket_id": ticket_id,
    })
    return {}


# ── PATCH /tickets/:id/pending ───────────────────────────────────────────────
@router.patch("/{ticket_id}/pending")
async def set_ticket_pending(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(require_agent_or_admin),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    ticket.status = "pending"
    await db.flush()
    return {}


# ── POST /tickets/:id/replies ─────────────────────────────────────────────────
@router.post("/{ticket_id}/replies", response_model=ReplyOut, status_code=status.HTTP_201_CREATED)
async def add_reply(
    ticket_id: int,
    body: ReplyCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    # author_name: usar name del JWT si existe (ej. TICBot), sino fallback a id
    reply = Reply(
        ticket_id=ticket_id,
        author_id=current_user.id,
        author_name=current_user.name or f"Usuario #{current_user.id}",
        text=body.text,
        is_internal=body.is_internal if current_user.role in ("Agente", "Admin") else False,
    )
    db.add(reply)
    await db.flush()
    await db.refresh(reply)
    # Commit explícito antes de la background task: el agente necesita ver la reply
    await db.commit()
    # Disparar interact solo para respuestas visibles del cliente (no internas, no del propio bot)
    if not body.is_internal and current_user.id != 0:
        background_tasks.add_task(_trigger_interact, ticket_id)
    if current_user.id != ticket.created_by:
        await publish_notification({
            "user_ids": [ticket.created_by],
            "type": "new_reply",
            "title": "Nueva respuesta en tu ticket",
            "message": f"Hay una nueva respuesta en tu ticket '{ticket.title}'.",
            "ticket_id": ticket_id,
        })
    return reply
