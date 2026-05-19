"""POST /agent/interact/{ticket_id}"""
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenUser, get_current_user
from app.core.config import settings, create_service_token
from app.db.database import get_db
from app.agent.graph import run_interact
from app.agent.memory import upsert_client_memory
from app.agent.knowledge import save_qa_to_db
from app.schemas.agent import InteractResult

router = APIRouter()


class InteractRequest(BaseModel):
    save_qa: bool = False
    qa_problem_summary: Optional[str] = None
    qa_solution_summary: Optional[str] = None


@router.post("/interact/{ticket_id}", response_model=InteractResult)
async def interact_with_client(
    ticket_id: int,
    body: InteractRequest = InteractRequest(),
    _: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    TICBot generates a reply for the client based on ticket context,
    client memory, and knowledge base. Posts the reply to the ticket thread.
    """
    token = create_service_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=settings.TICKET_SERVICE_URL, timeout=60.0) as client:
        resp = await client.get(f"/tickets/{ticket_id}", headers=headers)
        if resp.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
        resp.raise_for_status()
        ticket = resp.json()

        client_id: int = ticket["created_by"]
        agent_reply = await run_interact(ticket, client_id, db)

        # Post reply to ticket thread
        reply_resp = await client.post(
            f"/tickets/{ticket_id}/replies",
            json={"text": agent_reply, "is_internal": False},
            headers=headers,
        )
        reply_resp.raise_for_status()

    # Update client memory
    await upsert_client_memory(
        client_id=client_id,
        problem_summary=ticket["description"][:500],
        resolution_summary=agent_reply[:500],
        tic_area=ticket.get("tic_area", "general_tech_support"),
        db=db,
    )

    # Auto-save QA entry when the agent resolves the ticket
    qa_saved = False
    async with httpx.AsyncClient(base_url=settings.TICKET_SERVICE_URL, timeout=15.0) as status_client:
        try:
            status_resp = await status_client.get(f"/tickets/{ticket_id}", headers=headers)
            if status_resp.status_code == 200:
                updated_ticket = status_resp.json()
                if updated_ticket.get("status") == "resolved":
                    await save_qa_to_db(
                        problem=ticket["description"][:1000],
                        solution=agent_reply[:1000],
                        tic_area=ticket.get("tic_area"),
                        source_ticket_id=ticket_id,
                        db=db,
                    )
                    qa_saved = True
        except Exception:
            pass  # QA save is best-effort, never block the response

    # Manual QA override (explicit save_qa from caller)
    if not qa_saved and body.save_qa and body.qa_problem_summary and body.qa_solution_summary:
        await save_qa_to_db(
            problem=body.qa_problem_summary,
            solution=body.qa_solution_summary,
            tic_area=ticket.get("tic_area"),
            source_ticket_id=ticket_id,
            db=db,
        )
        qa_saved = True

    return InteractResult(
        ticket_id=ticket_id,
        reply_posted=True,
        message=agent_reply,
        qa_saved=qa_saved,
    )
