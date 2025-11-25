"""
ExecutionAgent model for tracking individual agent execution within a run.
"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime, Float, Enum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class AgentExecutionStatus(str, enum.Enum):
    """Agent execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionAgent(Base):
    """ExecutionAgent model for tracking individual agent executions."""

    __tablename__ = "execution_agents"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(AgentExecutionStatus), default=AgentExecutionStatus.PENDING, nullable=False)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    cost = Column(Float, default=0.0)

    # Relationships
    execution = relationship("Execution", back_populates="execution_agents")
    agent = relationship("Agent", back_populates="execution_agents")
