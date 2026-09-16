"""
P2-Full: Configurable validation gate routes.

Endpoints for:
- Querying/updating project gate configuration
- Submitting validation decisions (approve/reject with annotations)
- Querying pending validation and history
- Resuming execution after gate validation
"""
from fastapi import APIRouter, Depends, HTTPException, status
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
from app.workers.enqueue import enfiler_execution, file_de_reprise

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
    verify_execution_access(execution_id, current_user.id, db)
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
    from app.services.pm_orchestrator_service_v2 import (
        EXPORT_RESUME_POINTS,
        resolve_export_action,
    )

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

    # VAGUE 1 / FILE C — PROD-06, deuxieme point : la porte n'est consommee
    # qu'une fois la reprise jugee possible.
    #
    # Avant, `submit_validation` etait appele ici : il commitait la decision et
    # effacait `pending_validation`, et la faisabilite n'etait examinee
    # qu'ensuite. Une reprise impossible rendait alors un 409 sur une porte
    # deja consommee : la decision du client etait perdue et la porte ne
    # pouvait plus etre soumise. On lit donc le nom de la porte sur
    # `pending_validation`, on verifie, puis on enregistre.
    gate_name = (service.get_pending_validation(execution_id) or {}).get("gate", "")

    # VAGUE 3 / §3.3 et §3.4 — les six valeurs emises par ces deux tables
    # etaient toutes mortes. Elles tombaient dans la branche generique
    # d'`execute_workflow` et **rejouaient le SDS depuis la phase 2**. La plus
    # couteuse est dans le chemin nominal du client : approuver
    # `after_build_code` emettait `deploy` et relancait toute la chaine SDS —
    # une validation humaine relancait le travail qu'elle venait de valider.
    #
    # Les valeurs restent ecrites ici, dans le vocabulaire des portes ; c'est
    # l'aiguillage qui les traduit vers l'une des trois chaines reelles.
    if submission.approved:
        resume_map = {
            "after_expert_specs": "phase5_sds",
            "after_sds_generation": "phase6_export",
            "after_build_code": "deploy",
        }
        resume_point = resume_map.get(gate_name)
        annotations = None
        statut_reponse = "resumed"
    else:
        # Rejected — set status back to the previous running state
        # so agent can re-run with annotations as feedback
        rerun_map = {
            "after_expert_specs": "phase4_experts",
            "after_sds_generation": "phase5_sds",
            "after_build_code": "build",
        }
        resume_point = rerun_map.get(gate_name)
        annotations = submission.annotations
        statut_reponse = "rerun"

    if not resume_point:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown validation gate: {gate_name!r}",
        )

    # PROD-06 — refus AVANT consommation : `resolve_export_action` est la seule
    # decision de reprise qui peut conclure « impossible ». On la joue a blanc
    # ici, sur l'etat courant ; l'aiguillage la rejouera pour agir.
    if resume_point in EXPORT_RESUME_POINTS:
        decision = resolve_export_action(
            state=execution.execution_state,
            sds_document_path=execution.sds_document_path,
        )
        if decision["action"] == "resume_upstream":
            logger.warning(
                f"[ValidationGate] Porte {gate_name!r} non consommee pour "
                f"l'execution {execution_id} : {decision['reason']}"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=decision["reason"],
            )

    # La reprise est possible : la decision peut etre enregistree.
    result = service.submit_validation(
        execution_id=execution_id,
        approved=submission.approved,
        annotations=submission.annotations,
    )
    assert result.get("gate", gate_name) == gate_name

    return await _relancer_apres_porte(
        db=db,
        execution=execution,
        execution_id=execution_id,
        gate_name=gate_name,
        resume_point=resume_point,
        approved=submission.approved,
        annotations=annotations,
        statut_reponse=statut_reponse,
    )


