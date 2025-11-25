"""
Agent Iteration model for tracking retry attempts when quality gates fail.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class IterationStatus(str, enum.Enum):
    """Agent iteration status enumeration."""
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentIteration(Base):
    """Agent Iteration model for retry tracking."""

    __tablename__ = "agent_iterations"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)

    iteration_number = Column(Integer, nullable=False)  # 1, 2 (max 2 iterations)

    # Reason for iteration
    quality_gate_id = Column(Integer, ForeignKey("quality_gates.id"))
    retry_reason = Column(Text)

    # New deliverable after retry
    new_deliverable_id = Column(Integer, ForeignKey("agent_deliverables.id"))

    # Status
    status = Column(Enum(IterationStatus), nullable=False)

    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    execution = relationship("Execution", backref="agent_iterations")
    agent = relationship("Agent", backref="agent_iterations")
    quality_gate = relationship("QualityGate", backref="agent_iterations")
    new_deliverable = relationship("AgentDeliverable", backref="agent_iterations")
