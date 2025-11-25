"""
Pydantic schemas for PM Orchestration.
"""
from typing import Optional, Dict, List, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.pm_orchestration import PMStatus


class UserStory(BaseModel):
    """User Story schema."""
    id: str
    title: str
    description: str
    acceptance_criteria: List[str]
    priority: str  # Must Have, Should Have, Could Have, Won't Have
    story_points: int
    dependencies: List[str] = []


class RoadmapPhase(BaseModel):
    """Roadmap Phase schema."""
    name: str
    duration_weeks: int
    user_stories: List[str]  # List of user story IDs
    deliverables: List[str]
    success_criteria: List[str]


class PMOrchestrationBase(BaseModel):
    """Base PM Orchestration schema."""
    business_need: str
    business_context: Optional[Dict[str, Any]] = None


class PMOrchestrationCreate(PMOrchestrationBase):
    """Schema for creating PM Orchestration."""
    project_id: int


class PMOrchestrationUpdate(BaseModel):
    """Schema for updating PM Orchestration."""
    business_need: Optional[str] = None
    business_context: Optional[Dict[str, Any]] = None
    prd_content: Optional[str] = None
    user_stories: Optional[List[Dict[str, Any]]] = None
    roadmap: Optional[Dict[str, Any]] = None
    pm_status: Optional[PMStatus] = None


class PMOrchestrationResponse(PMOrchestrationBase):
    """Schema for PM Orchestration response."""
    id: int
    project_id: int
    execution_id: Optional[int] = None
    prd_content: Optional[str] = None
    user_stories: Optional[List[Dict[str, Any]]] = None
    roadmap: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    generated_at: Optional[datetime] = None
    pm_status: PMStatus

    class Config:
        from_attributes = True


class PMDialogueRequest(BaseModel):
    """Schema for PM dialogue request."""
    project_id: int
    message: str
    is_final_input: bool = False


class PMDialogueResponse(BaseModel):
    """Schema for PM dialogue response."""
    pm_response: str
    next_questions: List[str] = []
    can_generate_prd: bool = False
    context_updated: bool = True


class GeneratePRDRequest(BaseModel):
    """Schema for generate PRD request."""
    project_id: int


class GeneratePRDResponse(BaseModel):
    """Schema for generate PRD response."""
    orchestration_id: int
    generation_status: str  # 'started', 'completed', 'failed'
    prd_content: Optional[str] = None
