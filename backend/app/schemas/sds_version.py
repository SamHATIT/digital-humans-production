"""Schemas for SDS versions."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SDSVersionBase(BaseModel):
    """Base schema for SDS version."""
    version_number: int
    notes: Optional[str] = None


class SDSVersionCreate(SDSVersionBase):
    """Schema for creating an SDS version."""
    project_id: int
    execution_id: Optional[int] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    change_request_id: Optional[int] = None


class SDSVersionResponse(SDSVersionBase):
    """Schema for SDS version response."""
    id: int
    project_id: int
    execution_id: Optional[int] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    change_request_id: Optional[int] = None
    generated_at: datetime
    created_at: datetime
    
    # Computed field for download URL
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


class SDSVersionList(BaseModel):
    """Schema for list of SDS versions."""
    versions: list[SDSVersionResponse]
    current_version: int
    total_count: int
