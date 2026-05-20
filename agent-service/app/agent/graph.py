"""
Agent orchestration for TICBot.
Each mode (categorize, interact, notes, qa_audit, admin_chat) uses a dedicated
runner with appropriate system prompt and tool set.

Tool-calling strategy
─────────────────────
Gemini 3.x models (gemini-3.1-flash-lite etc.) embed a `thought_signature`
in every FunctionCall part of their response.  The Gemini API requires that
same signature to be present when the history is sent back on the next turn.
langchain-google-genai does NOT preserve those bytes through the LangChain
message pipeline, so any call that passes an AIMessage(tool_calls=[...]) as
history gets a 400 INVALID_ARGUMENT.

Fix: _tic_react() replaces create_react_agent().  It never sends tool-call
AIMessages back to the model.  Instead it executes tools, collects their
output as plain text, and injects that text into the next HumanMessage.
Every LLM call is a clean [SystemMessage, HumanMessage] pair — no signed
FunctionCall parts in history.
"""
import json
import re
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import get_llm
from app.agent.prompts import (
    CATEGORIZATION_PROMPT,
    client_interaction_prompt,
    internal_notes_prompt,
    qa_audit_prompt,
)
from app.agent.memory import get_client_memory_text
from app.agent.knowledge import search_knowledge, search_qa
from app.agent.tools import CLIENT_TOOLS, NOTES_TOOLS, QA_TOOLS, make_ticket_status_tools


# ── Core tool loop ────────────────────────────────────────────────────────────

async def _tic_react(
    llm,
    tools: list,
    system_prompt: str,
    user_message: str,
    max_tool_rounds: int = 4,
) -> str:
    """
    ReAct-style loop that is safe with Gemini 3.x thought_signature requirement.

    Instead of passing AIMessage(tool_calls=[...]) back to the model (which
    would require re-attaching the thought_signatures that langchain drops),
    each round injects tool results as plain text into a fresh HumanMessage.
    """
    llm_with_tools = llm.bind_tools(tools)
    tool_map = {t.name: t for t in tools}

    current_user_msg = user_message
    accumulated: list[str] = []

    for _ in range(max_tool_rounds):
        ai_msg = await llm_with_tools.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=current_user_msg)]
        )

        if not getattr(ai_msg, "tool_calls", None):
            return ai_msg.content or "TICBot no pudo generar una respuesta."

        # Execute every tool call requested in this round
        for tc in ai_msg.tool_calls:
            name = tc["name"]
            args = tc.get("args", {})
            try:
                result = (
                    await tool_map[name].ainvoke(args)
                    if name in tool_map
                    else f"Herramienta '{name}' no disponible."
                )
            except Exception as exc:
                result = f"Error en {name}: {exc}"
            accumulated.append(f"[{name}]: {result}")

        # Rebuild the user message with all accumulated results as inline context
        results_block = "\n\n".join(accumulated)
        current_user_msg = (
            f"{user_message}\n\n"
            "---\n"
            f"Información obtenida de herramientas:\n{results_block}\n"
            "---\n\n"
            "Con esta información, redacta tu respuesta. "
            "Si necesitas más datos, consulta más herramientas. "
            "Si corresponde cambiar el estado del ticket (resolve_ticket, close_ticket, set_ticket_pending), "
            "llama a esa herramienta en este mismo paso antes de dar tu respuesta final."
        )

    # Rounds exhausted — force a plain-text answer (no tools bound)
    results_block = "\n\n".join(accumulated)
    final_msg = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    f"{user_message}\n\n"
                    "---\n"
                    f"Información recopilada:\n{results_block}\n"
                    "---\n\n"
                    "Genera tu respuesta final basándote en esta información."
                )
            ),
        ]
    )
    return final_msg.content or "TICBot no pudo generar una respuesta."


# ── 1. Categorization ─────────────────────────────────────────────────────────

