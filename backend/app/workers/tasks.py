"""ARQ task definitions for long-running executions."""
import asyncio
import logging
from datetime import datetime, timezone
from app.database import SessionLocal
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

logger = logging.getLogger("arq.worker")

def _clore_en_echec(db, execution_id: int, motif: str) -> None:
    """Marque une execution FAILED avec un motif lisible, statut ET etat.

    VAGUE 1 / FILE C — CAL-02. Sert les deux sorties anormales d'un job : une
    exception metier, et une **annulation** (`job_timeout` d'ARQ, arret du
    worker). L'ancien code n'ecrivait que `status` et ne voyait pas
    l'annulation ; l'execution restait RUNNING jusqu'au redemarrage suivant.

    Une execution deja terminee n'est pas reecrite : un job annule apres coup
    ne doit pas transformer un succes en echec.
    """
    from app.models.execution import Execution, ExecutionStatus
    from app.services.execution_state import ExecutionStateMachine

    try:
        execution = db.query(Execution).get(execution_id)
        if execution is None:
            return
        if execution.status in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        ):
            return
        try:
            ExecutionStateMachine(db, execution_id).transition_to(
                "failed", metadata={"raison": motif[:200]}
            )
        except Exception as e:
            logger.warning(
                f"[ARQ] Transition vers 'failed' refusee pour l'execution "
                f"{execution_id} ({e}) — statut et etat poses directement"
            )
            execution.status = ExecutionStatus.FAILED
            execution.execution_state = "failed"
        execution.logs = (execution.logs or "") + "\n" + motif
        execution.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        logger.error(f"[ARQ] Impossible de clore l'execution {execution_id} : {e}")
        try:
            db.rollback()
        except Exception:
            pass


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
        # PROD-04 : `execute_workflow` rend `{"success": False, "error": ...}`
        # sur un echec metier. L'ancien message « completed successfully » etait
        # ecrit dans les deux cas — un echec journalise comme un succes.
        if isinstance(result, dict) and result.get("success") is False:
            logger.error(
                f"[ARQ] Execution {execution_id} terminee en echec : "
                f"{result.get('error')}"
            )
        else:
            logger.info(f"[ARQ] Execution {execution_id} completed successfully")
        return result
    except asyncio.CancelledError:
        # CAL-02 : `job_timeout` d'ARQ et l'arret d'un worker annulent la tache.
        # `CancelledError` n'herite pas d'`Exception` depuis Python 3.8 : le
        # `except Exception` ci-dessous ne la voyait pas, et l'execution restait
        # RUNNING sans erreur visible jusqu'au redemarrage suivant.
        logger.error(f"[ARQ] Execution {execution_id} annulee (timeout ou arret du worker)")
        _clore_en_echec(
            db,
            execution_id,
            "[Job annule] Le job a ete interrompu (delai d'execution depasse ou "
            "arret du worker). L'execution est close en echec ; reprenez-la avec "
            "/resume, le travail deja valide est conserve.",
        )
        raise
    except Exception as e:
        logger.error(f"[ARQ] Execution {execution_id} failed: {e}")
        _clore_en_echec(db, execution_id, str(e))
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
    except asyncio.CancelledError:
        logger.error(f"[ARQ] Architecture resume {execution_id} annule (timeout ou arret du worker)")
        _clore_en_echec(
            db,
            execution_id,
            "[Job annule] La reprise apres validation d'architecture a ete "
            "interrompue (delai depasse ou arret du worker).",
        )
        raise
    except Exception as e:
        logger.error(f"[ARQ] Architecture resume {execution_id} failed: {e}")
        _clore_en_echec(db, execution_id, str(e))
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
    except asyncio.CancelledError:
        logger.error(f"[ARQ] BUILD v2 {execution_id} annule (timeout ou arret du worker)")
        _clore_en_echec(
            db,
            execution_id,
            "[Job annule] Le BUILD a ete interrompu (delai depasse ou arret du "
            "worker). Les taches deja terminees sont conservees.",
        )
        raise
    except Exception as e:
        logger.error(f"[ARQ] BUILD v2 error: {e}")
        _clore_en_echec(db, execution_id, str(e))
        raise
    finally:
        db.close()
