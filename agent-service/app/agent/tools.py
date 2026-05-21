"""
LangChain tools for TICBot.
Tools are async and use module-level clients injected at call time.
"""
import asyncio
from typing import Optional

import httpx
from langchain_core.tools import tool
from duckduckgo_search import DDGS

from app.agent.knowledge import search_knowledge, search_qa, search_client_profile
from app.core.config import settings, create_service_token


# ── Web search ────────────────────────────────────────────────────────────────

@tool
async def web_search(query: str) -> str:
    """Search the internet for technical information when internal knowledge is insufficient."""
    try:
        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: list(DDGS().text(query, max_results=settings.DUCKDUCKGO_MAX_RESULTS)),
        )
        if not results:
            return "No se encontraron resultados en internet."
        lines = ["Resultados de búsqueda web:"]
        for r in results:
            lines.append(f"  • {r.get('title', '')}: {r.get('body', '')[:200]}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error en búsqueda web: {exc}"


# ── Internal knowledge base ───────────────────────────────────────────────────

@tool
async def search_knowledge_base(query: str) -> str:
    """Search the internal TIC company knowledge base for procedures, policies and guides."""
    return await search_knowledge(query)


@tool
async def search_past_qa(query: str) -> str:
    """Search past resolved problem-solution pairs (QA database) for similar issues."""
    return await search_qa(query)


@tool
async def search_similar_resolutions(query: str) -> str:
    """Search the history of problems from ALL clients and how they were resolved. Use this when the internal knowledge base and QA entries are not enough, or to validate your proposed solution against real past cases."""
    return await search_client_profile(query)


# ── Ticket service ────────────────────────────────────────────────────────────

@tool
async def get_all_tickets_summary() -> str:
    """
    Retrieve a summary of ALL company tickets for QA analysis.
    Use this only when performing a QA audit — it may be slow for large datasets.
    """
    token = create_service_token()
    try:
        async with httpx.AsyncClient(
            base_url=settings.TICKET_SERVICE_URL, timeout=30.0
        ) as client:
            resp = await client.get(
                "/tickets/",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            tickets = resp.json()

        if not tickets:
            return "No hay tickets en el sistema."

        lines = [f"Total de tickets: {len(tickets)}\n"]
        for t in tickets:
            sla = " [SLA INCUMPLIDO]" if t.get("sla_breached") else ""
            lines.append(
                f"  #{t['id']} [{t['status']}|{t['priority']}|{t.get('tic_area','?')}] "
                f"{t['title']}{sla}"
            )
        return "\n".join(lines)
    except Exception as exc:
        return f"Error al obtener tickets: {exc}"


# ── Ticket status tools (bound per call to avoid leaking ticket_id to the LLM) ──

def make_ticket_status_tools(ticket_id: int) -> list:
    """
    Returns three LangChain tools pre-bound to *ticket_id*.
    The LLM never needs to supply the ID; it just calls the tool.
    """

    @tool
    async def resolve_ticket() -> str:
        """
        Mark the current ticket as RESOLVED.
        Use this when your reply fully addresses the client's issue.
        Do NOT use if the client still has unresolved questions.
        """
        token = create_service_token()
        try:
            async with httpx.AsyncClient(
                base_url=settings.TICKET_SERVICE_URL, timeout=15.0
            ) as c:
                resp = await c.patch(
                    f"/tickets/{ticket_id}/resolve",
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
            return f"Ticket #{ticket_id} marcado como RESUELTO."
        except Exception as exc:
            return f"Error al resolver el ticket: {exc}"

    @tool
    async def close_ticket() -> str:
        """
        Close the current ticket.
        Use ONLY when the client explicitly asks to close the ticket.
        """
        token = create_service_token()
        try:
            async with httpx.AsyncClient(
                base_url=settings.TICKET_SERVICE_URL, timeout=15.0
            ) as c:
                resp = await c.patch(
                    f"/tickets/{ticket_id}/close",
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
            return f"Ticket #{ticket_id} marcado como CERRADO."
        except Exception as exc:
            return f"Error al cerrar el ticket: {exc}"

    @tool
    async def set_ticket_pending() -> str:
        """
        Set the current ticket to PENDING.
        Use ONLY when the client explicitly asks to leave the ticket pending
        or says they need more time to try the solution.
        """
        token = create_service_token()
        try:
            async with httpx.AsyncClient(
                base_url=settings.TICKET_SERVICE_URL, timeout=15.0
            ) as c:
                resp = await c.patch(
                    f"/tickets/{ticket_id}/pending",
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
            return f"Ticket #{ticket_id} marcado como PENDIENTE."
        except Exception as exc:
            return f"Error al marcar el ticket como pendiente: {exc}"

    return [resolve_ticket, close_ticket, set_ticket_pending]


# ── Tool sets per mode ────────────────────────────────────────────────────────

CLIENT_TOOLS = [web_search, search_knowledge_base, search_past_qa, search_similar_resolutions]
NOTES_TOOLS = [web_search, search_knowledge_base, search_past_qa, get_all_tickets_summary]
QA_TOOLS = [get_all_tickets_summary, search_knowledge_base, search_past_qa]
