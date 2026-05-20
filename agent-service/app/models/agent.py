from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, func
from app.db.database import Base


class ClientMemory(Base):
    """Stores recurring problem patterns per client. Updated on every resolved interaction."""
    __tablename__ = "client_memories"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, nullable=False, index=True)
    tic_area = Column(String(50), nullable=True)
    problem_summary = Column(Text, nullable=False)
    resolution_summary = Column(Text, nullable=True)
    frequency = Column(Integer, nullable=False, default=1)
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class QAEntry(Base):
    """Problem-solution pairs saved by the agent from resolved conversations."""
    __tablename__ = "qa_entries"

    id = Column(Integer, primary_key=True, index=True)
    problem = Column(Text, nullable=False)
    solution = Column(Text, nullable=False)
    tic_area = Column(String(50), nullable=True)
    source_ticket_id = Column(Integer, nullable=True, index=True)
    vector_id = Column(String(100), nullable=True)  # Qdrant point UUID
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeBase(Base):
    """Internal company knowledge documents indexed in Qdrant."""
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(80), nullable=True)
    vector_id = Column(String(100), nullable=True)  # Qdrant point UUID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
