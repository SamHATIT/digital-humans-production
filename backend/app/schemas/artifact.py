"""
Pydantic schemas for V2 artifacts system
Digital Humans - Traceable Artifacts
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


# ============ ENUMS ============

class ArtifactTypeEnum(str, Enum):
    REQUIREMENT = 'requirement'
    BUSINESS_REQ = 'business_req'
    USE_CASE = 'use_case'
    QUESTION = 'question'
    ADR = 'adr'
    SPEC = 'spec'
    CODE = 'code'
    CONFIG = 'config'
    TEST = 'test'
    DOC = 'doc'


class ArtifactStatusEnum(str, Enum):
    DRAFT = 'draft'
    PENDING_REVIEW = 'pending_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    SUPERSEDED = 'superseded'


class GateStatusEnum(str, Enum):
    PENDING = 'pending'
    READY = 'ready'
    APPROVED = 'approved'
    REJECTED = 'rejected'


class QuestionStatusEnum(str, Enum):
    PENDING = 'pending'
    ANSWERED = 'answered'


# ============ ARTIFACT SCHEMAS ============

class ArtifactBase(BaseModel):
    """Base schema for artifacts"""
    artifact_type: ArtifactTypeEnum
    artifact_code: str = Field(..., max_length=20, description="Unique code like UC-001, BR-002")
    title: str = Field(..., max_length=255)
    producer_agent: str = Field(..., max_length=20)
    content: Dict[str, Any]
    parent_refs: Optional[List[str]] = None


class ArtifactCreate(ArtifactBase):
    """Schema for creating a new artifact"""
    execution_id: int


class ArtifactUpdate(BaseModel):
    """Schema for updating an artifact (creates new version)"""
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[Dict[str, Any]] = None
    parent_refs: Optional[List[str]] = None


class ArtifactStatusUpdate(BaseModel):
    """Schema for updating artifact status"""
    status: ArtifactStatusEnum
    rejection_reason: Optional[str] = None


class ArtifactResponse(ArtifactBase):
    """Schema for artifact response"""
    id: int
    execution_id: int
    version: int
    is_current: bool
    status: ArtifactStatusEnum
    status_changed_at: Optional[datetime] = None
    status_changed_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArtifactListResponse(BaseModel):
    """Schema for list of artifacts with stats"""
    artifacts: List[ArtifactResponse]
    total: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]


# ============ VALIDATION GATE SCHEMAS ============

class GateBase(BaseModel):
    """Base schema for validation gates"""
    gate_number: int = Field(..., ge=1, le=6)
    gate_name: str = Field(..., max_length=50)
    phase: str = Field(..., max_length=50)
    artifact_types: List[str]


class GateCreate(GateBase):
    """Schema for creating a gate"""
    execution_id: int


class GateStatusUpdate(BaseModel):
    """Schema for updating gate status"""
    status: GateStatusEnum
    rejection_reason: Optional[str] = None


class GateResponse(GateBase):
    """Schema for gate response"""
    id: int
    execution_id: int
    artifacts_count: int
    status: GateStatusEnum
    submitted_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None
    validated_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class GateListResponse(BaseModel):
    """Schema for list of gates with progress"""
    gates: List[GateResponse]
    current_gate: Optional[int] = None
    progress_percent: float


# ============ QUESTION SCHEMAS ============

class QuestionBase(BaseModel):
    """Base schema for agent questions"""
    question_code: str = Field(..., max_length=20, description="Unique code like Q-001")
    from_agent: str = Field(..., max_length=20)
    to_agent: str = Field(..., max_length=20)
    context: str
    question: str
    related_artifacts: Optional[List[str]] = None


class QuestionCreate(QuestionBase):
    """Schema for creating a question"""
    execution_id: int


class QuestionAnswer(BaseModel):
    """Schema for answering a question"""
    answer: str
    recommendation: Optional[str] = None


class QuestionResponse(QuestionBase):
    """Schema for question response"""
    id: int
    execution_id: int
    answer: Optional[str] = None
    recommendation: Optional[str] = None
    answered_at: Optional[datetime] = None
    status: QuestionStatusEnum
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionListResponse(BaseModel):
    """Schema for list of questions with counts"""
    questions: List[QuestionResponse]
    pending_count: int
    answered_count: int


# ============ GRAPH SCHEMAS ============

class GraphNode(BaseModel):
    """Node in the dependency graph"""
    id: str  # artifact_code
    type: ArtifactTypeEnum
    title: str
    status: ArtifactStatusEnum
    producer: str


class GraphEdge(BaseModel):
    """Edge in the dependency graph"""
    source: str  # artifact_code
    target: str  # artifact_code
    relation: str  # "derives_from", "implements", etc.


class DependencyGraph(BaseModel):
    """Complete dependency graph for visualization"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# ============ AGENT CONTEXT SCHEMA ============

class AgentContext(BaseModel):
    """Context provided to an agent for execution"""
    execution_id: int
    agent_id: str
    artifacts: List[ArtifactResponse]
    pending_questions: List[QuestionResponse]
    answered_questions: List[QuestionResponse]


# ============ INITIALIZATION SCHEMAS ============

class InitializeGatesRequest(BaseModel):
    """Request to initialize all 6 gates for an execution"""
    execution_id: int


class InitializeGatesResponse(BaseModel):
    """Response after initializing gates"""
    execution_id: int
    gates_created: int
    gates: List[GateResponse]
