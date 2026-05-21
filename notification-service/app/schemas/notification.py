from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel

NotificationType = Literal[
    "ticket_created",
    "ticket_updated",
    "ticket_resolved",
    "ticket_closed",
    "ticket_pending",
    "new_reply",
    "new_client_reply",
    "sla_breached",
    "ticket_escalated",
    "critical_ticket",
    "agent_note",
]


class NotificationOut(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    message: str
    ticket_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationCreate(BaseModel):
    # Usado internamente por el consumer de RabbitMQ para persistir notificaciones.
    user_id: int
    type: NotificationType
    title: str
    message: str
    ticket_id: Optional[int] = None


class NotificationEvent(BaseModel):
    # Payload que otros servicios publican en RabbitMQ.
    user_ids: list[int] = []          # destinatarios específicos (IDs)
    notify_roles: list[str] = []      # roles a notificar — notification-service resuelve los IDs
    type: NotificationType
    title: str
    message: str
    ticket_id: Optional[int] = None
    send_email: bool = False          # si True, envía email a los user_ids vía EmailJS
