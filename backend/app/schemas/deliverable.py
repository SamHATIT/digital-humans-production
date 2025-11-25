"""
Pydantic schemas for Agent Deliverables.
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class AgentDeliverableBase(BaseModel):
    """Base Agent Deliverable schema."""
    deliverable_type: str
    content: str
    content_metadata: Optional[Dict[str, Any]] = None


class AgentDeliverableCreate(AgentDeliverableBase):
    """Schema for creating Agent Deliverable."""
    execution_id: int
    agent_id: int
    execution_agent_id: Optional[int] = None
    output_file_id: Optional[int] = None


class AgentDeliverableUpdate(BaseModel):
    """Schema for updating Agent Deliverable."""
    content: Optional[str] = None
    content_metadata: Optional[Dict[str, Any]] = None
    output_file_id: Optional[int] = None


class AgentDeliverableResponse(AgentDeliverableBase):
    """Schema for Agent Deliverable response."""
    id: int
    execution_id: int
    agent_id: int
    execution_agent_id: Optional[int] = None
    output_file_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentDeliverablePreview(BaseModel):
    """Schema for Agent Deliverable preview (truncated content)."""
    id: int
    agent_id: int
    agent_name: str
    deliverable_type: str
    content_preview: str  # First 500 chars
    content_size: int
    content_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    download_url: Optional[str] = None


class AgentDeliverableFull(BaseModel):
    """Schema for full Agent Deliverable content."""
    id: int
    deliverable_type: str
    content: str
    content_metadata: Optional[Dict[str, Any]] = None
    download_url: Optional[str] = None
    created_at: datetime
