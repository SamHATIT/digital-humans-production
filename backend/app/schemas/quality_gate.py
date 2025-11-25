"""
Pydantic schemas for Quality Gates.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel

from app.models.quality_gate import GateStatus


class QualityGateBase(BaseModel):
    """Base Quality Gate schema."""
    gate_type: str
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    status: GateStatus
    validation_details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class QualityGateCreate(QualityGateBase):
    """Schema for creating Quality Gate."""
    execution_id: int
    agent_id: int
    execution_agent_id: Optional[int] = None


class QualityGateResponse(QualityGateBase):
    """Schema for Quality Gate response."""
    id: int
    execution_id: int
    agent_id: int
    execution_agent_id: Optional[int] = None
    checked_at: datetime

    class Config:
        from_attributes = True


class QualityGateSummary(BaseModel):
    """Schema for Quality Gate summary."""
    agent_id: int
    agent_name: str
    total_gates: int
    passed_gates: int
    failed_gates: int
    all_passed: bool
    gates: List[QualityGateResponse]


class IterationBase(BaseModel):
    """Base Iteration schema."""
    iteration_number: int
    retry_reason: Optional[str] = None
    status: str  # retrying, completed, failed


class IterationCreate(IterationBase):
    """Schema for creating Iteration."""
    execution_id: int
    agent_id: int
    quality_gate_id: Optional[int] = None


class IterationResponse(IterationBase):
    """Schema for Iteration response."""
    id: int
    execution_id: int
    agent_id: int
    quality_gate_id: Optional[int] = None
    new_deliverable_id: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
