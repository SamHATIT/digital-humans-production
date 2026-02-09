"""
BUILD phase monitoring routes for PM Orchestrator.

P4: Extracted from pm_orchestrator.py — BUILD task/phase monitoring and execution.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.execution import Execution, ExecutionStatus
from app.utils.dependencies import get_current_user, get_current_user_from_token_or_header
from app.workers.arq_config import get_redis_pool
from app.rate_limiter import limiter, RateLimits
from app.api.routes.orchestrator._helpers import verify_execution_access

logger = logging.getLogger(__name__)

router = APIRouter(tags=["PM Orchestrator"])


@router.get("/execute/{execution_id}/detailed-progress")
def get_detailed_execution_progress(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header),
):
    """Get detailed progress with agent tasks breakdown."""
    execution = verify_execution_access(execution_id, current_user.id, db)

    from app.models.agent_deliverable import AgentDeliverable

    deliverables = db.query(AgentDeliverable).filter(
        AgentDeliverable.execution_id == execution_id
    ).all()
    completed_agent_types = {d.deliverable_type for d in deliverables if d.deliverable_type}

    agent_to_type = {
        "ba": "business_analyst_specification",
        "architect": "solution_architect_specification",
        "apex": "apex_developer_code",
        "lwc": "lwc_developer_code",
        "admin": "admin_configuration",
        "qa": "qa_test_plan",
        "devops": "devops_setup",
        "data": "data_migration_plan",
        "trainer": "training_documentation",
    }

    tasks = [
        {"order": 1, "name": "Business Analysis & Requirements", "agent": "ba", "status": "completed" if agent_to_type["ba"] in completed_agent_types else "waiting"},
        {"order": 2, "name": "Solution Architecture Design", "agent": "architect", "status": "completed" if agent_to_type["architect"] in completed_agent_types else "waiting"},
        {"order": 3, "name": "Apex Development (Triggers & Classes)", "agent": "apex", "status": "completed" if agent_to_type["apex"] in completed_agent_types else "waiting"},
        {"order": 4, "name": "LWC Development (Components)", "agent": "lwc", "status": "completed" if agent_to_type["lwc"] in completed_agent_types else "waiting"},
        {"order": 5, "name": "Admin Configuration (Flows & Rules)", "agent": "admin", "status": "completed" if agent_to_type["admin"] in completed_agent_types else "waiting"},
        {"order": 6, "name": "Quality Assurance & Testing", "agent": "qa", "status": "completed" if agent_to_type["qa"] in completed_agent_types else "waiting"},
        {"order": 7, "name": "DevOps Setup & CI/CD", "agent": "devops", "status": "completed" if agent_to_type["devops"] in completed_agent_types else "waiting"},
        {"order": 8, "name": "Data Migration Strategy", "agent": "data", "status": "completed" if agent_to_type["data"] in completed_agent_types else "waiting"},
        {"order": 9, "name": "Training & Documentation", "agent": "trainer", "status": "completed" if agent_to_type["trainer"] in completed_agent_types else "waiting"},
        {"order": 10, "name": "PM Consolidation & SDS Generation", "agent": "pm", "status": "completed" if execution.sds_document_path else "waiting"},
    ]

    current_task_index = len([t for t in tasks if t["status"] == "completed"])
    if current_task_index < len(tasks) and execution.status == ExecutionStatus.RUNNING:
        tasks[current_task_index]["status"] = "running"

    return {
        "execution_id": execution_id,
        "project_id": execution.project_id,
        "status": execution.status.value if hasattr(execution.status, "value") else str(execution.status),
        "tasks": tasks,
        "current_task": next((t for t in tasks if t["status"] == "running"), None),
        "sds_document_path": execution.sds_document_path,
    }


@router.get("/execute/{execution_id}/build-tasks")
def get_build_tasks(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header),
):
    """Get all BUILD phase tasks with their execution status."""
    from app.models.task_execution import TaskExecution, TaskStatus

    execution = verify_execution_access(execution_id, current_user.id, db)

    tasks = db.query(TaskExecution).filter(
        TaskExecution.execution_id == execution_id
    ).order_by(TaskExecution.task_id).all()

    tasks_by_agent = {}
    for task in tasks:
        agent = task.assigned_agent or "unassigned"
        if agent not in tasks_by_agent:
            tasks_by_agent[agent] = []
        tasks_by_agent[agent].append({
            "task_id": task.task_id,
            "task_name": task.task_name,
            "phase_name": task.phase_name,
            "status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "attempt_count": task.attempt_count,
            "last_error": task.last_error,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "git_commit_sha": task.git_commit_sha,
        })

    total = len(tasks)
    completed = len([t for t in tasks if t.status == TaskStatus.COMPLETED or t.status == TaskStatus.PASSED])
    running = len([t for t in tasks if t.status == TaskStatus.RUNNING])
    failed = len([t for t in tasks if t.status == TaskStatus.FAILED])
    pending = len([t for t in tasks if t.status == TaskStatus.PENDING])

    return {
        "execution_id": execution_id,
        "execution_status": execution.status.value if hasattr(execution.status, "value") else str(execution.status),
        "build_phase": {
            "total_tasks": total,
            "completed": completed,
            "running": running,
            "failed": failed,
            "pending": pending,
            "progress_percent": int((completed / total) * 100) if total > 0 else 0,
        },
        "tasks_by_agent": tasks_by_agent,
        "all_tasks": [
            {
                "task_id": t.task_id,
                "task_name": t.task_name,
                "phase_name": t.phase_name,
                "assigned_agent": t.assigned_agent,
                "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                "attempt_count": t.attempt_count,
                "last_error": t.last_error,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
    }


@router.get("/execute/{execution_id}/build-phases")
def get_build_phases(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header),
):
    """Get BUILD v2 phase execution status."""
    from sqlalchemy import text

    execution = verify_execution_access(execution_id, current_user.id, db)

    result = db.execute(
        text("""
            SELECT
                phase_number, phase_name, status, agent_id,
                total_batches, completed_batches,
                elena_verdict, elena_feedback, elena_review_count,
                deploy_method, branch_name, pr_url, pr_number, merge_sha,
                started_at, completed_at, last_error, attempt_count
            FROM build_phase_executions
            WHERE execution_id = :exec_id
            ORDER BY phase_number
        """),
        {"exec_id": execution_id},
    )

    phases = []
    current_phase = None
    for row in result:
        phase_data = {
            "phase_number": row.phase_number,
            "phase_name": row.phase_name,
            "status": row.status,
            "agent_id": row.agent_id,
            "total_batches": row.total_batches or 0,
            "completed_batches": row.completed_batches or 0,
            "elena_verdict": row.elena_verdict,
            "elena_feedback": row.elena_feedback,
            "elena_review_count": row.elena_review_count or 0,
            "deploy_method": row.deploy_method,
            "branch_name": row.branch_name,
            "pr_url": row.pr_url,
            "pr_number": row.pr_number,
            "merge_sha": row.merge_sha,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "last_error": row.last_error,
            "attempt_count": row.attempt_count or 0,
        }
        phases.append(phase_data)
        if row.status not in ("completed", "failed") and current_phase is None:
            current_phase = row.phase_number

    return {
        "execution_id": execution_id,
        "execution_status": execution.status.value if hasattr(execution.status, "value") else str(execution.status),
        "phases": phases,
        "current_phase": current_phase,
        "total_phases": 6,
        "completed_phases": len([p for p in phases if p["status"] == "completed"]),
    }


@router.post("/projects/{project_id}/start-build")
@limiter.limit(RateLimits.EXECUTE_BUILD)
async def start_build_phase(
    request: Request,
    response: Response,
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header),
):
    """Start the BUILD phase for a project after SDS approval."""
    from app.services.pm_orchestrator_service_v2 import BuildPhaseService

    service = BuildPhaseService(db)
    result = service.prepare_build_phase(project_id, current_user.id)

    if not result.get("success"):
        raise HTTPException(status_code=result.get("code", 400), detail=result.get("error"))

    pool = await get_redis_pool()
    job = await pool.enqueue_job(
        "execute_build_task",
        project_id=project_id,
        execution_id=result["execution_id"],
        _queue_name="digital-humans",
    )
    logger.info(f"[ARQ] Job {job.job_id} enqueued for BUILD {result['execution_id']}")

    return {
        "message": f"BUILD phase started with {result['tasks_created']} tasks",
        "execution_id": result["execution_id"],
        "project_id": project_id,
        "tasks_created": result["tasks_created"],
    }
