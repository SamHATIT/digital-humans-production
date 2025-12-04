"""Change Request model for SDS modifications."""
import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, ARRAY, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class CRStatus(str, enum.Enum):
    """Change Request status enumeration."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ANALYZED = "analyzed"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"


class CRCategory(str, enum.Enum):
    """Change Request category enumeration."""
    BUSINESS_RULE = "business_rule"
    DATA_MODEL = "data_model"
    PROCESS = "process"
    UI_UX = "ui_ux"
    INTEGRATION = "integration"
    SECURITY = "security"
    OTHER = "other"


class CRPriority(str, enum.Enum):
    """Change Request priority enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeRequest(Base):
    """Model for Change Requests on SDS documents."""
    __tablename__ = "change_requests"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="SET NULL"), nullable=True)
    
    # Classification
    cr_number = Column(String(20), nullable=False)  # CR-001, CR-002...
    category = Column(String(50), nullable=False)
    related_br_id = Column(Integer, ForeignKey("business_requirements.id", ondelete="SET NULL"), nullable=True)
    
    # Content
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(20), default="medium")
    
    # Impact analysis (filled by Sophie)
    impact_analysis = Column(JSONB)
    estimated_cost = Column(Numeric(10, 2))
    agents_to_rerun = Column(ARRAY(String))
    
    # Status
    status = Column(String(30), default="draft")
    
    # Result
    resolution_notes = Column(Text)
    resulting_sds_version_id = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True))
    analyzed_at = Column(DateTime(timezone=True))
    approved_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # User
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="change_requests")
    execution = relationship("Execution", back_populates="change_requests")
    related_br = relationship("BusinessRequirement", back_populates="change_requests")
    resulting_sds = relationship("SDSVersion", back_populates="change_request", uselist=False)
    creator = relationship("User")
