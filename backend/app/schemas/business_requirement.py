"""
Pydantic schemas for Business Requirement model validation and serialization.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models.business_requirement import BRStatus, BRPriority, BRSource


# ==================== BASE SCHEMAS ====================

class BusinessRequirementBase(BaseModel):
    """Base schema with common attributes."""
    category: Optional[str] = Field(None, max_length=100)
    requirement: str = Field(..., min_length=1)
    priority: BRPriority = BRPriority.SHOULD
    client_notes: Optional[str] = None


class BusinessRequirementCreate(BusinessRequirementBase):
    """Schema for creating a new BR (manual add)."""
    pass


class BusinessRequirementUpdate(BaseModel):
    """Schema for updating a BR."""
    category: Optional[str] = Field(None, max_length=100)
    requirement: Optional[str] = Field(None, min_length=1)
    priority: Optional[BRPriority] = None
    client_notes: Optional[str] = None


class BusinessRequirementExtracted(BaseModel):
    """Schema for Sophie's extracted BR."""
    category: str
    requirement: str
    priority: BRPriority = BRPriority.SHOULD


# ==================== RESPONSE SCHEMAS ====================

class BusinessRequirementResponse(BusinessRequirementBase):
    """Schema for BR response."""
    id: int
    execution_id: Optional[int] = None
    project_id: int
    br_id: str
    source: BRSource
    original_text: Optional[str] = None
    status: BRStatus
    validated_at: Optional[datetime] = None
    validated_by: Optional[int] = None
    order_index: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BusinessRequirementListResponse(BaseModel):
    """Schema for list of BRs with stats."""
    brs: List[BusinessRequirementResponse]
    total: int
    pending: int
    validated: int
    modified: int
    deleted: int


# ==================== EXTRACTION SCHEMAS ====================

class BRExtractionRequest(BaseModel):
    """Request to extract BRs from project."""
    project_id: int


class BRExtractionResponse(BaseModel):
    """Response after BR extraction."""
    execution_id: int
    project_id: int
    brs_extracted: int
    message: str


# ==================== VALIDATION SCHEMAS ====================

class BRValidateAllRequest(BaseModel):
    """Request to validate all BRs."""
    pass


class BRValidateAllResponse(BaseModel):
    """Response after validating all BRs."""
    validated_count: int
    message: str


# ==================== REORDER SCHEMA ====================

class BRReorderRequest(BaseModel):
    """Request to reorder BRs."""
    order: List[int]  # List of BR ids in new order


class BRReorderResponse(BaseModel):
    """Response after reordering."""
    success: bool
    message: str
