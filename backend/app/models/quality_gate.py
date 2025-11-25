"""
Quality Gate model for tracking agent quality checks.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class GateStatus(str, enum.Enum):
    """Quality gate status enumeration."""
    PASSED = "passed"
    FAILED = "failed"


class QualityGate(Base):
    """Quality Gate model for agent quality validation."""

    __tablename__ = "quality_gates"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    execution_agent_id = Column(Integer, ForeignKey("execution_agents.id"))

    # Gate details
    gate_type = Column(String(100), nullable=False)  # 'erd_present', 'hld_size', 'test_coverage', etc.
    expected_value = Column(Text)  # What was expected
    actual_value = Column(Text)  # What was found

    # Status
    status = Column(Enum(GateStatus), nullable=False, index=True)

    # Validation details
    validation_details = Column(JSONB)
    error_message = Column(Text)

    # Timestamps
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    execution = relationship("Execution", backref="quality_gates")
    agent = relationship("Agent", backref="quality_gates")
    execution_agent = relationship("ExecutionAgent", backref="quality_gates")
