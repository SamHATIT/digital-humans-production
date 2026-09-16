"""ARQ task definitions for long-running executions."""
import logging
from app.database import SessionLocal
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

logger = logging.getLogger("arq.worker")

#: Statuts qui font d'un job un fantome : l'execution est deja close, le job
#: qui arrive est un reliquat (worker redemarre, double enfilage).
STATUTS_TERMINAUX = ("completed", "failed", "cancelled")


def _est_un_fantome(execution, resume_from) -> bool:
    """Ce job est-il un reliquat, ou une reprise demandee ?

    VAGUE 1 / FILE C — CAL-05. La garde d'origine refusait toute execution
    COMPLETED, FAILED ou CANCELLED. C'est juste pour un job orphelin ; c'est
    faux pour une reprise explicite : `/resume` et `/retry` posent un
    `resume_from`, et le job etait quand meme saute si le statut n'avait pas
    ete remis a RUNNING entre-temps (course avec le nettoyage du demarrage,
    reprise enfilee a la main, retry d'une execution reconciliee).

    `resume_from` est precisement le drapeau qui distingue les deux cas.

    Une execution CANCELLED reste refusee meme avec `resume_from` : une
    annulation est une decision, on ne la contourne pas par un parametre.
    """
    from app.models.execution import ExecutionStatus

    statut = execution.status
    valeur = statut.value if hasattr(statut, "value") else str(statut)
    if valeur not in STATUTS_TERMINAUX:
        return False
    if statut == ExecutionStatus.CANCELLED:
        return True
    if resume_from:
        logger.info(
            f"[ARQ] Execution {execution.id} est {valeur} mais le job porte "
            f"resume_from={resume_from!r} : reprise explicite, ce n'est pas un "
            f"job fantome (CAL-05)."
        )
        return False
    return True


async def execute_sds_task(ctx, execution_id: int, project_id: int,
                           selected_agents: list = None,
                           include_as_is: bool = False,
                           sfdx_metadata: dict = None,
                           resume_from: str = None):
    """ARQ task: Execute SDS workflow in isolated worker process."""
    db = SessionLocal()
    try:
        # BUG-008: Ghost job guard — skip if execution already completed/failed
        from app.models.execution import Execution, ExecutionStatus
        execution = db.query(Execution).get(execution_id)
        if execution and _est_un_fantome(execution, resume_from):
            logger.warning(f"[ARQ] Ghost job detected for exec {execution_id} (status={execution.status.value}), skipping")
            return {"skipped": True, "reason": "ghost_job", "execution_id": execution_id}

        service = PMOrchestratorServiceV2(db)
        result = await service.execute_workflow(
            execution_id=execution_id,
            project_id=project_id,
            selected_agents=selected_agents,
            include_as_is=include_as_is,
            sfdx_metadata=sfdx_metadata,
            resume_from=resume_from,
        )
        logger.info(f"[ARQ] Execution {execution_id} completed successfully")
        return result
    except Exception as e:
        logger.error(f"[ARQ] Execution {execution_id} failed: {e}")
        # Ensure execution is marked FAILED in DB
        try:
            from app.models.execution import Execution, ExecutionStatus
            execution = db.query(Execution).get(execution_id)
            if execution and execution.status not in (
                ExecutionStatus.COMPLETED, ExecutionStatus.FAILED
            ):
                execution.status = ExecutionStatus.FAILED
                execution.logs = str(e)
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


async def resume_architecture_task(ctx, execution_id: int, project_id: int, action: str):
    """ARQ task: Resume from architecture validation pause."""
    db = SessionLocal()
    try:
        # BUG-008: Ghost job guard
        from app.models.execution import Execution, ExecutionStatus
        execution = db.query(Execution).get(execution_id)
        if execution and _est_un_fantome(execution, None):
            logger.warning(f"[ARQ] Ghost resume detected for exec {execution_id} (status={execution.status.value}), skipping")
            return {"skipped": True, "reason": "ghost_job", "execution_id": execution_id}

        service = PMOrchestratorServiceV2(db)
        result = await service.resume_from_architecture_validation(
            execution_id=execution_id,
            project_id=project_id,
            action=action,
        )
        logger.info(f"[ARQ] Architecture resume {execution_id} completed: action={action}")
        return result
    except Exception as e:
        logger.error(f"[ARQ] Architecture resume {execution_id} failed: {e}")
        try:
            from app.models.execution import Execution, ExecutionStatus
            execution = db.query(Execution).get(execution_id)
            if execution and execution.status not in (
                ExecutionStatus.COMPLETED, ExecutionStatus.FAILED
            ):
                execution.status = ExecutionStatus.FAILED
                execution.logs = str(e)
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


async def execute_build_task(ctx, project_id: int, execution_id: int):
    """ARQ task: Execute BUILD v2 with PhasedBuildExecutor."""
    from app.services.phased_build_executor import PhasedBuildExecutor
    from app.services.execution_state import ExecutionStateMachine, InvalidTransitionError
    from app.models.task_execution import TaskExecution

    db = SessionLocal()
    try:
        logger.info(f"[ARQ] BUILD v2 starting for project {project_id}, execution {execution_id}")

        # Transition to build_running
        sm = ExecutionStateMachine(db, execution_id)
        try:
            sm.transition_to("build_running")
            db.commit()
        except InvalidTransitionError as e:
            logger.warning(f"[ARQ] BUILD state transition skipped: {e}")

        tasks = db.query(TaskExecution).filter(
            TaskExecution.execution_id == execution_id
        ).all()

        wbs_tasks = []
        for task in tasks:
            wbs_tasks.append({
                "task_id": task.task_id,
                "task_name": task.task_name,
                "name": task.task_name,
                "target_object": task.task_name,
                "task_type": task.task_type,
                "assigned_agent": task.assigned_agent,
                "description": task.description or task.task_name,
                "phase_name": task.phase_name,
            })

        logger.info(f"[ARQ] BUILD v2 found {len(wbs_tasks)} tasks")

        executor = PhasedBuildExecutor(project_id, execution_id, db)
        # Initialize jordan_service (git/sfdx) before execute_build — without
        # this call, executor.jordan_service stays None and Phase 1 crashes on
        # create_phase_branch with NoneType. Symmetric close() in finally.
        await executor.initialize()
        try:
            result = await executor.execute_build(wbs_tasks)
        finally:
            await executor.close()

        # Transition to build_complete or failed
        try:
            if result.get("success"):
                sm.transition_to("build_complete")
            else:
                sm.transition_to("failed")
            db.commit()
        except InvalidTransitionError as e:
            logger.warning(f"[ARQ] BUILD final state transition skipped: {e}")

        logger.info(f"[ARQ] BUILD v2 completed: {result}")
        return result
    except Exception as e:
        logger.error(f"[ARQ] BUILD v2 error: {e}")
        # Mark as failed in state machine
        try:
            sm = ExecutionStateMachine(db, execution_id)
            sm.transition_to("failed")
            db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()
