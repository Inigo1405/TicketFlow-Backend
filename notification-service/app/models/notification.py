from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, func

from app.db.database import Base


class Notification(Base):
    """
    Notificación dirigida a un usuario específico.

    Tipos soportados (type):
      - ticket_created   : se creó un ticket nuevo (notifica a Agentes/Admin)
      - ticket_updated   : prioridad o área cambiaron (notifica al creador)
      - ticket_resolved  : el ticket fue resuelto (notifica al creador)
      - ticket_closed    : el ticket fue cerrado (notifica al creador)
      - ticket_pending   : el ticket pasó a pendiente (notifica al creador)
      - new_reply        : hay una nueva respuesta en el hilo (notifica al creador)
      - sla_breached     : el ticket superó el tiempo de SLA (notifica a Agentes/Admin)
      - agent_note       : TICBot publicó una nota interna (notifica a Agentes/Admin)
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)   # destinatario
    type = Column(String(40), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    ticket_id = Column(Integer, nullable=True, index=True)  # referencia opcional al ticket
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
