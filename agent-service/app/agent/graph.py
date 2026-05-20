"""
LangGraph-based agent orchestration.
Each mode (categorize, interact, notes, qa_audit) uses a dedicated runner
with appropriate system prompt and tool set.
"""
import json
import re
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
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

def _extract_last_ai_message(result: dict) -> str:
    for msg in reversed(result["messages"]):
        content = getattr(msg, "content", None)
        tool_calls = getattr(msg, "tool_calls", None)
        if content and not tool_calls:
            return content
    return "TICBot no pudo generar una respuesta."


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
    agent = create_react_agent(llm, CLIENT_TOOLS + ticket_tools, prompt=system_prompt)

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

    result = await agent.ainvoke({"messages": [HumanMessage(content=human_content)]})
    return _extract_last_ai_message(result)


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
    agent = create_react_agent(llm, NOTES_TOOLS, prompt=system_prompt)

    human_content = (
        f"Ticket #{ticket['id']}: {ticket['title']}\n"
        f"Descripción: {ticket['description']}\n"
        f"Área TIC: {ticket.get('tic_area', 'uncategorized')}\n"
        f"Prioridad: {ticket.get('priority', 'medium')}\n"
        f"Estado: {ticket.get('status', 'open')}\n\n"
        "Genera la nota interna para el equipo TIC."
    )

    result = await agent.ainvoke({"messages": [HumanMessage(content=human_content)]})
    return _extract_last_ai_message(result)


# ── 4. QA Audit ───────────────────────────────────────────────────────────────

async def run_qa_audit(extra_context: Optional[str] = None) -> str:
    """
    Run the QA audit agent. It will call get_all_tickets_summary internally.
    """
    tickets_ctx = extra_context or "Usa la herramienta get_all_tickets_summary para obtener los tickets."
    system_prompt = qa_audit_prompt(tickets_context=tickets_ctx)

    llm = get_llm(temperature=0.2)
    agent = create_react_agent(llm, QA_TOOLS, prompt=system_prompt)

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content="Realiza la auditoría de calidad de todos los tickets del sistema.")]}
    )
    return _extract_last_ai_message(result)


# ── 5. Admin privileged chat ───────────────────────────────────────────────────────────

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

    agent = create_react_agent(llm, admin_tools, prompt=system_prompt)
    result = await agent.ainvoke({"messages": [HumanMessage(content=message)]})
    return _extract_last_ai_message(result)
