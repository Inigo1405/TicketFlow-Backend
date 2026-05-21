"""
LangGraph-based agent orchestration.
Each mode (categorize, interact, notes, qa_audit) uses a dedicated runner
with appropriate system prompt and tool set.
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


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _tic_react(
    llm,
    tools: list,
    system_prompt: str,
    user_message: str,
    max_tool_rounds: int = 4,
) -> str:
    """
    Custom ReAct loop that avoids the Gemini 3 thought_signature issue.

    Gemini 3.x embeds a thought_signature inside every FunctionCall part and
    REQUIRES those signatures back in the next turn.  LangGraph's
    create_react_agent accumulates AIMessage(tool_calls=[...]) in the history
    and never re-attaches the signatures → 400 INVALID_ARGUMENT on the 2nd
    tool call.

    This loop never sends tool-call AIMessages back to the model.  Instead:
    - Each round starts from a clean [SystemMessage, HumanMessage] pair.
    - Tool results are injected as plain text into the next HumanMessage.
    """
    tool_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools) if tools else llm
    accumulated = user_message

    for round_num in range(max_tool_rounds):
        if round_num == 0:
            human_text = accumulated
        else:
            human_text = (
                accumulated
                + "\n\nCon esta información, redacta tu respuesta. "
                "Si necesitas más datos, consulta más herramientas. "
                "Si corresponde cambiar el estado del ticket "
                "(resolve_ticket, close_ticket, set_ticket_pending), "
                "llama a esa herramienta en este mismo paso antes de dar tu respuesta final."
            )

        response = await llm_with_tools.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=human_text)]
        )
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            return response.content or "TICBot no pudo generar una respuesta."

        results_text = []
        for tc in tool_calls:
            name = tc["name"]
            args = tc.get("args", {})
            tool = tool_map.get(name)
            if tool is None:
                results_text.append(f"[{name}]: Herramienta no encontrada.")
                continue
            try:
                result = await tool.ainvoke(args)
                results_text.append(f"[{name}]: {result}")
            except Exception as exc:
                results_text.append(f"[{name}]: Error — {exc}")

        accumulated = accumulated + "\n\nResultados de herramientas:\n" + "\n".join(results_text)

    # Max rounds exhausted — final call without tools
    final = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=accumulated + "\n\nRedacta ahora tu respuesta final."),
        ]
    )
    return final.content or "TICBot no pudo generar una respuesta."


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
        llm,
        QA_TOOLS,
        system_prompt,
        "Realiza la auditoría de calidad de todos los tickets del sistema.",
    )


# ── 5. QA solution summary ───────────────────────────────────────────────────

async def generate_qa_solution_summary(ticket: dict) -> str:
    """
    Generate a concise technical description of the solution applied to a ticket.
    Uses the full reply thread (internal + public) for accuracy.
    Stored in QA entries instead of the polite closing message.
    """
    llm = get_llm(temperature=0.1)
    replies = ticket.get("replies", [])
    thread = "\n".join(
        f"[{'INTERNO' if r.get('is_internal') else r.get('author_name', 'Agente')}]: {r['text']}"
        for r in replies
    )
    human_content = (
        f"Ticket #{ticket['id']}: {ticket['title']}\n"
        f"Descripción: {ticket['description']}\n"
        f"Área: {ticket.get('tic_area', 'general_tech_support')}\n\n"
        f"Hilo completo:\n{thread}\n\n"
        "Genera una descripción técnica breve de la SOLUCIÓN aplicada (máximo 2 oraciones). "
        "Describe QUÉ SE HIZO para resolver el problema, no el cierre conversacional. "
        "Ejemplo correcto: 'Se restableció la contraseña del usuario desde el panel de autoservicio. "
        "Se verificó el acceso correcto al sistema.'"
    )
    response = await llm.ainvoke(
        [
            SystemMessage(content="Eres un técnico TIC. Resume soluciones de tickets de soporte de forma concisa y técnica."),
            HumanMessage(content=human_content),
        ]
    )
    return response.content.strip()


# ── 6. Admin privileged chat ──────────────────────────────────────────────────

async def run_admin_chat(message: str, history: list[dict], db: AsyncSession) -> str:
    """
    Admin privileged chat using _tic_react to avoid thought_signature errors.
    History is injected as plain text into the system prompt.
    """
    from app.agent.admin_tools import make_admin_tools
    from app.agent.prompts import ADMIN_CHAT_PROMPT
    from app.core.config import settings
    from langchain_google_genai import ChatGoogleGenerativeAI

    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_ADMIN_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.3,
    )
    admin_tools = make_admin_tools(db)

    # Inject prior conversation as plain text — never as AIMessage objects.
    system_prompt = ADMIN_CHAT_PROMPT
    if history:
        lines = [
            f"{'Admin' if h['role'] == 'user' else 'TICBot'}: {h['content']}"
            for h in history
        ]
        system_prompt = (
            ADMIN_CHAT_PROMPT
            + "\n\n## Conversación anterior (contexto)\n"
            + "\n".join(lines)
            + "\n\n---"
        )

    return await _tic_react(llm, admin_tools, system_prompt, message)
