"""
API routes for V2 Orchestrator
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from agents_v2.orchestrator import OrchestratorV2

router = APIRouter(prefix="/api/v2/orchestrator", tags=["V2 Orchestrator"])


# ============ REQUEST MODELS ============

class InitializeRequest(BaseModel):
    execution_id: int


class RunPhaseRequest(BaseModel):
    execution_id: int
    project_requirements: Optional[str] = None  # Required for Phase 1


class GateActionRequest(BaseModel):
    execution_id: int
    reason: Optional[str] = None  # Required for reject


# ============ ENDPOINTS ============

@router.post("/initialize")
def initialize_execution(request: InitializeRequest, db: Session = Depends(get_db)):
    """Initialize a new V2 execution with 6 validation gates"""
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.initialize()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Initialization failed"))
    
    return result


@router.get("/status/{execution_id}")
def get_execution_status(execution_id: int, db: Session = Depends(get_db)):
    """Get current status of a V2 execution"""
    orchestrator = OrchestratorV2(execution_id, db)
    return orchestrator.get_status()


@router.post("/phase/analysis")
def run_phase_1_analysis(request: RunPhaseRequest, db: Session = Depends(get_db)):
    """
    Run Phase 1: Business Analysis
    Produces BR and UC artifacts, submits Gate 1 for review
    """
    if not request.project_requirements:
        raise HTTPException(status_code=400, detail="project_requirements is required for Phase 1")
    
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.run_phase_1_analysis(request.project_requirements)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Phase 1 failed"))
    
    return result


@router.post("/phase/architecture")
def run_phase_2_architecture(request: RunPhaseRequest, db: Session = Depends(get_db)):
    """
    Run Phase 2: Architecture Design
    Produces ADR and SPEC artifacts, submits Gate 2 for review
    Requires Gate 1 to be approved
    """
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.run_phase_2_architecture()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Phase 2 failed"))
    
    return result


@router.post("/gate/approve")
def approve_gate(request: GateActionRequest, db: Session = Depends(get_db)):
    """Approve the current pending gate"""
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.approve_current_gate()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Approval failed"))
    
    return result


@router.post("/gate/reject")
def reject_gate(request: GateActionRequest, db: Session = Depends(get_db)):
    """Reject the current pending gate"""
    if not request.reason:
        raise HTTPException(status_code=400, detail="reason is required for rejection")
    
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.reject_current_gate(request.reason)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Rejection failed"))
    
    return result
