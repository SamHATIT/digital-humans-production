"""
API routes for V2 Orchestrator with PM coordination and iterations
"""
from fastapi import APIRouter, Depends, HTTPException
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
    project_requirements: Optional[str] = None


class GateActionRequest(BaseModel):
    execution_id: int
    reason: Optional[str] = None


# ============ ENDPOINTS ============

@router.post("/initialize")
def initialize_execution(request: InitializeRequest, db: Session = Depends(get_db)):
    """Initialize a new V2 execution with 6 validation gates"""
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.initialize()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/status/{execution_id}")
def get_execution_status(execution_id: int, db: Session = Depends(get_db)):
    """Get current status of a V2 execution"""
    orchestrator = OrchestratorV2(execution_id, db)
    return orchestrator.get_status()


@router.post("/phase/pm-analysis")
def run_phase_0_pm_analysis(request: RunPhaseRequest, db: Session = Depends(get_db)):
    """
    Phase 0: PM Analysis
    PM analyzes raw requirements, creates structured REQ and PLAN artifacts
    """
    if not request.project_requirements:
        raise HTTPException(status_code=400, detail="project_requirements is required")
    
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.run_phase_0_pm_analysis(request.project_requirements)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/phase/analysis")
def run_phase_1_analysis(request: RunPhaseRequest, db: Session = Depends(get_db)):
    """
    Phase 1: Business Analysis
    BA produces BR and UC artifacts, PM reviews before Gate 1
    """
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.run_phase_1_analysis(request.project_requirements)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/phase/architecture")
def run_phase_2_architecture(request: RunPhaseRequest, db: Session = Depends(get_db)):
    """
    Phase 2: Architecture Design with BA ↔ Architect iterations
    
    Workflow:
    1. Architect reviews approved BR/UC
    2. Architect poses questions if needed → BA answers
    3. Iterate until clear (max 3 iterations)
    4. Architect produces ADR/SPEC
    5. PM reviews → Gate 2
    
    If auto_continue=True in response, call this endpoint again to continue.
    """
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.run_phase_2_architecture()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/phase/architecture/continue")
def continue_phase_2(request: RunPhaseRequest, db: Session = Depends(get_db)):
    """
    Continue Phase 2 after an iteration
    Call this after receiving auto_continue=True from /phase/architecture
    """
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.continue_phase_2()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/gate/approve")
def approve_gate(request: GateActionRequest, db: Session = Depends(get_db)):
    """Approve the current pending gate"""
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.approve_current_gate()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/gate/reject")
def reject_gate(request: GateActionRequest, db: Session = Depends(get_db)):
    """Reject the current pending gate with reason"""
    if not request.reason:
        raise HTTPException(status_code=400, detail="reason is required")
    
    orchestrator = OrchestratorV2(request.execution_id, db)
    result = orchestrator.reject_current_gate(request.reason)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


# ============ WORKFLOW SUMMARY ============
"""
Complete V2 Workflow:

1. POST /initialize
   → Creates 6 validation gates

2. POST /phase/pm-analysis
   → PM analyzes requirements
   → Creates REQ-XXX and PLAN-001 artifacts

3. POST /phase/analysis
   → BA creates BR-XXX and UC-XXX artifacts
   → PM reviews quality
   → Submits Gate 1 if ready

4. POST /gate/approve (execution_id)
   → Approves Gate 1
   → All BR/UC become "approved"

5. POST /phase/architecture
   → Architect reviews BR/UC
   → May return with auto_continue=True if questions asked
   
5a. (If auto_continue) POST /phase/architecture/continue
   → BA answers questions
   → Architect continues
   → Repeat until done

6. POST /gate/approve (execution_id)
   → Approves Gate 2
   → All ADR/SPEC become "approved"

[Continue with Phase 3-6 for Development, QA, Training, Deployment]
"""