def _tracer_annotations_non_relues(gate_name: str, annotations) -> None:
    """VAGUE 3 / §6 — dire que les annotations ne sont relues par personne.

    Elles sont conservees : `ValidationGateService.submit_validation` les ecrit
    dans `execution.validation_history`. Mais aucun agent ne les relit. Le taire
    laisserait croire — au client comme au prochain developpeur — qu'un rejet
    commente influence la relance. Il ne l'influence pas encore.
    """
    if not annotations:
        return
    logger.warning(
        "[ValidationGate] Porte %r rejetee avec annotations : conservees dans "
        "execution.validation_history, mais AUCUN agent ne les relit "
        "aujourd'hui. La relance repart sans ce retour. Voir SPEC_VAGUE3 §6.",
        gate_name,
    )


def _annotations_dans_la_reponse(approved: bool, annotations) -> dict:
    """Ce que la reponse dit des annotations, sans rien promettre de faux."""
    if approved:
        return {}
    return {
        "annotations": annotations,
        # Explicite : le client voit que son commentaire est enregistre et
        # qu'il n'est pas encore reinjecte dans la relance.
        "annotations_applied": False,
    }


async def _relancer_apres_porte(
    *,
    db: Session,
    execution: Execution,
    execution_id: int,
    gate_name: str,
    resume_point: str,
    approved: bool,
    annotations,
    statut_reponse: str,
):
    """Aiguille une valeur de porte vers la bonne chaine.

    VAGUE 3 / §3.3 et §3.4. Trois destinations, pas une :

    - **BUILD** (`deploy`, `build`) — job ARQ `execute_build_task`. La reprise
      ne s'exprime pas par `resume_from` mais par l'etat des `TaskExecution`,
      remises a PENDING avant l'enfilage. Meme mecanique que le LOT 1a de la
      vague 2 (`57ee795`), qui a servi de modele.
    - **Export** (`phase6_export`) — aucun agent relance. La decision se lit sur
      l'etat de la machine et l'extension de `sds_document_path`.
    - **SDS** (`phase5_sds`, `phase4_experts`) — job `execute_sds_task`, avec un
      point de reprise canonique (§3.2).
    """
    from app.models.task_execution import TaskExecution, TaskStatus
    from app.services.pm_orchestrator_service_v2 import (
        BUILD_RESUME_POINTS,
        EXPORT_RESUME_POINTS,
        resolve_export_action,
        resolve_resume_point,
    )

    pool = await get_redis_pool()

    # ── §3.4 — chaine BUILD ────────────────────────────────────────────────
    if resume_point in BUILD_RESUME_POINTS:
        taches = db.query(TaskExecution).filter(
            TaskExecution.execution_id == execution_id,
            TaskExecution.status.in_([TaskStatus.FAILED, TaskStatus.BLOCKED]),
        ).all()
        try:
            for tache in taches:
                tache.status = TaskStatus.PENDING
                tache.attempt_count = 0
                tache.last_error = None
                tache.error_log = None
            execution.status = ExecutionStatus.RUNNING
            db.commit()
        except Exception:
            db.rollback()
            raise

        _tracer_annotations_non_relues(gate_name, annotations)

        # VAGUE 1 / FILE C — la file etait ecrite en dur ici, alors que la
        # vague 0 (AS-02) avait ramene les sept autres sites d'enfilage a
        # `arq_config.ARQ_QUEUE_NAME` : une porte validee pendant un test
        # enfilait sur la file de production. Job identifie (PROD-04) et file
        # du lancement (CAL-07).
        await enfiler_execution(
            pool,
            db,
            execution,
            "execute_build_task",
            file=file_de_reprise(execution),
            project_id=execution.project_id,
            execution_id=execution.id,
        )
        logger.info(
            f"[ValidationGate] BUILD relance apres la porte "
            f"{gate_name} — {len(taches)} tasks reset to PENDING"
        )
        return {
            "execution_id": execution_id,
            "status": statut_reponse,
            "gate": gate_name,
            "approved": approved,
            **_annotations_dans_la_reponse(approved, annotations),
            "message": (
                f"{'Approved' if approved else 'Rejected with feedback'}. "
                f"BUILD resuming — {len(taches)} tasks reset."
            ),
        }

    # ── §3.3 — export, aucun agent relance ─────────────────────────────────
    if resume_point in EXPORT_RESUME_POINTS:
        decision = resolve_export_action(
            state=execution.execution_state,
            sds_document_path=execution.sds_document_path,
        )
        logger.info(
            f"[ValidationGate] Gate {gate_name} -> export : "
            f"{decision['action']} — {decision['reason']}"
        )

        if decision["action"] == "serve":
            return {
                "execution_id": execution_id,
                "status": "completed",
                "gate": gate_name,
                "approved": approved,
                "document_path": decision["path"],
                "message": f"Approved. {decision['reason']}",
            }

        if decision["action"] == "resume_upstream":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=decision["reason"],
            )

        # regenerate_export et resume_workflow relancent tous deux le workflow :
        # le premier a `phase5` aussi, l'ecriture etant idempotente et la
        # regeneration de l'export en dependant.
        execution.status = ExecutionStatus.RUNNING
        db.commit()
        await enfiler_execution(
            pool,
            db,
            execution,
            "execute_sds_task",
            file=file_de_reprise(execution),
            execution_id=execution.id,
            project_id=execution.project_id,
            selected_agents=execution.selected_agents,
            resume_from="phase5",
        )
        logger.info(
            f"[ValidationGate] Regeneration de l'export enfilee pour "
            f"l'execution {execution_id}"
        )
        return {
            "execution_id": execution_id,
            "status": statut_reponse,
            "gate": gate_name,
            "approved": approved,
            "message": f"{decision['reason']}",
        }

    # ── §3.2 — chaine SDS ──────────────────────────────────────────────────
    point_canonique = resolve_resume_point(resume_point)

    execution.status = ExecutionStatus.RUNNING
    db.commit()

    # VAGUE 3 / §6 — le kwarg `annotations` est retire.
    #
    # Il etait passe a `execute_sds_task`, qui n'a pas ce parametre
    # (`workers/tasks.py:9`). ARQ serialise les kwargs sans les valider :
    # l'enfilage reussissait, le job mourait en `TypeError` **dans le worker**,
    # et cote client la porte etait rejetee avec un 200 sans que rien ne
    # redemarre. Rejeter une porte avec commentaires ne relancait donc rien.
    #
    # Il n'est pas rebranche plus loin, et c'est un choix (regle 2, verifier les
    # consommateurs) : **personne ne lit ces annotations**. Aucun agent, aucun
    # prompt ; `execute_workflow` n'a pas de parametre `annotations` ;
    # `execution.validation_history` est ecrit et jamais relu ailleurs. Le
    # cabler jusqu'a `execute_workflow` creerait un parametre inerte de plus.
    # Les faire relire par les agents est de la fonctionnalite, pas un
    # correctif — voir le rapport de vague 3.
    _tracer_annotations_non_relues(gate_name, annotations)

    await enfiler_execution(
        pool,
        db,
        execution,
        "execute_sds_task",
        file=file_de_reprise(execution),
        execution_id=execution.id,
        project_id=execution.project_id,
        selected_agents=execution.selected_agents,
        resume_from=point_canonique,
    )
    logger.info(
        f"[ValidationGate] Execution {execution_id} relancee depuis "
        f"{point_canonique} (porte {gate_name})"
    )
    return {
        "execution_id": execution_id,
        "status": statut_reponse,
        "gate": gate_name,
        "approved": approved,
        **_annotations_dans_la_reponse(approved, annotations),
        "message": (
            f"{'Approved' if approved else 'Rejected with feedback'}. "
            f"Execution resuming from {point_canonique}."
        ),
    }


@router.get("/execute/{execution_id}/validation-history")
def get_validation_history(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full validation history for an execution."""
    verify_execution_access(execution_id, current_user.id, db)
    service = ValidationGateService(db)
    history = service.get_validation_history(execution_id)
    return {
        "execution_id": execution_id,
        "history": history,
    }
