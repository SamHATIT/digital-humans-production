"""
Agent Deliverable model for storing agent-generated content in database.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AgentDeliverable(Base):
    """Agent Deliverable model for storing agent outputs in database."""

    __tablename__ = "agent_deliverables"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    execution_agent_id = Column(Integer, ForeignKey("execution_agents.id"))

    # Content storage
    deliverable_type = Column(String(100), nullable=False, index=True)  # 'data_model', 'hld', 'apex_code', etc.
    content = Column(Text, nullable=False)  # Full content (markdown, code, etc.)
    content_metadata = Column(JSONB)  # Additional structured data

    # File reference (if converted to Word/PPTX)
    output_file_id = Column(Integer, ForeignKey("outputs.id"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    execution = relationship("Execution", backref="agent_deliverables")
    agent = relationship("Agent", backref="agent_deliverables")
    execution_agent = relationship("ExecutionAgent", backref="agent_deliverables")
    output_file = relationship("Output", backref="agent_deliverables")
