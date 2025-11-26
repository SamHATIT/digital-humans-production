"""
API routes for V2 artifacts system
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.services.artifact_service import ArtifactService
from app.schemas.artifact import (
    ArtifactCreate, ArtifactUpdate, ArtifactStatusUpdate, ArtifactResponse, ArtifactListResponse,
    GateResponse, GateListResponse, GateStatusUpdate,
    QuestionCreate, QuestionAnswer, QuestionResponse, QuestionListResponse,
    DependencyGraph, AgentContext,
    InitializeGatesRequest, InitializeGatesResponse,
    ArtifactStatusEnum, GateStatusEnum
)

router = APIRouter(prefix="/api/v2", tags=["V2 Artifacts"])


# ============ ARTIFACT ENDPOINTS ============

@router.post("/artifacts", response_model=ArtifactResponse)
def create_artifact(data: ArtifactCreate, db: Session = Depends(get_db)):
    """Create a new artifact"""
    service = ArtifactService(db)
    try:
        artifact = service.create_artifact(data)
        return artifact
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/artifacts", response_model=ArtifactListResponse)
def list_artifacts(
    execution_id: int,
    artifact_type: Optional[str] = None,
    status: Optional[str] = None,
    current_only: bool = True,
    db: Session = Depends(get_db)
):
    """List artifacts for an execution"""
    service = ArtifactService(db)
    artifacts = service.list_artifacts(execution_id, artifact_type, status, current_only)
    stats = service.get_artifacts_stats(execution_id)
    return ArtifactListResponse(
        artifacts=artifacts,
        total=stats["total"],
        by_type=stats["by_type"],
        by_status=stats["by_status"]
    )


@router.get("/artifacts/{artifact_code}", response_model=ArtifactResponse)
def get_artifact(
    artifact_code: str,
    execution_id: int,
    version: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get a specific artifact"""
    service = ArtifactService(db)
    artifact = service.get_artifact(artifact_code, execution_id, version)
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_code} not found")
    return artifact


