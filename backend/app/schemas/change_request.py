"""Schemas for Change Requests."""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel
from decimal import Decimal

from app.models.change_request import CRStatus, CRCategory, CRPriority


class ImpactAnalysis(BaseModel):
    """Schema for impact analysis results."""
    affected_brs: List[str] = []
    affected_use_cases: List[str] = []
    affected_architecture: List[str] = []
    affected_agents: List[str] = []
    estimated_tokens: int = 0
    estimated_cost: float = 0.0
    summary: str = ""
    risk_level: str = "low"  # low, medium, high


class ChangeRequestBase(BaseModel):
    """Base schema for change request."""
    category: str
    title: str
    description: str
    priority: str = "medium"
    related_br_id: Optional[int] = None


class ChangeRequestCreate(ChangeRequestBase):
    """Schema for creating a change request."""
    pass


class ChangeRequestUpdate(BaseModel):
    """Schema for updating a change request."""
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    related_br_id: Optional[int] = None


class ChangeRequestSubmit(BaseModel):
    """Schema for submitting a CR for analysis."""
    pass


class ChangeRequestApprove(BaseModel):
    """Schema for approving a CR."""
    notes: Optional[str] = None


class ChangeRequestResponse(ChangeRequestBase):
    """Schema for change request response."""
    id: int
    project_id: int
    execution_id: Optional[int] = None
    cr_number: str
    status: str
    
    # Impact analysis
    impact_analysis: Optional[dict] = None
    estimated_cost: Optional[float] = None
    agents_to_rerun: Optional[List[str]] = None
    
    # Result
    resolution_notes: Optional[str] = None
    resulting_sds_version_id: Optional[int] = None
    
    # Timestamps
    created_at: datetime
    submitted_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Related BR info (for display)
    related_br_text: Optional[str] = None

    class Config:
        from_attributes = True


class ChangeRequestList(BaseModel):
    """Schema for list of change requests."""
    change_requests: List[ChangeRequestResponse]
    total_count: int
    pending_count: int
    completed_count: int
