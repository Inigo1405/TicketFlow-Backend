from typing import Optional
from datetime import datetime
from pydantic import BaseModel


# ── Client Memory ─────────────────────────────────────────────────────────────

class ClientMemoryOut(BaseModel):
    id: int
    client_id: int
    tic_area: Optional[str] = None
    problem_summary: str
    resolution_summary: Optional[str] = None
    frequency: int
    last_seen: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ── QA Entries ────────────────────────────────────────────────────────────────

class QAEntryCreate(BaseModel):
    problem: str
    solution: str
    tic_area: Optional[str] = None
    source_ticket_id: Optional[int] = None


class QAEntryOut(BaseModel):
    id: int
    problem: str
    solution: str
    tic_area: Optional[str] = None
    source_ticket_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Knowledge Base ────────────────────────────────────────────────────────────

class KnowledgeCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None


class KnowledgeOut(BaseModel):
    id: int
    title: str
    content: str
    category: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Agent responses ───────────────────────────────────────────────────────────

class CategorizeResult(BaseModel):
    ticket_id: int
    tic_area: str
    priority: str
    reasoning: str


class InteractResult(BaseModel):
    ticket_id: int
    reply_posted: bool
    message: str
    qa_saved: bool = False


class NotesResult(BaseModel):
    ticket_id: int
    note_posted: bool
    note: str


class QAuditResult(BaseModel):
    total_tickets: int
    report: str