async def run_categorize(ticket: dict) -> dict:
    """
    Categorize a ticket using direct LLM call (no tools needed).
    Returns dict with tic_area, priority, reasoning.
    """
    llm = get_llm(temperature=0.1)
    human_content = (
        f"Ticket a categorizar:\n"
        f"Título: {ticket['title']}\n"
        f"Descripción: {ticket['description']}\n"
        f"Categoría actual: {ticket.get('category', 'general')}"
    )
    response = await llm.ainvoke(
        [SystemMessage(content=CATEGORIZATION_PROMPT), HumanMessage(content=human_content)]
    )
    raw = response.content.strip()

    # Extract JSON (model may wrap it in markdown fences)
    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback defaults
    return {
        "tic_area": "general_tech_support",
        "priority": "medium",
        "reasoning": "No se pudo parsear la respuesta del modelo.",
    }


# ── 2. Client interaction ─────────────────────────────────────────────────────

async def run_interact(
    ticket: dict,
    client_id: int,
    db: AsyncSession,
    knowledge_ctx: str = None,
    qa_ctx: str = None,
) -> str:
    """
    Run the ReAct agent to generate a reply for the client.
    Injects client memory and relevant knowledge into the system prompt.
    """
    client_ctx = await get_client_memory_text(client_id, db)
    if knowledge_ctx is None:
        knowledge_ctx = await search_knowledge(ticket["description"])
    if qa_ctx is None:
        qa_ctx = await search_qa(ticket["description"])
    combined_knowledge = f"{knowledge_ctx}\n\n{qa_ctx}"

    system_prompt = client_interaction_prompt(
        client_context=client_ctx,
        knowledge_context=combined_knowledge,
    )

    llm = get_llm(temperature=0.4)
    ticket_tools = make_ticket_status_tools(ticket["id"])

    # Build conversation thread (public replies only — internal notes are not shown to clients)
    public_replies = [
        r for r in ticket.get("replies", []) if not r.get("is_internal", False)
    ]

    base_info = (
        f"Ticket #{ticket['id']}: {ticket['title']}\n"
        f"Descripción original: {ticket['description']}\n"
        f"Área TIC: {ticket.get('tic_area', 'general_tech_support')}\n"
        f"Prioridad: {ticket.get('priority', 'medium')}\n"
        f"Estado: {ticket.get('status', 'open')}"
    )

    if public_replies:
        thread = "\n\n".join(
            f"[{r['author_name']}]: {r['text']}" for r in public_replies
        )
        human_content = (
            f"{base_info}\n\n"
            f"Conversación hasta ahora:\n{thread}\n\n"
            "Responde al último mensaje del cliente de manera fluida y directa, "
            "sin repetir información que ya se mencionó en la conversación."
        )
    else:
        human_content = (
            f"{base_info}\n\n"
            "Responde al cliente para ayudarle con este problema."
        )

    return await _tic_react(llm, CLIENT_TOOLS + ticket_tools, system_prompt, human_content)


# ── 3. Internal notes ─────────────────────────────────────────────────────────

async def run_notes(ticket: dict, knowledge_ctx: str = None, qa_ctx: str = None) -> str:
    """
    Run the agent to generate a technical internal note for the TIC team.
    """
    if knowledge_ctx is None:
        knowledge_ctx = await search_knowledge(ticket["description"])
    if qa_ctx is None:
        qa_ctx = await search_qa(ticket["description"])
    combined_knowledge = f"{knowledge_ctx}\n\n{qa_ctx}"

    system_prompt = internal_notes_prompt(knowledge_context=combined_knowledge)

    llm = get_llm(temperature=0.2)

    human_content = (
        f"Ticket #{ticket['id']}: {ticket['title']}\n"
        f"Descripción: {ticket['description']}\n"
        f"Área TIC: {ticket.get('tic_area', 'uncategorized')}\n"
        f"Prioridad: {ticket.get('priority', 'medium')}\n"
        f"Estado: {ticket.get('status', 'open')}\n\n"
        "Genera la nota interna para el equipo TIC."
    )

    return await _tic_react(llm, NOTES_TOOLS, system_prompt, human_content)


# ── 4. QA Audit ───────────────────────────────────────────────────────────────

