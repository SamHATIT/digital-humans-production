"""
P2-Full: Configurable validation gate routes.

Endpoints for:
- Querying/updating project gate configuration
- Submitting validation decisions (approve/reject with annotations)
- Querying pending validation and history
- Resuming execution after gate validation
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import logging

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.execution import Execution, ExecutionStatus
from app.utils.dependencies import get_current_user
from app.services.validation_gate_service import (
    ValidationGateService,
    DEFAULT_VALIDATION_GATES,
    GATE_LABELS,
)
from app.api.routes.orchestrator._helpers import verify_execution_access
from app.workers.arq_config import get_redis_pool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["PM Orchestrator"])


# ── Schemas ──

class GateConfigUpdate(BaseModel):
    """Request body for updating gate configuration."""
    after_expert_specs: Optional[bool] = None
    after_sds_generation: Optional[bool] = None
    after_build_code: Optional[bool] = None


class ValidationSubmission(BaseModel):
    """Request body for submitting a gate validation decision."""
    approved: bool
    annotations: Optional[str] = None


# ── Project gate configuration ──

@router.get("/projects/{project_id}/validation-gates")
def get_project_validation_gates(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the validation gate configuration for a project."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    service = ValidationGateService(db)
    gates = service.get_project_gates(project_id)
    return {
        "project_id": project_id,
        "gates": gates,
        "labels": GATE_LABELS,
        "defaults": DEFAULT_VALIDATION_GATES,
    }


@router.put("/projects/{project_id}/validation-gates")
def update_project_validation_gates(
    project_id: int,
    config: GateConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the validation gate configuration for a project."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    service = ValidationGateService(db)
    # Build update dict from non-None fields
    updates = {k: v for k, v in config.dict().items() if v is not None}
    updated = service.update_project_gates(project_id, updates)
    return {
        "project_id": project_id,
        "gates": updated,
        "message": "Validation gates updated",
    }


# ── Execution gate validation ──

@router.get("/execute/{execution_id}/validation-gate")
def get_pending_validation(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current pending validation gate for an execution."""
    execution = verify_execution_access(execution_id, current_user.id, db)
    service = ValidationGateService(db)
    pending = service.get_pending_validation(execution_id)
    history = service.get_validation_history(execution_id)
    return {
        "execution_id": execution_id,
        "pending": pending,
        "history": history,
    }


@router.post("/execute/{execution_id}/validation-gate/submit")
async def submit_validation_decision(
    execution_id: int,
    submission: ValidationSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a validation decision (approve or reject with annotations).

    If approved, resumes execution automatically.
    If rejected, stores annotations and resumes the previous phase
    so the agent can retry with feedback.
    """
    execution = verify_execution_access(execution_id, current_user.id, db)

    # Ensure execution is in a waiting state
    waiting_statuses = [
        ExecutionStatus.WAITING_EXPERT_VALIDATION,
        ExecutionStatus.WAITING_SDS_VALIDATION,
        ExecutionStatus.WAITING_BUILD_VALIDATION,
    ]
    if execution.status not in waiting_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution is not waiting for validation. Current status: {execution.status.value}",
        )

    service = ValidationGateService(db)
    result = service.submit_validation(
        execution_id=execution_id,
        approved=submission.approved,
        annotations=submission.annotations,
    )

    gate_name = result.get("gate", "")

    # Resume execution
    if submission.approved:
        # Determine resume point based on gate
        resume_map = {
            "after_expert_specs": "phase5_sds",
            "after_sds_generation": "phase6_export",
            "after_build_code": "deploy",
        }
        resume_point = resume_map.get(gate_name)

        execution.status = ExecutionStatus.RUNNING
        db.commit()

        pool = await get_redis_pool()
        job = await pool.enqueue_job(
            "execute_sds_task",
            execution_id=execution.id,
            project_id=execution.project_id,
            selected_agents=execution.selected_agents,
            resume_from=resume_point,
            _queue_name="digital-humans",
        )
        logger.info(
            f"[ValidationGate] Resume job {job.job_id} enqueued for "
            f"execution {execution_id} from {resume_point}"
        )

        return {
            "execution_id": execution_id,
            "status": "resumed",
            "gate": gate_name,
            "approved": True,
            "message": f"Approved. Execution resuming from {resume_point}.",
        }
    else:
        # Rejected — set status back to the previous running state
        # so agent can re-run with annotations as feedback
        rerun_map = {
            "after_expert_specs": "phase4_experts",
            "after_sds_generation": "phase5_sds",
            "after_build_code": "build",
        }
        resume_point = rerun_map.get(gate_name)

        execution.status = ExecutionStatus.RUNNING
        db.commit()

        pool = await get_redis_pool()
        job = await pool.enqueue_job(
            "execute_sds_task",
            execution_id=execution.id,
            project_id=execution.project_id,
            selected_agents=execution.selected_agents,
            resume_from=resume_point,
            annotations=submission.annotations,
            _queue_name="digital-humans",
        )
        logger.info(
            f"[ValidationGate] Rejection rerun job {job.job_id} enqueued for "
            f"execution {execution_id} at {resume_point} with annotations"
        )

        return {
            "execution_id": execution_id,
            "status": "rerun",
            "gate": gate_name,
            "approved": False,
            "annotations": submission.annotations,
            "message": f"Rejected with feedback. Re-running from {resume_point}.",
        }


@router.get("/execute/{execution_id}/validation-history")
def get_validation_history(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full validation history for an execution."""
    execution = verify_execution_access(execution_id, current_user.id, db)
    service = ValidationGateService(db)
    history = service.get_validation_history(execution_id)
    return {
        "execution_id": execution_id,
        "history": history,
    }
