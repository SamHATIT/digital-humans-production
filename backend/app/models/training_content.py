"""
Training Content model for storing Trainer-generated content (Phase 3).
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ContentStatus(str, enum.Enum):
    """Training content status enumeration."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class FormattingStatus(str, enum.Enum):
    """Training formatting status enumeration."""
    PENDING = "pending"
    FORMATTING = "formatting"
    COMPLETED = "completed"
    FAILED = "failed"


class TrainingContent(Base):
    """Training Content model for Trainer outputs."""

    __tablename__ = "training_content"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Content structure (JSON format from Trainer)
    training_guide = Column(JSONB)  # Structured training guide content
    presentation_slides = Column(JSONB)  # Structured presentation content

    # Generated files (after N8N formatting)
    training_guide_file_id = Column(Integer, ForeignKey("outputs.id"))
    presentation_file_id = Column(Integer, ForeignKey("outputs.id"))

    # Status
    content_status = Column(Enum(ContentStatus), default=ContentStatus.PENDING, nullable=False)
    formatting_status = Column(Enum(FormattingStatus), default=FormattingStatus.PENDING, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    content_generated_at = Column(DateTime(timezone=True))
    files_generated_at = Column(DateTime(timezone=True))

    # Relationships
    execution = relationship("Execution", backref="training_content")
    training_guide_file = relationship("Output", foreign_keys=[training_guide_file_id], backref="training_guide_content")
    presentation_file = relationship("Output", foreign_keys=[presentation_file_id], backref="presentation_content")
