"""
Pydantic schemas for Document Fusion.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

from app.models.document_fusion import FusionStatus


class DocumentFusionBase(BaseModel):
    """Base Document Fusion schema."""
    fusion_type: str  # 'functional_specs', 'technical_specs'
    source_deliverable_ids: List[int]


class DocumentFusionCreate(DocumentFusionBase):
    """Schema for creating Document Fusion."""
    project_id: int
    execution_id: int


class DocumentFusionUpdate(BaseModel):
    """Schema for updating Document Fusion."""
    content: Optional[str] = None
    output_file_id: Optional[int] = None
    fusion_status: Optional[FusionStatus] = None


class DocumentFusionResponse(DocumentFusionBase):
    """Schema for Document Fusion response."""
    id: int
    project_id: int
    execution_id: int
    content: Optional[str] = None
    output_file_id: Optional[int] = None
    fusion_status: FusionStatus
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentFusionStatus(BaseModel):
    """Schema for Document Fusion status."""
    fusion_type: str
    status: FusionStatus
    output_file_url: Optional[str] = None
    source_deliverables: List[int]
    completed_at: Optional[datetime] = None
