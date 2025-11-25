"""
Pydantic schemas for Execution model validation and serialization.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.execution import ExecutionStatus


class ExecutionCreate(BaseModel):
    """Schema for creating a new execution via PM Orchestrator."""
    project_id: int
    selected_agents: List[str] = Field(..., min_length=1, description="List of agent IDs (e.g., ['ba', 'architect', 'pm'])")


class ExecutionUpdate(BaseModel):
    """Schema for updating execution information."""
    status: Optional[ExecutionStatus] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    current_agent: Optional[str] = None
    agent_execution_status: Optional[Dict[str, Any]] = None


class AgentStatus(BaseModel):
    """Schema for individual agent execution status."""
    state: str = Field(..., description="waiting, running, completed, error")
    progress: int = Field(default=0, ge=0, le=100)
    message: str = Field(default="", description="Current status message")


class ExecutionInDB(BaseModel):
    """Schema for execution stored in database."""
    id: int
    project_id: int
    user_id: int
    status: ExecutionStatus
    progress: int
    current_agent: Optional[str] = None

    # PM Orchestrator fields
    selected_agents: Optional[List[str]] = None
    agent_execution_status: Optional[Dict[str, Dict[str, Any]]] = None
    sds_document_path: Optional[str] = None
    total_tokens_used: int = 0

    # Costs and timing
    total_cost: float
    duration_seconds: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    # Logs
    logs: Optional[str] = None

    class Config:
        from_attributes = True


class Execution(ExecutionInDB):
    """Schema for execution response (public)."""
    pass


class ExecutionStartResponse(BaseModel):
    """Response when starting a new execution."""
    execution_id: int
    status: str
    message: str


class ExecutionResultResponse(BaseModel):
    """Response for completed execution."""
    execution_id: int
    status: ExecutionStatus
    sds_document_url: Optional[str] = None
    execution_time: Optional[int] = None
    agents_used: int
    total_cost: float
    completed_at: Optional[datetime] = None


class ExecutionLog(BaseModel):
    """Schema for execution log entry."""
    timestamp: datetime
    level: str  # info, warning, error
    message: str
    agent: Optional[str] = None


class ExecutionProgress(BaseModel):
    """Schema for SSE execution progress updates."""
    execution_id: int
    status: ExecutionStatus
    progress: int
    current_agent: Optional[str] = None
    agent_statuses: Dict[str, AgentStatus]
    message: str
