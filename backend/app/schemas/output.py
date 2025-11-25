"""
Pydantic schemas for Output model validation and serialization.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class OutputBase(BaseModel):
    """Base output schema with common attributes."""
    file_name: str
    file_size: Optional[int] = None
    mime_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class OutputCreate(OutputBase):
    """Schema for creating a new output."""
    project_id: int
    execution_id: int
    agent_id: Optional[int] = None
    file_path: str


class OutputInDB(OutputBase):
    """Schema for output stored in database."""
    id: int
    project_id: int
    execution_id: int
    agent_id: Optional[int] = None
    file_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class Output(OutputInDB):
    """Schema for output response (public)."""
    pass