async def run_qa_audit(extra_context: Optional[str] = None) -> str:
    """
    Run the QA audit agent. It will call get_all_tickets_summary internally.
    """
    tickets_ctx = extra_context or "Usa la herramienta get_all_tickets_summary para obtener los tickets."
    system_prompt = qa_audit_prompt(tickets_context=tickets_ctx)

    llm = get_llm(temperature=0.2)
    return await _tic_react(
        llm, QA_TOOLS, system_prompt,
        "Realiza la auditoría de calidad de todos los tickets del sistema."
    )


# ── 5. QA solution summary ────────────────────────────────────────────────────

async def generate_qa_solution_summary(ticket: dict) -> str:
    """
    Generate a concise technical description of HOW the ticket was resolved.
    Used when saving a QA entry so the 'solution' field captures the actual
    fix (e.g. "El usuario restableció su contraseña desde el autoservicio")
    instead of the agent's polite closing message.
    """
    replies = ticket.get("replies", [])
    if not replies:
        return ticket.get("description", "")[:500]

    thread = "\n".join(
        f"[{r['author_name']} ({'interno' if r.get('is_internal') else 'cliente'})]:"
        f" {r['text']}"
        for r in replies
    )

    llm = get_llm(temperature=0.1)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "Eres un analista de soporte TIC. Genera una descripción técnica concisa "
                    "(1-2 oraciones) de la acción o causa que resolvió el problema del ticket. "
                    "Escribe solo la solución técnica, sin saludos ni menciones al ticket. "
                    "Usa tercera persona. "
                    "Ejemplos correctos:\n"
                    "- 'El usuario restableció su contraseña desde el autoservicio del portal corporativo.'\n"
                    "- 'Se reinició el servidor de impresión, restaurando el servicio para todo el piso.'\n"
                    "- 'Se instaló el certificado VPN faltante en el equipo del usuario.'"
                )
            ),
            HumanMessage(
                content=(
                    f"Problema: {ticket.get('title', '')} — {ticket['description']}\n"
                    f"Área TIC: {ticket.get('tic_area', 'general')}\n\n"
                    f"Conversación completa del ticket:\n{thread}\n\n"
                    "Genera la descripción técnica de cómo se resolvió."
                )
            ),
        ]
    )
    return response.content.strip() or ticket["description"][:500]


# ── 6. Admin privileged chat ───────────────────────────────────────────────────────────

async def run_admin_chat(message: str, history: list[dict], db: AsyncSession) -> str:
    """
    Admin privileged chat.
    History is injected as plain text into the system prompt rather than
    reconstructed as AIMessage objects.  This avoids the Gemini 400 error
    caused by missing thought_signature on serialised tool-call turns.
    """
    from app.agent.admin_tools import make_admin_tools
    from app.agent.prompts import ADMIN_CHAT_PROMPT
    from app.core.config import settings
    from langchain_google_genai import ChatGoogleGenerativeAI

    # Use GEMINI_ADMIN_MODEL (Gemini 2.x) instead of the default Gemini 3 model.
    # Gemini 3 requires thought_signatures on every function call in the ReAct loop,
    # which langchain-google-genai 2.x does not preserve between steps — causing a
    # 400 INVALID_ARGUMENT error on the second LLM call.  Gemini 2.x has no such
    # requirement, so the existing library version works fine.
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_ADMIN_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.3,
    )
    admin_tools = make_admin_tools(db)

    # Build system prompt: base prompt + prior conversation as plain text.
    # Never pass prior AI turns as AIMessage objects – that would strip any
    # thought_signature Gemini embedded, causing INVALID_ARGUMENT on turn 2+.
    system_prompt = ADMIN_CHAT_PROMPT
    if history:
        lines = []
        for h in history:
            role = "Admin" if h["role"] == "user" else "TICBot"
            lines.append(f"{role}: {h['content']}")
        system_prompt = (
            ADMIN_CHAT_PROMPT
            + "\n\n## Conversación anterior (contexto)\n"
            + "\n".join(lines)
            + "\n\n---"
        )

    return await _tic_react(llm, admin_tools, system_prompt, message)
