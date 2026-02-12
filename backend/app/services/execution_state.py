"""
Execution State Machine — Explicit phase tracking with transactional transitions.

Provides granular state tracking for SDS and BUILD pipeline phases,
replacing the simple ExecutionStatus enum with a full state machine
that supports:
- Explicit phase states (sds_phase1_running, sds_phase2_complete, etc.)
- Validated transitions (prevents invalid state jumps)
- Row-level locking for concurrent safety
- Transition history for audit/debugging
- Backward compatibility mapping to legacy ExecutionStatus
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum as PyEnum

from sqlalchemy.orm import Session
from app.models.execution import Execution

logger = logging.getLogger(__name__)


class ExecutionState(str, PyEnum):
    """Granular execution states covering the full SDS + BUILD lifecycle."""

    # Lifecycle
    DRAFT = "draft"
    QUEUED = "queued"

    # SDS Phases
    SDS_PHASE1_RUNNING = "sds_phase1_running"
    SDS_PHASE1_COMPLETE = "sds_phase1_complete"
    WAITING_BR_VALIDATION = "waiting_br_validation"

    SDS_PHASE2_RUNNING = "sds_phase2_running"
    SDS_PHASE2_COMPLETE = "sds_phase2_complete"

    SDS_PHASE2_5_RUNNING = "sds_phase2_5_running"
    SDS_PHASE2_5_COMPLETE = "sds_phase2_5_complete"

    SDS_PHASE3_RUNNING = "sds_phase3_running"
    SDS_PHASE3_COMPLETE = "sds_phase3_complete"
    WAITING_ARCHITECTURE_VALIDATION = "waiting_architecture_validation"

    SDS_PHASE4_RUNNING = "sds_phase4_running"
    SDS_PHASE4_COMPLETE = "sds_phase4_complete"
    # P2-Full: Configurable gate after expert specs
    WAITING_EXPERT_VALIDATION = "waiting_expert_validation"

    SDS_PHASE5_RUNNING = "sds_phase5_running"
    SDS_COMPLETE = "sds_complete"
    # P2-Full: Configurable gate after SDS generation
    WAITING_SDS_VALIDATION = "waiting_sds_validation"

    # BUILD Phases
    BUILD_QUEUED = "build_queued"
    BUILD_RUNNING = "build_running"
    BUILD_VALIDATING = "build_validating"
    BUILD_COMPLETE = "build_complete"
    # P2-Full: Configurable gate after build code
    WAITING_BUILD_VALIDATION = "waiting_build_validation"

    # Deploy
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"

    # Terminal
    FAILED = "failed"
    CANCELLED = "cancelled"


# Transition table: current_state -> list of valid target states
TRANSITIONS: Dict[str, List[str]] = {
    "draft":                ["queued"],
    "queued":               ["sds_phase1_running", "failed", "cancelled"],

    "sds_phase1_running":   ["sds_phase1_complete", "waiting_br_validation", "failed"],
    "sds_phase1_complete":  ["sds_phase2_running", "waiting_br_validation"],
    "waiting_br_validation": ["sds_phase2_running", "cancelled"],

    "sds_phase2_running":   ["sds_phase2_complete", "failed"],
    "sds_phase2_complete":  ["sds_phase2_5_running"],

    "sds_phase2_5_running": ["sds_phase2_5_complete", "failed"],
    "sds_phase2_5_complete": ["sds_phase3_running"],

    "sds_phase3_running":   ["sds_phase3_complete", "waiting_architecture_validation", "failed"],
    "sds_phase3_complete":  ["sds_phase4_running"],
    "waiting_architecture_validation": ["sds_phase3_running", "sds_phase4_running", "cancelled"],

    "sds_phase4_running":   ["sds_phase4_complete", "failed"],
    "sds_phase4_complete":  ["sds_phase5_running", "waiting_expert_validation"],
    # P2-Full: After expert validation, proceed to Phase 5
    "waiting_expert_validation": ["sds_phase5_running", "sds_phase4_running", "cancelled"],

    "sds_phase5_running":   ["sds_complete", "failed"],
    "sds_complete":         ["build_queued", "waiting_sds_validation"],
    # P2-Full: After SDS validation, proceed to BUILD
    "waiting_sds_validation": ["build_queued", "sds_phase5_running", "cancelled"],

    "build_queued":         ["build_running", "failed", "cancelled"],
    "build_running":        ["build_validating", "build_complete", "failed"],
    "build_validating":     ["build_complete", "build_running", "failed"],
    "build_complete":       ["deploying", "waiting_build_validation"],
    # P2-Full: After build validation, proceed to deploy
    "waiting_build_validation": ["deploying", "build_running", "cancelled"],

    "deploying":            ["deployed", "failed"],
    "deployed":             [],
    # BUG-011: Allow resume from failed to any running phase (enables resume after crash)
    "failed":               ["queued", "sds_phase1_running", "sds_phase2_running", "sds_phase2_5_running",
                             "sds_phase3_running", "sds_phase4_running", "sds_phase5_running",
                             "build_queued", "build_running"],
    "cancelled":            ["queued"],
}


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current: str, target: str):
        self.current = current
        self.target = target
        super().__init__(f"Invalid transition: {current} → {target}")


class ExecutionStateMachine:
    """
    Manages execution state transitions with DB persistence.

    Usage:
        sm = ExecutionStateMachine(db, execution_id)
        sm.transition_to("sds_phase1_running")
        db.commit()
    """

    def __init__(self, db: Session, execution_id: int):
        self.db = db
        self.execution_id = execution_id

    def _get_execution(self) -> Execution:
        """Fetch execution with row-level lock for safe concurrent updates."""
        execution = self.db.query(Execution).filter(
            Execution.id == self.execution_id
        ).with_for_update().first()
        if not execution:
            raise ValueError(f"Execution {self.execution_id} not found")
        return execution

    @property
    def current_state(self) -> str:
        """Get current execution state without locking."""
        execution = self.db.query(Execution).filter(
            Execution.id == self.execution_id
        ).first()
        if not execution:
            raise ValueError(f"Execution {self.execution_id} not found")
        return execution.execution_state or "draft"

    def can_transition_to(self, target: str) -> bool:
        """Check if a transition to the target state is valid."""
        current = self.current_state
        return target in TRANSITIONS.get(current, [])

    def transition_to(self, target: str, metadata: Optional[dict] = None) -> str:
        """
        Transition to a new state. Auto-commits to release row lock.

        Args:
            target: Target state name
            metadata: Optional metadata to store with transition

        Returns:
            The new state

        Raises:
            InvalidTransitionError: if transition is not allowed
            ValueError: if execution not found
        """
        execution = self._get_execution()  # Row lock (FOR UPDATE)
        current = execution.execution_state or "draft"

        if target not in TRANSITIONS.get(current, []):
            self.db.rollback()  # BUG-002b: release FOR UPDATE lock on invalid transition
            raise InvalidTransitionError(current, target)

        # Update state
        execution.execution_state = target
        execution.state_updated_at = datetime.utcnow()

        # Map to legacy status for backward compatibility
        execution.status = self._map_to_legacy_status(target)

        # Store transition in history
        from sqlalchemy.orm.attributes import flag_modified
        history = list(execution.state_history or [])
        history.append({
            "from": current,
            "to": target,
            "at": datetime.utcnow().isoformat(),
            "metadata": metadata,
        })
        execution.state_history = history
        flag_modified(execution, "state_history")

        # BUG-002 fix: Auto-commit to release FOR UPDATE lock immediately.
        # Prevents deadlocks with audit_service or other sessions that
        # reference executions via FK constraints.
        self.db.commit()

        logger.info(
            f"[StateMachine] Execution {self.execution_id}: {current} → {target}"
        )
        return target

    @staticmethod
    def _map_to_legacy_status(state: str):
        """Map granular state to legacy ExecutionStatus for backward compat."""
        from app.models.execution import ExecutionStatus
        STATUS_MAP = {
            "draft": ExecutionStatus.PENDING,
            "failed": ExecutionStatus.FAILED,
            "cancelled": ExecutionStatus.CANCELLED,
            "waiting_br_validation": ExecutionStatus.WAITING_BR_VALIDATION,
            "waiting_architecture_validation": ExecutionStatus.WAITING_ARCHITECTURE_VALIDATION,
            "waiting_expert_validation": ExecutionStatus.WAITING_EXPERT_VALIDATION,
            "waiting_sds_validation": ExecutionStatus.WAITING_SDS_VALIDATION,
            "waiting_build_validation": ExecutionStatus.WAITING_BUILD_VALIDATION,
            "sds_complete": ExecutionStatus.COMPLETED,
            "build_complete": ExecutionStatus.COMPLETED,
            "deployed": ExecutionStatus.COMPLETED,
        }
        if state in STATUS_MAP:
            return STATUS_MAP[state]
        return ExecutionStatus.RUNNING

    def get_current_phase_number(self) -> int:
        """Get current SDS phase number (1-5) for frontend timeline."""
        state = self.current_state
        mapping = {
            "sds_phase1": 1,
            "waiting_br": 1,
            "sds_phase2_5": 2,
            "sds_phase2": 2,
            "sds_phase3": 3,
            "waiting_arch": 3,
            "sds_phase4": 4,
            "waiting_expert": 4,
            "sds_phase5": 5,
            "sds_complete": 5,
            "waiting_sds": 5,
        }
        for prefix, phase in mapping.items():
            if state.startswith(prefix):
                return phase
        return 0
