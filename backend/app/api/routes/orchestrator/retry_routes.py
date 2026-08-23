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
from app.utils.feature_access import ensure_feature, require_feature

logger = logging.getLogger(__name__)

router = APIRouter(tags=["PM Orchestrator"])


@router.post("/execute/{execution_id}/retry", response_model=ExecutionStartResponse, status_code=status.HTTP_202_ACCEPTED)
@require_feature("sds_document")
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

    # LOT-A bis : les lignes TaskExecution sont des taches BUILD — elles ne sont
    # creees que par BuildPhaseService.prepare_build_phase. Le retry les remet a
    # PENDING et efface leurs erreurs : c'est une mutation d'etat BUILD, donc
    # reservee aux paliers qui ont le BUILD. Le gate est conditionnel pour ne pas
    # priver un compte Pro du retry SDS, qui lui est du (cas d'une retrogradation
    # Team -> Pro laissant des taches BUILD derriere elle).
    if failed_tasks:
        ensure_feature(current_user, "build_phase")

    agent_status = execution.agent_execution_status or {}
    resume_from = "phase1"

    # VAGUE 3 / §3.2 — cette boucle construisait `f"phase_{agent suivant}"`,
    # soit `phase_ba`, `phase_architect`, `phase_data`, `phase_trainer`,
    # `phase_qa`, `phase_devops` : six valeurs qu'`execute_workflow` ne
    # reconnaissait pas et qui rejouaient toutes depuis la phase 2. La route
    # continue de raisonner en agents — c'est ce qu'elle observe — mais elle
    # **traduit avant d'enfiler**, pour que le job porte un point de reprise
    # canonique.
    phase_order = ["pm", "ba", "architect", "data", "trainer", "qa", "devops"]
    for agent_id in reversed(phase_order):
        if agent_id in agent_status:
            status_info = agent_status[agent_id]
            if status_info.get("state") == "completed":
                idx = phase_order.index(agent_id)
                if idx < len(phase_order) - 1:
                    resume_from = f"phase_{phase_order[idx + 1]}"
                break

    # Import local, comme le reste du fichier : `pm_orchestrator_service_v2`
    # tire python-docx et chromadb. Le monter au niveau module ferait dependre
    # le demarrage de l'API de ces deux paquets, alors qu'aujourd'hui `app.main`
    # s'importe sans eux. Un test verrouille cette propriete.
    from app.services.pm_orchestrator_service_v2 import resolve_resume_point

    resume_from = resolve_resume_point(resume_from)

    # VAGUE 2 / LOT 1a — `resume_from="build_tasks"` etait une valeur morte.
    # Elle etait posee ici puis passee a `execute_sds_task`, donc a
    # `execute_workflow`, qui ne connait que phase1/phase1_pm/phase2/phase4/
    # phase5 : elle tombait dans la branche generique « saute la phase 1 » et
    # **rejouait le SDS a partir de la phase 2**. Un retry de taches BUILD
    # repayait ainsi toute la chaine SDS au lieu de reprendre le BUILD.
    #
    # Le BUILD a deja son point d'entree, utilise par /resume-build : le job ARQ
    # `execute_build_task`, qui relit les TaskExecution et reprend celles qui ne
    # sont pas COMPLETED. La reprise BUILD ne se porte donc pas par un
    # `resume_from` mais par l'etat des taches, remises a PENDING juste avant.
    is_build_retry = bool(failed_tasks)

    # P7: Atomic transaction for retry reset — all task resets + status update together
    try:
        if failed_tasks:
            for task in failed_tasks:
                task.status = TaskStatus.PENDING
                task.attempt_count = 0
                task.last_error = None
                task.error_log = None

        execution.status = ExecutionStatus.RUNNING
        db.commit()
    except Exception:
        db.rollback()
        raise

    pool = await get_redis_pool()

    if is_build_retry:
        job = await pool.enqueue_job(
            "execute_build_task",
            project_id=execution.project_id,
            execution_id=execution.id,
            _queue_name="digital-humans",
        )
        logger.info(
            f"[ARQ] Job {job.job_id} enqueued for BUILD retry {execution.id} — "
            f"{len(failed_tasks)} failed tasks reset to PENDING"
        )
        return ExecutionStartResponse(
            execution_id=execution.id,
            status="retrying",
            message=(
                f"BUILD retrying. {len(failed_tasks)} failed tasks reset."
            ),
        )

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
    """Get information about retry options for a failed execution.

    LOT-A bis — decision : route de LECTURE, volontairement non gardee par palier.
    La propriete est deja verifiee par verify_execution_access, et la reponse
    n'expose rien de plus que les endpoints de progression voisins
    (/progress, /build-tasks, /build-phases), eux aussi non gardes. La garder
    ouverte permet a l'UI d'afficher l'etat puis l'invite a monter d'offre ;
    la fermer seule serait incoherent sans fermer aussi les trois autres.
    """
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
@require_feature("build_phase")
def pause_build(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pause the BUILD phase execution."""
    from app.services.pm_orchestrator_service_v2 import BuildPhaseService

    # LOT-A bis : le commentaire precedent affirmait que BuildPhaseService
    # verifiait la propriete. C'est faux — pause_build/resume_build filtrent sur
    # Execution.id seul, sans user_id. La verification est donc faite ici.
    verify_execution_access(execution_id, current_user.id, db)

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
@require_feature("build_phase")
async def resume_build(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume a paused BUILD phase execution."""
    from app.services.pm_orchestrator_service_v2 import BuildPhaseService

    # LOT-A bis : idem pause_build — la propriete n'est pas verifiee en aval.
    verify_execution_access(execution_id, current_user.id, db)

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
