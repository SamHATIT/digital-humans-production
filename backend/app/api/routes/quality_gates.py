"""
Quality Gates API routes.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.quality_gate_service import QualityGateService
from app.schemas.quality_gate import (
    QualityGateCreate,
    QualityGateResponse,
    QualityGateSummary,
    IterationCreate,
    IterationResponse
)

router = APIRouter(prefix="/quality-gates", tags=["Quality Gates"])


@router.post("/", response_model=QualityGateResponse, status_code=status.HTTP_201_CREATED)
def create_quality_gate(
    data: QualityGateCreate,
    db: Session = Depends(get_db)
):
    """Create new quality gate check."""
    service = QualityGateService(db)

    try:
        gate = service.create_quality_gate(data)
        return gate
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating quality gate: {str(e)}"
        )


@router.get("/executions/{execution_id}", response_model=List[QualityGateResponse])
def get_execution_quality_gates(
    execution_id: int,
    db: Session = Depends(get_db)
):
    """Get all quality gates for an execution."""
    service = QualityGateService(db)
    return service.get_by_execution(execution_id)


@router.get("/executions/{execution_id}/agents/{agent_id}", response_model=List[QualityGateResponse])
def get_agent_quality_gates(
    execution_id: int,
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Get quality gates for a specific agent in an execution."""
    service = QualityGateService(db)
    return service.get_by_execution_and_agent(execution_id, agent_id)


@router.get("/executions/{execution_id}/agents/{agent_id}/summary", response_model=QualityGateSummary)
def get_quality_gate_summary(
    execution_id: int,
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Get quality gate summary for an agent."""
    service = QualityGateService(db)
    return service.get_summary(execution_id, agent_id)


@router.post("/executions/{execution_id}/agents/{agent_id}/check-erd", response_model=QualityGateResponse)
def check_erd_present(
    execution_id: int,
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Check if ERD diagram is present."""
    service = QualityGateService(db)
    return service.check_erd_present(execution_id, agent_id)


@router.post("/executions/{execution_id}/agents/{agent_id}/check-flows", response_model=QualityGateResponse)
def check_process_flows(
    execution_id: int,
    agent_id: int,
    minimum: int = 3,
    db: Session = Depends(get_db)
):
    """Check if minimum number of process flows exist."""
    service = QualityGateService(db)
    return service.check_process_flows_count(execution_id, agent_id, minimum)


@router.post("/executions/{execution_id}/agents/{agent_id}/check-hld", response_model=QualityGateResponse)
def check_hld_size(
    execution_id: int,
    agent_id: int,
    minimum_pages: int = 100,
    db: Session = Depends(get_db)
):
    """Check if HLD document meets minimum page count."""
    service = QualityGateService(db)
    return service.check_hld_size(execution_id, agent_id, minimum_pages)


# Iteration endpoints

@router.post("/iterations", response_model=IterationResponse, status_code=status.HTTP_201_CREATED)
def create_iteration(
    data: IterationCreate,
    db: Session = Depends(get_db)
):
    """Create new iteration (retry attempt)."""
    service = QualityGateService(db)

    try:
        iteration = service.create_iteration(data)
        return iteration
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating iteration: {str(e)}"
        )


@router.get("/executions/{execution_id}/agents/{agent_id}/iterations", response_model=List[IterationResponse])
def get_agent_iterations(
    execution_id: int,
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Get all iterations for an agent in an execution."""
    service = QualityGateService(db)
    return service.get_iterations(execution_id, agent_id)


@router.get("/executions/{execution_id}/agents/{agent_id}/should-retry")
def should_retry(
    execution_id: int,
    agent_id: int,
    max_iterations: int = 2,
    db: Session = Depends(get_db)
):
    """Check if agent should retry."""
    service = QualityGateService(db)
    can_retry = service.should_retry(execution_id, agent_id, max_iterations)
    iteration_count = service.get_iteration_count(execution_id, agent_id)

    return {
        "can_retry": can_retry,
        "iteration_count": iteration_count,
        "max_iterations": max_iterations
    }
