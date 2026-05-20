from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, field_validator

CategoryType = Literal["general", "technical", "billing", "access", "other"]
PriorityType = Literal["low", "medium", "high", "critical"]
StatusType = Literal["open", "pending", "resolved", "closed"]
TICAreaType = Literal[
    "backend_services",
    "frontend_services",
    "general_tech_support",
    "network_infrastructure",
    "cybersecurity",
    "data_databases",
    "cloud_services",
    "systems_hardware",
    "uncategorized",
]


class ReplyOut(BaseModel):
    id: int
    author_id: int
    author_name: str
    text: str
    is_internal: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ReplyCreate(BaseModel):
    text: str
    is_internal: bool = False

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El texto del reply no puede estar vacío")
        return v.strip()


class TicketBase(BaseModel):
    title: str
    description: str
    category: CategoryType = "general"


class TicketCreate(TicketBase):
    status: Literal["open", "pending"] = "open"

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El título no puede estar vacío")
        return v.strip()


class TicketUpdate(BaseModel):
    priority: Optional[PriorityType] = None
    notes: Optional[str] = None
    tic_area: Optional[TICAreaType] = None
    agent_processed: Optional[bool] = None


class TicketOut(TicketBase):
    id: int
    priority: PriorityType
    status: StatusType
    tic_area: TICAreaType = "uncategorized"
    agent_processed: bool = False
    created_at: datetime
    created_by: int
    sla_breached: bool
    notes: Optional[str] = None
    replies: List[ReplyOut] = []

    model_config = {"from_attributes": True}


# Lightweight version without replies for list endpoints
class TicketSummary(TicketBase):
    id: int
    priority: PriorityType
    status: StatusType
    tic_area: TICAreaType = "uncategorized"
    agent_processed: bool = False
    created_at: datetime
    created_by: int
    sla_breached: bool
    notes: Optional[str] = None

    model_config = {"from_attributes": True}
