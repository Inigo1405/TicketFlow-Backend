from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.ticket import Ticket, Reply
from app.schemas.ticket import (
    TicketCreate, TicketUpdate, TicketOut, TicketSummary, ReplyCreate, ReplyOut
)
from app.core.config import settings
from app.core.auth import get_current_user, require_agent_or_admin, TokenUser

router = APIRouter()


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
    result = await db.execute(select(Ticket))
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
    result = await db.execute(select(Ticket).where(Ticket.created_by == current_user.id))
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
    return ticket


# ── POST /tickets ─────────────────────────────────────────────────────────────
@router.post("/", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate,
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
    return {}


# ── POST /tickets/:id/replies ─────────────────────────────────────────────────
@router.post("/{ticket_id}/replies", response_model=ReplyOut, status_code=status.HTTP_201_CREATED)
async def add_reply(
    ticket_id: int,
    body: ReplyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenUser = Depends(get_current_user),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    # author_name: El gateway inyecta el nombre real del usuario en el header "X-User-Name" basado en el token JWT.
    # Fallback a "Usuario #{id}" si no se encuentra el header.
    from fastapi import Request
    reply = Reply(
        ticket_id=ticket_id,
        author_id=current_user.id,
        author_name=f"Usuario #{current_user.id}",  # gateway lo sobreescribe con el nombre real
        text=body.text,
    )
    db.add(reply)
    await db.flush()
    await db.refresh(reply)
    return reply
