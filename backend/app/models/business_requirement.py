"""
Business Requirement model for storing extracted and validated requirements.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class BRStatus(str, enum.Enum):
    """Business Requirement status enumeration."""
    PENDING = "pending"
    VALIDATED = "validated"
    MODIFIED = "modified"
    DELETED = "deleted"


class BRPriority(str, enum.Enum):
    """Business Requirement priority (MoSCoW)."""
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


class BRSource(str, enum.Enum):
    """Source of the business requirement."""
    EXTRACTED = "extracted"  # Extracted by Sophie
    MANUAL = "manual"        # Added manually by client


class BusinessRequirement(Base):
    """Business Requirement model for tracking requirements through validation."""

    __tablename__ = "business_requirements"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relations
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Unique identifier (BR-001, BR-002, etc.)
    br_id = Column(String(20), nullable=False)
    
    # Content
    category = Column(String(100))
    requirement = Column(Text, nullable=False)
    priority = Column(Enum(BRPriority), default=BRPriority.SHOULD)
    
    # Source and versioning
    source = Column(Enum(BRSource), default=BRSource.EXTRACTED)
    original_text = Column(Text)  # What Sophie extracted (for history)
    
    # Validation
    status = Column(Enum(BRStatus), default=BRStatus.PENDING)
    client_notes = Column(Text)
    validated_at = Column(DateTime(timezone=True))
    validated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Ordering
    order_index = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    execution = relationship("Execution", back_populates="business_requirements")
    project = relationship("Project", back_populates="br_items")
    change_requests = relationship("ChangeRequest", back_populates="related_br")
    validator = relationship("User", foreign_keys=[validated_by])

    def __repr__(self):
        return f"<BusinessRequirement {self.br_id}: {self.requirement[:50]}...>"
