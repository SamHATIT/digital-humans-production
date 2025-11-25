"""
PM Orchestration model for storing PM-generated deliverables (PRD, User Stories, Roadmap).
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class PMStatus(str, enum.Enum):
    """PM orchestration status enumeration."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class PMOrchestration(Base):
    """PM Orchestration model for storing PM deliverables."""

    __tablename__ = "pm_orchestration"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"))

    # Business Input (from user)
    business_need = Column(Text, nullable=False)  # Raw non-technical description
    business_context = Column(JSONB)  # Additional context (industry, size, etc.)

    # PM Generated Deliverables
    prd_content = Column(Text)  # Full PRD markdown/text
    user_stories = Column(JSONB)  # Array of user stories
    roadmap = Column(JSONB)  # Structured roadmap

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    generated_at = Column(DateTime(timezone=True))  # When PM finished generation

    # Status tracking
    pm_status = Column(Enum(PMStatus), default=PMStatus.PENDING, nullable=False)

    # Relationships
    project = relationship("Project", backref="pm_orchestration")
    execution = relationship("Execution", backref="pm_orchestration")
