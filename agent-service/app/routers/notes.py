"""POST /agent/notes/{ticket_id}"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import TokenUser, require_agent_or_admin
from app.core.config import settings, create_service_token
from app.agent.graph import run_notes
from app.schemas.agent import NotesResult

router = APIRouter()


@router.post("/notes/{ticket_id}", response_model=NotesResult)
async def generate_internal_note(
    ticket_id: int,
    _: TokenUser = Depends(require_agent_or_admin),
):
    """
    TICBot generates a technical internal note for the TIC team and posts
    it as an internal reply (not visible to clients).
    """
    token = create_service_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url=settings.TICKET_SERVICE_URL, timeout=60.0) as client:
        resp = await client.get(f"/tickets/{ticket_id}", headers=headers)
        if resp.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
        resp.raise_for_status()
        ticket = resp.json()

        note = await run_notes(ticket)

        # Post as internal reply
        reply_resp = await client.post(
            f"/tickets/{ticket_id}/replies",
            json={"text": f"[TICBot — Nota Interna]\n\n{note}", "is_internal": True},
            headers=headers,
        )
        reply_resp.raise_for_status()

    return NotesResult(ticket_id=ticket_id, note_posted=True, note=note)