@router.put("/artifacts/{artifact_code}", response_model=ArtifactResponse)
def update_artifact(
    artifact_code: str,
    execution_id: int,
    data: ArtifactUpdate,
    db: Session = Depends(get_db)
):
    """Update an artifact (creates new version)"""
    service = ArtifactService(db)
    try:
        artifact = service.update_artifact(artifact_code, execution_id, data)
        return artifact
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/artifacts/{artifact_code}/status", response_model=ArtifactResponse)
def update_artifact_status(
    artifact_code: str,
    execution_id: int,
    data: ArtifactStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update artifact status"""
    service = ArtifactService(db)
    try:
        artifact = service.update_artifact_status(artifact_code, execution_id, data)
        return artifact
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/artifacts/next-code/{artifact_type}")
def get_next_artifact_code(
    artifact_type: str,
    execution_id: int,
    db: Session = Depends(get_db)
):
    """Get the next artifact code for a type"""
    service = ArtifactService(db)
    code = service.get_next_artifact_code(execution_id, artifact_type)
    return {"next_code": code}


# ============ CONTEXT ENDPOINTS ============

@router.get("/context/{agent_id}", response_model=AgentContext)
def get_agent_context(
    agent_id: str,
    execution_id: int,
    db: Session = Depends(get_db)
):
    """Get context for an agent"""
    service = ArtifactService(db)
    context = service.get_context_for_agent(execution_id, agent_id)
    return context


# ============ GATE ENDPOINTS ============

@router.post("/gates/initialize", response_model=InitializeGatesResponse)
def initialize_gates(data: InitializeGatesRequest, db: Session = Depends(get_db)):
    """Initialize all 6 gates for an execution"""
    service = ArtifactService(db)
    
    # Check if gates already exist
    existing = service.list_gates(data.execution_id)
    if existing:
        raise HTTPException(status_code=400, detail="Gates already initialized for this execution")
    
    gates = service.initialize_gates(data.execution_id)
    return InitializeGatesResponse(
        execution_id=data.execution_id,
        gates_created=len(gates),
        gates=gates
    )


@router.get("/gates", response_model=GateListResponse)
def list_gates(execution_id: int, db: Session = Depends(get_db)):
    """List all gates for an execution"""
    service = ArtifactService(db)
    progress = service.get_gates_progress(execution_id)
    return GateListResponse(
        gates=progress["gates"],
        current_gate=progress["current_gate"],
        progress_percent=progress["progress_percent"]
    )


@router.get("/gates/{gate_number}", response_model=GateResponse)
def get_gate(gate_number: int, execution_id: int, db: Session = Depends(get_db)):
    """Get a specific gate"""
    service = ArtifactService(db)
    gate = service.get_gate(execution_id, gate_number)
    if not gate:
        raise HTTPException(status_code=404, detail=f"Gate {gate_number} not found")
    return gate


@router.post("/gates/{gate_number}/submit", response_model=GateResponse)
def submit_gate(gate_number: int, execution_id: int, db: Session = Depends(get_db)):
    """Submit a gate for user review"""
    service = ArtifactService(db)
    try:
        gate = service.submit_gate_for_review(execution_id, gate_number)
        return gate
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/gates/{gate_number}/approve", response_model=GateResponse)
def approve_gate(gate_number: int, execution_id: int, db: Session = Depends(get_db)):
    """Approve a gate"""
    service = ArtifactService(db)
    try:
        gate = service.approve_gate(execution_id, gate_number)
        return gate
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/gates/{gate_number}/reject", response_model=GateResponse)
def reject_gate(
    gate_number: int,
    execution_id: int,
    data: GateStatusUpdate,
    db: Session = Depends(get_db)
):
    """Reject a gate"""
    if not data.rejection_reason:
        raise HTTPException(status_code=400, detail="rejection_reason is required")
    
    service = ArtifactService(db)
    try:
        gate = service.reject_gate(execution_id, gate_number, data.rejection_reason)
        return gate
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============ QUESTION ENDPOINTS ============

@router.post("/questions", response_model=QuestionResponse)
def create_question(data: QuestionCreate, db: Session = Depends(get_db)):
    """Create a new question between agents"""
    service = ArtifactService(db)
    try:
        question = service.create_question(data)
        return question
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/questions", response_model=QuestionListResponse)
def list_questions(
    execution_id: int,
    from_agent: Optional[str] = None,
    to_agent: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List questions for an execution"""
    service = ArtifactService(db)
    questions = service.list_questions(execution_id, from_agent, to_agent, status)
    pending = sum(1 for q in questions if q.status == "pending")
    answered = sum(1 for q in questions if q.status == "answered")
    return QuestionListResponse(
        questions=questions,
        pending_count=pending,
        answered_count=answered
    )


@router.get("/questions/{question_code}", response_model=QuestionResponse)
def get_question(question_code: str, execution_id: int, db: Session = Depends(get_db)):
    """Get a specific question"""
    service = ArtifactService(db)
    question = service.get_question(question_code, execution_id)
    if not question:
        raise HTTPException(status_code=404, detail=f"Question {question_code} not found")
    return question


@router.post("/questions/{question_code}/answer", response_model=QuestionResponse)
def answer_question(
    question_code: str,
    execution_id: int,
    data: QuestionAnswer,
    db: Session = Depends(get_db)
):
    """Answer a question"""
    service = ArtifactService(db)
    try:
        question = service.answer_question(question_code, execution_id, data)
        return question
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/questions/next-code")
def get_next_question_code(execution_id: int, db: Session = Depends(get_db)):
    """Get the next question code"""
    service = ArtifactService(db)
    code = service.get_next_question_code(execution_id)
    return {"next_code": code}


# ============ GRAPH ENDPOINT ============

@router.get("/graph", response_model=DependencyGraph)
def get_dependency_graph(execution_id: int, db: Session = Depends(get_db)):
    """Get the dependency graph for visualization"""
    service = ArtifactService(db)
    return service.get_dependency_graph(execution_id)
