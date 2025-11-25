"""
Pydantic schemas for Project model validation and serialization.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.models.project import ProjectStatus


class ProjectBase(BaseModel):
    """Base project schema with common attributes."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None

    # PM Orchestrator specific fields
    salesforce_product: Optional[str] = Field(None, max_length=100)
    organization_type: Optional[str] = Field(None, max_length=100)
    business_requirements: Optional[str] = Field(None, description="Business requirements (3-7 bullet points max)")

    # Technical Context
    existing_systems: Optional[str] = None
    compliance_requirements: Optional[str] = None
    expected_users: Optional[int] = Field(None, ge=0)
    expected_data_volume: Optional[str] = Field(None, max_length=100)

    # Architecture Preferences
    architecture_preferences: Optional[Dict[str, Any]] = None
    architecture_notes: Optional[str] = None

    # Legacy fields (for backwards compatibility)
    requirements_text: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Schema for creating a new project via PM Orchestrator."""
    # PM Orchestrator requires these fields
    salesforce_product: str = Field(..., description="Service Cloud, Sales Cloud, etc.")
    organization_type: str = Field(..., description="New Implementation, Existing Org Enhancement, Migration")
    business_requirements: str = Field(..., min_length=10, description="Clear business objectives (3-7 lines)")


class ProjectUpdate(BaseModel):
    """Schema for updating project information."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    salesforce_product: Optional[str] = Field(None, max_length=100)
    organization_type: Optional[str] = Field(None, max_length=100)
    business_requirements: Optional[str] = None
    existing_systems: Optional[str] = None
    compliance_requirements: Optional[str] = None
    expected_users: Optional[int] = Field(None, ge=0)
    expected_data_volume: Optional[str] = Field(None, max_length=100)
    architecture_preferences: Optional[Dict[str, Any]] = None
    architecture_notes: Optional[str] = None
    requirements_text: Optional[str] = None
    status: Optional[ProjectStatus] = None


class ProjectInDB(ProjectBase):
    """Schema for project stored in database."""
    id: int
    user_id: int
    requirements_file_path: Optional[str] = None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Project(ProjectInDB):
    """Schema for project response (public)."""
    pass
