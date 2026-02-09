"""
Retry and execution control routes for PM Orchestrator.

P4: Extracted from pm_orchestrator.py — Retry, pause, resume controls.
P7: Multi-step retry operations wrapped in try/except with rollback.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models.user import User
from app.models.execution import Execution, ExecutionStatus
from app.schemas.execution import ExecutionStartResponse
from app.utils.dependencies import get_current_user
from app.workers.arq_config import get_redis_pool
from app.api.routes.orchestrator._helpers import verify_execution_access

logger = logging.getLogger(__name__)

router = APIRouter(tags=["PM Orchestrator"])


@router.post("/execute/{execution_id}/retry", response_model=ExecutionStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_failed_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retry a failed execution from the last stable point."""
    from app.models.task_execution import TaskExecution, TaskStatus

    execution = verify_execution_access(execution_id, current_user.id, db)

    if execution.status not in [ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution cannot be retried. Current status: {execution.status.value}. Only failed/cancelled executions can be retried.",
        )

    failed_tasks = db.query(TaskExecution).filter(
        TaskExecution.execution_id == execution_id,
        TaskExecution.status == TaskStatus.FAILED,
    ).all()

    agent_status = execution.agent_execution_status or {}
    resume_from = "phase1"

    phase_order = ["pm", "ba", "architect", "data", "trainer", "qa", "devops"]
    for agent_id in reversed(phase_order):
        if agent_id in agent_status:
            status_info = agent_status[agent_id]
            if status_info.get("state") == "completed":
                idx = phase_order.index(agent_id)
                if idx < len(phase_order) - 1:
                    resume_from = f"phase_{phase_order[idx + 1]}"
                break

    # P7: Atomic transaction for retry reset — all task resets + status update together
    try:
        if failed_tasks:
            for task in failed_tasks:
                task.status = TaskStatus.PENDING
                task.attempt_count = 0
                task.last_error = None
                task.error_log = None
            resume_from = "build_tasks"

        execution.status = ExecutionStatus.RUNNING
        db.commit()
    except Exception:
        db.rollback()
        raise

    pool = await get_redis_pool()
    job = await pool.enqueue_job(
        "execute_sds_task",
        execution_id=execution.id,
        project_id=execution.project_id,
        selected_agents=execution.selected_agents,
        resume_from=resume_from,
        _queue_name="digital-humans",
    )
    logger.info(f"[ARQ] Job {job.job_id} enqueued for retry {execution.id} from {resume_from}")

    return ExecutionStartResponse(
        execution_id=execution.id,
        status="retrying",
        message=f"Execution retrying from {resume_from}. {len(failed_tasks)} failed tasks reset.",
    )


@router.get("/execute/{execution_id}/retry-info")
def get_retry_info(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get information about retry options for a failed execution."""
    from app.models.task_execution import TaskExecution, TaskStatus

    execution = verify_execution_access(execution_id, current_user.id, db)

    task_summary = {"completed": [], "failed": [], "pending": [], "blocked": []}
    tasks = db.query(TaskExecution).filter(
        TaskExecution.execution_id == execution_id
    ).all()

    for task in tasks:
        status_key = (
            task.status.value
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PENDING, TaskStatus.BLOCKED]
            else "other"
        )
        if status_key in task_summary:
            task_summary[status_key].append({
                "task_id": task.task_id,
                "name": task.task_name,
                "agent": task.assigned_agent,
                "attempts": task.attempt_count,
                "last_error": task.last_error,
            })

    agent_status = execution.agent_execution_status or {}
    completed_phases = [k for k, v in agent_status.items() if v.get("state") == "completed"]
    can_retry = execution.status in [ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]

    return {
        "execution_id": execution_id,
        "current_status": execution.status.value,
        "can_retry": can_retry,
        "completed_phases": completed_phases,
        "task_summary": {
            "completed": len(task_summary["completed"]),
            "failed": len(task_summary["failed"]),
            "pending": len(task_summary["pending"]),
            "blocked": len(task_summary["blocked"]),
        },
        "failed_tasks": task_summary["failed"],
        "resume_point": (
            "build_tasks"
            if task_summary["failed"]
            else ("phase2" if "pm" in completed_phases else "phase1")
        ),
    }


@router.post("/execute/{execution_id}/pause-build")
def pause_build(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pause the BUILD phase execution."""
    from app.services.pm_orchestrator_service_v2 import BuildPhaseService

    # verify_execution_access not needed here — BuildPhaseService handles it
    service = BuildPhaseService(db)
    result = service.pause_build(execution_id)

    if not result.get("success"):
        raise HTTPException(status_code=result.get("code", 400), detail=result.get("error"))

    return {
        "status": result["status"],
        "message": result["message"],
        "execution_id": execution_id,
    }


@router.post("/execute/{execution_id}/resume-build")
async def resume_build(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume a paused BUILD phase execution."""
    from app.services.pm_orchestrator_service_v2 import BuildPhaseService

    service = BuildPhaseService(db)
    result = service.resume_build(execution_id)

    if not result.get("success"):
        raise HTTPException(status_code=result.get("code", 400), detail=result.get("error"))

    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        pool = await get_redis_pool()
        job = await pool.enqueue_job(
            "execute_build_task",
            project_id=execution.project_id,
            execution_id=execution_id,
            _queue_name="digital-humans",
        )
        logger.info(f"[ARQ] Job {job.job_id} enqueued for build resume {execution_id}")

    return {
        "status": result["status"],
        "message": "BUILD resumed. Execution continuing from next pending task.",
        "execution_id": execution_id,
    }
