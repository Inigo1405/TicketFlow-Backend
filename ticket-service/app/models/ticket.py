from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(30), nullable=False, default="general")
    # general | technical | billing | access | other
    priority = Column(String(20), nullable=False, default="low")
    # low | medium | high | critical
    status = Column(String(20), nullable=False, default="open")
    # open | pending | resolved | closed
    notes = Column(Text, nullable=True)
    sla_breached = Column(Boolean, nullable=False, default=False)
    created_by = Column(Integer, nullable=False, index=True)  # user id de auth-service
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    replies = relationship("Reply", back_populates="ticket", cascade="all, delete-orphan")


class Reply(Base):
    __tablename__ = "replies"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, nullable=False)
    author_name = Column(String(120), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ticket = relationship("Ticket", back_populates="replies")
