"""
Document Fusion model for tracking merged documents (Phase 1, Step 3).
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class FusionStatus(str, enum.Enum):
    """Document fusion status enumeration."""
    PENDING = "pending"
    FUSING = "fusing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentFusion(Base):
    """Document Fusion model for merged documents."""

    __tablename__ = "document_fusion"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Source deliverables used in fusion
    source_deliverable_ids = Column(ARRAY(Integer), nullable=False)  # Array of agent_deliverables.id

    # Fused document details
    fusion_type = Column(String(50), nullable=False)  # 'functional_specs', 'technical_specs'
    content = Column(Text)  # Fused content

    # Output file reference
    output_file_id = Column(Integer, ForeignKey("outputs.id"))

    # Status
    fusion_status = Column(Enum(FusionStatus), default=FusionStatus.PENDING, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))

    # Relationships
    project = relationship("Project", backref="document_fusions")
    execution = relationship("Execution", backref="document_fusions")
    output_file = relationship("Output", backref="document_fusions")
