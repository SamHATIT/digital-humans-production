"""
P2-Full: Configurable HITL validation gates between pipeline phases.

Manages pause/resume logic at configurable checkpoints. Works alongside
the existing BR validation (Phase 1) and architecture coverage gate (H12).
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.services.execution_state import ExecutionStateMachine

logger = logging.getLogger(__name__)

# Default gates configuration.
# after_br_extraction and after_architecture are always-on (handled by existing code).
# The three new gates are configurable and disabled by default.
DEFAULT_VALIDATION_GATES = {
    "after_br_extraction": True,       # Always on (existing Phase 1 HITL)
    "after_architecture": True,        # Always on (existing H12 coverage gate)
    "after_expert_specs": False,       # Configurable: pause after Phase 4
    "after_sds_generation": False,     # Configurable: pause after Phase 5
    "after_build_code": False,         # Configurable: pause after BUILD (future)
}

# Maps gate names to the ExecutionStatus used when pausing
GATE_STATUS_MAP = {
    "after_expert_specs": ExecutionStatus.WAITING_EXPERT_VALIDATION,
    "after_sds_generation": ExecutionStatus.WAITING_SDS_VALIDATION,
    "after_build_code": ExecutionStatus.WAITING_BUILD_VALIDATION,
}

# Maps gate names to the execution_state values
GATE_STATE_MAP = {
    "after_expert_specs": "waiting_expert_validation",
    "after_sds_generation": "waiting_sds_validation",
    "after_build_code": "waiting_build_validation",
}

# Human-readable labels
GATE_LABELS = {
    "after_br_extraction": "Business Requirements Validation",
    "after_architecture": "Architecture Coverage Validation",
    "after_expert_specs": "Expert Specifications Review",
    "after_sds_generation": "SDS Document Review",
    "after_build_code": "Build Code Review",
}


def empreinte_livrable(deliverables_summary: Optional[dict]) -> Optional[str]:
    """Empreinte stable du livrable soumis a une porte.

    VAGUE 1 / FILE C — PROD-06, troisieme point : « approbation rattachee a une
    version de sortie ; ne pas reposer une porte deja franchie sans nouveau
    contenu ». L'empreinte EST cette version : deux resumes identiques
    designent le meme livrable, un resume different un livrable regenere.

    Rend None pour un resume absent ou vide : sans contenu a comparer, il n'y a
    pas de version a rattacher, et la porte se repose (on ne ferme pas une
    porte par defaut).
    """
    if not deliverables_summary:
        return None
    try:
        forme = json.dumps(deliverables_summary, sort_keys=True, default=str)
    except Exception:  # un resume non serialisable ne fait pas foi
        return None
    return hashlib.sha256(forme.encode("utf-8")).hexdigest()[:32]


class ValidationGateService:
    """Manages HITL validation gates between pipeline phases."""

    def __init__(self, db: Session):
        self.db = db

    def get_project_gates(self, project_id: int) -> dict:
        """Get the effective gate configuration for a project.

        Returns the project-specific overrides merged with defaults.
        """
        project = self.db.query(Project).get(project_id)
        if not project:
            return dict(DEFAULT_VALIDATION_GATES)
        project_gates = project.validation_gates or {}
        merged = dict(DEFAULT_VALIDATION_GATES)
        merged.update(project_gates)
        return merged

    def update_project_gates(self, project_id: int, gates: dict) -> dict:
        """Update the validation gate configuration for a project.

        Only the three configurable gates can be toggled.
        after_br_extraction and after_architecture are always-on.
        """
        project = self.db.query(Project).get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Enforce always-on gates
        sanitized = {}
        for gate_name, enabled in gates.items():
            if gate_name in ("after_br_extraction", "after_architecture"):
                sanitized[gate_name] = True  # Cannot disable
            elif gate_name in DEFAULT_VALIDATION_GATES:
                sanitized[gate_name] = bool(enabled)

        project.validation_gates = sanitized
        flag_modified(project, "validation_gates")
        self.db.commit()
        return sanitized

    def should_pause(
        self,
        execution_id: int,
        gate_name: str,
        deliverables_summary: Optional[dict] = None,
    ) -> bool:
        """Check if execution should pause at this gate.

        Note: after_br_extraction and after_architecture are handled by
        existing code in pm_orchestrator_service_v2.py. This method is
        for the NEW configurable gates only.

        VAGUE 1 / FILE C — PROD-06 : une porte deja APPROUVEE pour ce meme
        livrable ne se repose pas. Sans ce point, la reprise qui suit une
        approbation repasse ici, repose la porte sur le contenu qu'elle vient
        de valider, et la boucle est fermee.

        `deliverables_summary` est le livrable que l'appelant s'apprete a
        soumettre. Il est facultatif : sans lui, il n'y a rien a comparer et la
        porte se pose, comme avant. Un rejet ne ferme pas la porte — seul un
        accord le fait.
        """
        execution = self.db.query(Execution).get(execution_id)
        if not execution:
            return False

        project = self.db.query(Project).get(execution.project_id)
        if not project:
            return False

        gates = project.validation_gates or {}
        # Merge with defaults - if not configured, use default
        effective = dict(DEFAULT_VALIDATION_GATES)
        effective.update(gates)
        if not effective.get(gate_name, False):
            return False

        empreinte = empreinte_livrable(deliverables_summary)
        if empreinte and self._deja_approuvee(execution, gate_name, empreinte):
            logger.info(
                f"[ValidationGate] Porte {gate_name!r} deja approuvee pour ce "
                f"livrable (execution {execution_id}) : pas de nouvelle pause."
            )
            return False
        return True

    @staticmethod
    def _deja_approuvee(execution: Execution, gate_name: str, empreinte: str) -> bool:
        """Cette porte a-t-elle ete approuvee pour ce livrable exact ?"""
        for decision in execution.validation_history or []:
            if (
                decision.get("gate") == gate_name
                and decision.get("approved") is True
                and decision.get("empreinte") == empreinte
            ):
                return True
        return False

    def pause_for_validation(
        self,
        execution_id: int,
        gate_name: str,
        deliverables_summary: dict,
    ) -> None:
        """Pause execution at a validation gate.

        Sets execution status and stores gate metadata for the frontend.
        """
        execution = self.db.query(Execution).get(execution_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        gate_status = GATE_STATUS_MAP.get(gate_name)
        gate_state = GATE_STATE_MAP.get(gate_name)
        if not gate_status or not gate_state:
            raise ValueError(f"Unknown gate: {gate_name}")

        # VAGUE 1 / FILE C — PROD-06, premier point : l'ORDRE compte.
        #
        # Avant, `pending_validation` et le statut etaient ecrits ici, puis la
        # transition etait demandee. Une transition refusee fait un
        # `rollback()` (pour liberer le verrou FOR UPDATE) — qui annulait les
        # deux ecritures precedentes. Le service forcait ensuite
        # `execution_state` seul : la porte etait posee sans son contenu, et
        # l'ecran de validation n'avait rien a afficher.
        #
        # La transition passe donc d'abord, et rien de ce qui suit ne peut etre
        # annule par elle.
        try:
            sm = ExecutionStateMachine(self.db, execution_id)
            sm.transition_to(gate_state)
        except Exception as e:
            logger.warning(
                f"[ValidationGate] State machine transition to {gate_state} failed: {e}. "
                f"Setting execution_state directly."
            )
            execution = self.db.query(Execution).get(execution_id)
            execution.execution_state = gate_state

        # L'objet peut avoir ete expire par le commit/rollback de la machine a
        # etats : on le relit avant d'ecrire.
        execution = self.db.query(Execution).get(execution_id)
        execution.pending_validation = {
            "gate": gate_name,
            "gate_label": GATE_LABELS.get(gate_name, gate_name),
            "deliverables": deliverables_summary,
            "empreinte": empreinte_livrable(deliverables_summary),
            "paused_at": datetime.now(timezone.utc).isoformat(),
        }
        flag_modified(execution, "pending_validation")
        execution.status = gate_status

        self.db.commit()
        logger.info(
            f"[ValidationGate] Execution {execution_id} paused at gate '{gate_name}'"
        )

    def submit_validation(
        self,
        execution_id: int,
        approved: bool,
        annotations: Optional[str] = None,
    ) -> dict:
        """User approves or rejects with optional annotations.

        Returns the validation result dict.
        """
        execution = self.db.query(Execution).get(execution_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")

        gate_info = execution.pending_validation or {}
        gate_name = gate_info.get("gate", "unknown")

        result = {
            "gate": gate_name,
            "gate_label": gate_info.get("gate_label", gate_name),
            "approved": approved,
            "annotations": annotations,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "deliverables": gate_info.get("deliverables", {}),
            # PROD-06 : la decision porte sur UNE version du livrable. C'est
            # elle que `should_pause` compare pour ne pas reposer une porte
            # deja franchie sur le meme contenu.
            "empreinte": gate_info.get("empreinte"),
        }

        # Append to validation history
        history = list(execution.validation_history or [])
        history.append(result)
        execution.validation_history = history
        flag_modified(execution, "validation_history")

        # Clear pending
        execution.pending_validation = None
        flag_modified(execution, "pending_validation")

        self.db.commit()

        logger.info(
            f"[ValidationGate] Execution {execution_id} gate '{gate_name}' "
            f"{'approved' if approved else 'rejected'}"
            f"{' with annotations' if annotations else ''}"
        )
        return result

    def get_pending_validation(self, execution_id: int) -> Optional[dict]:
        """Get the current pending validation info, or None if not paused."""
        execution = self.db.query(Execution).get(execution_id)
        if not execution:
            return None
        return execution.pending_validation

    def get_validation_history(self, execution_id: int) -> list:
        """Get the validation history for an execution."""
        execution = self.db.query(Execution).get(execution_id)
        if not execution:
            return []
        return execution.validation_history or []
