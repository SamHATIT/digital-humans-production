"""
P2-Full: Configurable HITL validation gates between pipeline phases.

Manages pause/resume logic at configurable checkpoints. Works alongside
the existing BR validation (Phase 1) and architecture coverage gate (H12).
"""
import logging
from datetime import datetime, timezone
from typing import Optional

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

    def should_pause(self, execution_id: int, gate_name: str) -> bool:
        """Check if execution should pause at this gate.

        Note: after_br_extraction and after_architecture are handled by
        existing code in pm_orchestrator_service_v2.py. This method is
        for the NEW configurable gates only.
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
        return effective.get(gate_name, False)

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

        # Store pending validation info
        execution.pending_validation = {
            "gate": gate_name,
            "gate_label": GATE_LABELS.get(gate_name, gate_name),
            "deliverables": deliverables_summary,
            "paused_at": datetime.now(timezone.utc).isoformat(),
        }
        flag_modified(execution, "pending_validation")

        # Update status
        execution.status = gate_status

        # Try state machine transition (may fail if state doesn't match exactly)
        try:
            sm = ExecutionStateMachine(self.db, execution_id)
            sm.transition_to(gate_state)
        except Exception as e:
            logger.warning(
                f"[ValidationGate] State machine transition to {gate_state} failed: {e}. "
                f"Setting execution_state directly."
            )
            execution.execution_state = gate_state

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
