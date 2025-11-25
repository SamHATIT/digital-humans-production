"""
Execution model for tracking agent execution runs.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Enum, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ExecutionStatus(str, enum.Enum):
    """Execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Execution(Base):
    """Execution model for tracking multi-agent execution runs."""

    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Execution status and progress
    status = Column(Enum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False)
    progress = Column(Integer, default=0)  # Progress percentage (0-100)
    current_agent = Column(String)  # Currently executing agent name

    # PM Orchestrator specific fields
    selected_agents = Column(JSON)  # List of agent IDs selected for execution
    agent_execution_status = Column(JSON)  # Detailed status per agent {agent_id: {state, progress, message}}

    # Results
    sds_document_path = Column(String(500))  # Path to generated SDS document
    total_tokens_used = Column(Integer, default=0)  # Total tokens used across all agents
    total_cost = Column(Float, default=0.0)  # Total cost of execution

    # Timing
    duration_seconds = Column(Integer)  # Total execution duration
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Logs
    logs = Column(Text)  # JSON array of log entries stored as text

    # Relationships
    project = relationship("Project", back_populates="executions")
    user = relationship("User", back_populates="executions")
    execution_agents = relationship("ExecutionAgent", back_populates="execution", cascade="all, delete-orphan")
    outputs = relationship("Output", back_populates="execution", cascade="all, delete-orphan")
