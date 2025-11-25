"""
Project model for managing user projects and requirements.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ProjectStatus(str, enum.Enum):
    """Project status enumeration."""
    DRAFT = "draft"
    READY = "ready"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(Base):
    """Project model for storing project information and requirements."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Basic project information
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # PM Orchestrator specific fields
    salesforce_product = Column(String(100))  # Service Cloud, Sales Cloud, etc.
    organization_type = Column(String(100))  # New Implementation, Existing Org, Migration

    # Business Requirements (3-7 lines max)
    business_requirements = Column(Text)

    # Technical Context (optional)
    existing_systems = Column(Text)
    compliance_requirements = Column(Text)
    expected_users = Column(Integer)
    expected_data_volume = Column(String(100))

    # Architecture Preferences (stored as JSON)
    architecture_preferences = Column(JSON)
    architecture_notes = Column(Text)

    # Legacy fields (for backwards compatibility)
    requirements_text = Column(Text)
    requirements_file_path = Column(String)

    # Metadata
    status = Column(Enum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="projects")
    executions = relationship("Execution", back_populates="project", cascade="all, delete-orphan")
    outputs = relationship("Output", back_populates="project", cascade="all, delete-orphan")
