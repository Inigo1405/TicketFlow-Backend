"""
GET  /agent/qa          — list QA entries
POST /agent/qa          — create QA entry manually
GET  /agent/qa/audit    — trigger full QA audit
"""
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import TokenUser, require_agent_or_admin
from app.db.database import get_db
from app.agent.graph import run_qa_audit
from app.agent.knowledge import save_qa_to_db
from app.models.agent import QAEntry
from app.schemas.agent import QAEntryCreate, QAEntryOut, QAuditResult

router = APIRouter()


@router.get("/qa/audit", response_model=QAuditResult)
async def qa_audit(
    _: TokenUser = Depends(require_agent_or_admin),
):
    """TICBot reviews all tickets and generates a QA report."""
    report = await run_qa_audit()
    return QAuditResult(total_tickets=0, report=report)


@router.get("/qa", response_model=List[QAEntryOut])
async def list_qa(
    _: TokenUser = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(QAEntry).order_by(QAEntry.created_at.desc()))
    return result.scalars().all()


@router.post("/qa", response_model=QAEntryOut, status_code=status.HTTP_201_CREATED)
async def create_qa(
    body: QAEntryCreate,
    _: TokenUser = Depends(require_agent_or_admin),
    db: AsyncSession = Depends(get_db),
):
    entry = await save_qa_to_db(
        problem=body.problem,
        solution=body.solution,
        tic_area=body.tic_area,
        source_ticket_id=body.source_ticket_id,
        db=db,
    )
    return entry
