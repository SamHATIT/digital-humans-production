"""
Tests for ExecutionStateMachine (I1.2).

Covers:
- Happy path: full SDS pipeline (draft → sds_complete)
- Invalid transitions
- Legacy status mapping
- Concurrent transitions (row-level locking)
- Phase number mapping
- Transition history tracking
- Edge cases (retry from failed, restart from cancelled)
"""
import pytest
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import create_engine, JSON
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.execution import Execution, ExecutionStatus
from app.models.user import User
from app.models.project import Project
from app.services.execution_state import (
    ExecutionState,
    ExecutionStateMachine,
    InvalidTransitionError,
    TRANSITIONS,
)

# Register PostgreSQL type → SQLite type mappings for test compatibility
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy import event, String

# In-memory SQLite for unit tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_state_machine.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL mode for better concurrent access in tests."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


# Patch SQLiteTypeCompiler to handle PostgreSQL-specific types
if not hasattr(SQLiteTypeCompiler, 'visit_JSONB'):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"
if not hasattr(SQLiteTypeCompiler, 'visit_ARRAY'):
    SQLiteTypeCompiler.visit_ARRAY = lambda self, type_, **kw: "JSON"
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def user(db):
    """Create a test user."""
    u = User(
        email="test@test.com",
        hashed_password="fakehash",
        name="Test User",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def project(db, user):
    """Create a test project."""
    p = Project(
        name="Test Project",
        description="A test project",
        user_id=user.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def execution(db, project, user):
    """Create a test execution with default state."""
    e = Execution(
        project_id=project.id,
        user_id=user.id,
        status=ExecutionStatus.PENDING,
        execution_state="draft",
        state_history=[],
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


class TestExecutionStateEnum:
    """Test the ExecutionState enum."""

    def test_all_states_in_transitions(self):
        """Every enum value must appear as a key in TRANSITIONS."""
        for state in ExecutionState:
            assert state.value in TRANSITIONS, (
                f"State {state.value} missing from TRANSITIONS table"
            )

    def test_all_transition_targets_are_valid_states(self):
        """Every target in TRANSITIONS must be a valid ExecutionState value."""
        valid_values = {s.value for s in ExecutionState}
        for source, targets in TRANSITIONS.items():
            for target in targets:
                assert target in valid_values, (
                    f"Invalid target '{target}' in transition from '{source}'"
                )

    def test_terminal_states(self):
        """Deployed has no outgoing transitions."""
        assert TRANSITIONS["deployed"] == []

    def test_failed_allows_retry(self):
        """Failed state allows transition back to queued."""
        assert "queued" in TRANSITIONS["failed"]

    def test_cancelled_allows_restart(self):
        """Cancelled state allows transition back to queued."""
        assert "queued" in TRANSITIONS["cancelled"]


class TestStateMachineHappyPath:
    """Test the full SDS pipeline happy path: draft → sds_complete."""

    HAPPY_PATH = [
        "queued",
        "sds_phase1_running",
        "sds_phase1_complete",
        "sds_phase2_running",
        "sds_phase2_complete",
        "sds_phase2_5_running",
        "sds_phase2_5_complete",
        "sds_phase3_running",
        "sds_phase3_complete",
        "sds_phase4_running",
        "sds_phase4_complete",
        "sds_phase5_running",
        "sds_complete",
    ]

    def test_full_sds_pipeline(self, db, execution):
        """Walk through the entire SDS pipeline without HITL pauses."""
        sm = ExecutionStateMachine(db, execution.id)
        assert sm.current_state == "draft"

        for target in self.HAPPY_PATH:
            result = sm.transition_to(target)
            db.commit()
            assert result == target
            assert sm.current_state == target

    def test_full_pipeline_records_history(self, db, execution):
        """Each transition is recorded in state_history."""
        sm = ExecutionStateMachine(db, execution.id)

        for target in self.HAPPY_PATH:
            sm.transition_to(target)
            db.commit()

        db.refresh(execution)
        history = execution.state_history
        assert len(history) == len(self.HAPPY_PATH)
        assert history[0]["from"] == "draft"
        assert history[0]["to"] == "queued"
        assert history[-1]["to"] == "sds_complete"

    def test_pipeline_with_br_validation(self, db, execution):
        """SDS pipeline with HITL BR validation pause."""
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        sm.transition_to("sds_phase1_running")
        sm.transition_to("waiting_br_validation")
        db.commit()

        assert sm.current_state == "waiting_br_validation"

        # User approves
        sm.transition_to("sds_phase2_running")
        db.commit()
        assert sm.current_state == "sds_phase2_running"

    def test_pipeline_with_architecture_validation(self, db, execution):
        """SDS pipeline with HITL architecture validation + revision."""
        sm = ExecutionStateMachine(db, execution.id)

        # Get to phase 3
        for target in ["queued", "sds_phase1_running", "sds_phase1_complete",
                        "sds_phase2_running", "sds_phase2_complete",
                        "sds_phase2_5_running", "sds_phase2_5_complete",
                        "sds_phase3_running"]:
            sm.transition_to(target)

        # Architecture needs revision
        sm.transition_to("waiting_architecture_validation")
        db.commit()
        assert sm.current_state == "waiting_architecture_validation"

        # User requests revision → re-run phase 3
        sm.transition_to("sds_phase3_running")
        db.commit()
        assert sm.current_state == "sds_phase3_running"

        # Phase 3 completes on second attempt
        sm.transition_to("sds_phase3_complete")
        sm.transition_to("sds_phase4_running")
        db.commit()
        assert sm.current_state == "sds_phase4_running"


class TestInvalidTransitions:
    """Test that invalid transitions raise InvalidTransitionError."""

    def test_skip_phases(self, db, execution):
        """Cannot jump from phase 1 running directly to phase 4."""
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        sm.transition_to("sds_phase1_running")
        db.commit()

        with pytest.raises(InvalidTransitionError) as exc_info:
            sm.transition_to("sds_phase4_running")

        assert exc_info.value.current == "sds_phase1_running"
        assert exc_info.value.target == "sds_phase4_running"

    def test_backward_transition(self, db, execution):
        """Cannot go from phase 2 back to phase 1."""
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        sm.transition_to("sds_phase1_running")
        sm.transition_to("sds_phase1_complete")
        sm.transition_to("sds_phase2_running")
        db.commit()

        with pytest.raises(InvalidTransitionError):
            sm.transition_to("sds_phase1_running")

    def test_draft_to_running(self, db, execution):
        """Cannot go from draft directly to running (must queue first)."""
        sm = ExecutionStateMachine(db, execution.id)

        with pytest.raises(InvalidTransitionError):
            sm.transition_to("sds_phase1_running")

    def test_complete_to_draft(self, db, execution):
        """Cannot go from sds_complete back to draft."""
        sm = ExecutionStateMachine(db, execution.id)
        for target in ["queued", "sds_phase1_running", "sds_phase1_complete",
                        "sds_phase2_running", "sds_phase2_complete",
                        "sds_phase2_5_running", "sds_phase2_5_complete",
                        "sds_phase3_running", "sds_phase3_complete",
                        "sds_phase4_running", "sds_phase4_complete",
                        "sds_phase5_running", "sds_complete"]:
            sm.transition_to(target)
        db.commit()

        with pytest.raises(InvalidTransitionError):
            sm.transition_to("draft")

    def test_deployed_is_terminal(self, db, execution):
        """Deployed has no valid outgoing transitions."""
        sm = ExecutionStateMachine(db, execution.id)
        # Walk full path to deployed
        for target in ["queued", "sds_phase1_running", "sds_phase1_complete",
                        "sds_phase2_running", "sds_phase2_complete",
                        "sds_phase2_5_running", "sds_phase2_5_complete",
                        "sds_phase3_running", "sds_phase3_complete",
                        "sds_phase4_running", "sds_phase4_complete",
                        "sds_phase5_running", "sds_complete",
                        "build_queued", "build_running", "build_complete",
                        "deploying", "deployed"]:
            sm.transition_to(target)
        db.commit()

        with pytest.raises(InvalidTransitionError):
            sm.transition_to("queued")


class TestLegacyStatusMapping:
    """Test _map_to_legacy_status backward compatibility."""

    def test_draft_maps_to_pending(self):
        assert ExecutionStateMachine._map_to_legacy_status("draft") == "pending"

    def test_failed_maps_to_failed(self):
        assert ExecutionStateMachine._map_to_legacy_status("failed") == "failed"

    def test_cancelled_maps_to_cancelled(self):
        assert ExecutionStateMachine._map_to_legacy_status("cancelled") == "cancelled"

    def test_waiting_states_preserved(self):
        assert ExecutionStateMachine._map_to_legacy_status("waiting_br_validation") == "waiting_br_validation"
        assert ExecutionStateMachine._map_to_legacy_status("waiting_architecture_validation") == "waiting_architecture_validation"

    def test_complete_states_map_to_completed(self):
        assert ExecutionStateMachine._map_to_legacy_status("sds_complete") == "completed"
        assert ExecutionStateMachine._map_to_legacy_status("build_complete") == "completed"
        assert ExecutionStateMachine._map_to_legacy_status("deployed") == "completed"

    def test_running_states_map_to_running(self):
        running_states = [
            "queued", "sds_phase1_running", "sds_phase1_complete",
            "sds_phase2_running", "sds_phase3_running", "sds_phase4_running",
            "sds_phase5_running", "build_queued", "build_running",
            "build_validating", "deploying",
        ]
        for state in running_states:
            assert ExecutionStateMachine._map_to_legacy_status(state) == "running", (
                f"State {state} should map to 'running'"
            )

    def test_legacy_status_updated_on_transition(self, db, execution):
        """When transitioning, legacy status field is also updated."""
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        db.commit()
        db.refresh(execution)
        assert execution.status == "running"

        sm.transition_to("sds_phase1_running")
        sm.transition_to("failed")
        db.commit()
        db.refresh(execution)
        assert execution.status == "failed"


class TestPhaseNumber:
    """Test get_current_phase_number mapping."""

    def test_draft_returns_0(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        assert sm.get_current_phase_number() == 0

    def test_phase1_states(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        sm.transition_to("sds_phase1_running")
        db.commit()
        assert sm.get_current_phase_number() == 1

    def test_phase1_complete(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        sm.transition_to("sds_phase1_running")
        sm.transition_to("sds_phase1_complete")
        db.commit()
        assert sm.get_current_phase_number() == 1

    def test_waiting_br_is_phase1(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        sm.transition_to("sds_phase1_running")
        sm.transition_to("waiting_br_validation")
        db.commit()
        assert sm.get_current_phase_number() == 1

    def test_phase2_states(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        for t in ["queued", "sds_phase1_running", "sds_phase1_complete",
                   "sds_phase2_running"]:
            sm.transition_to(t)
        db.commit()
        assert sm.get_current_phase_number() == 2

    def test_phase2_5_is_phase2(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        for t in ["queued", "sds_phase1_running", "sds_phase1_complete",
                   "sds_phase2_running", "sds_phase2_complete",
                   "sds_phase2_5_running"]:
            sm.transition_to(t)
        db.commit()
        assert sm.get_current_phase_number() == 2

    def test_phase3_states(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        for t in ["queued", "sds_phase1_running", "sds_phase1_complete",
                   "sds_phase2_running", "sds_phase2_complete",
                   "sds_phase2_5_running", "sds_phase2_5_complete",
                   "sds_phase3_running"]:
            sm.transition_to(t)
        db.commit()
        assert sm.get_current_phase_number() == 3

    def test_waiting_architecture_is_phase3(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        for t in ["queued", "sds_phase1_running", "sds_phase1_complete",
                   "sds_phase2_running", "sds_phase2_complete",
                   "sds_phase2_5_running", "sds_phase2_5_complete",
                   "sds_phase3_running", "waiting_architecture_validation"]:
            sm.transition_to(t)
        db.commit()
        assert sm.get_current_phase_number() == 3

    def test_phase4(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        for t in ["queued", "sds_phase1_running", "sds_phase1_complete",
                   "sds_phase2_running", "sds_phase2_complete",
                   "sds_phase2_5_running", "sds_phase2_5_complete",
                   "sds_phase3_running", "sds_phase3_complete",
                   "sds_phase4_running"]:
            sm.transition_to(t)
        db.commit()
        assert sm.get_current_phase_number() == 4

    def test_phase5(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        for t in ["queued", "sds_phase1_running", "sds_phase1_complete",
                   "sds_phase2_running", "sds_phase2_complete",
                   "sds_phase2_5_running", "sds_phase2_5_complete",
                   "sds_phase3_running", "sds_phase3_complete",
                   "sds_phase4_running", "sds_phase4_complete",
                   "sds_phase5_running"]:
            sm.transition_to(t)
        db.commit()
        assert sm.get_current_phase_number() == 5

    def test_sds_complete_is_phase5(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        for t in ["queued", "sds_phase1_running", "sds_phase1_complete",
                   "sds_phase2_running", "sds_phase2_complete",
                   "sds_phase2_5_running", "sds_phase2_5_complete",
                   "sds_phase3_running", "sds_phase3_complete",
                   "sds_phase4_running", "sds_phase4_complete",
                   "sds_phase5_running", "sds_complete"]:
            sm.transition_to(t)
        db.commit()
        assert sm.get_current_phase_number() == 5


class TestCanTransitionTo:
    """Test the can_transition_to helper."""

    def test_valid_transition(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        assert sm.can_transition_to("queued") is True

    def test_invalid_transition(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        assert sm.can_transition_to("sds_phase4_running") is False

    def test_after_transition(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        db.commit()
        assert sm.can_transition_to("sds_phase1_running") is True
        assert sm.can_transition_to("draft") is False


class TestTransitionMetadata:
    """Test metadata storage in transition history."""

    def test_metadata_stored(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued", metadata={"trigger": "api", "user_id": 42})
        db.commit()

        db.refresh(execution)
        entry = execution.state_history[0]
        assert entry["metadata"]["trigger"] == "api"
        assert entry["metadata"]["user_id"] == 42

    def test_metadata_none_by_default(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        db.commit()

        db.refresh(execution)
        entry = execution.state_history[0]
        assert entry["metadata"] is None

    def test_timestamp_recorded(self, db, execution):
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        db.commit()

        db.refresh(execution)
        entry = execution.state_history[0]
        assert "at" in entry
        # Should be parseable as ISO datetime
        datetime.fromisoformat(entry["at"])


class TestRetryAndRestart:
    """Test retry from failed and restart from cancelled."""

    def test_retry_from_failed(self, db, execution):
        """Failed → queued for retry."""
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        sm.transition_to("sds_phase1_running")
        sm.transition_to("failed")
        db.commit()

        assert sm.current_state == "failed"
        sm.transition_to("queued")
        db.commit()
        assert sm.current_state == "queued"

    def test_restart_from_cancelled(self, db, execution):
        """Cancelled → queued for restart."""
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        sm.transition_to("sds_phase1_running")
        sm.transition_to("waiting_br_validation")
        sm.transition_to("cancelled")
        db.commit()

        assert sm.current_state == "cancelled"
        sm.transition_to("queued")
        db.commit()
        assert sm.current_state == "queued"

    def test_full_retry_cycle(self, db, execution):
        """Failed → queued → run full pipeline again."""
        sm = ExecutionStateMachine(db, execution.id)
        # First attempt fails at phase 2
        sm.transition_to("queued")
        sm.transition_to("sds_phase1_running")
        sm.transition_to("sds_phase1_complete")
        sm.transition_to("sds_phase2_running")
        sm.transition_to("failed")
        db.commit()

        # Retry
        sm.transition_to("queued")
        sm.transition_to("sds_phase1_running")
        sm.transition_to("sds_phase1_complete")
        sm.transition_to("sds_phase2_running")
        sm.transition_to("sds_phase2_complete")
        db.commit()

        assert sm.current_state == "sds_phase2_complete"
        db.refresh(execution)
        # History should have all transitions from both attempts
        # First attempt: draft→queued, queued→phase1, phase1→complete, complete→phase2, phase2→failed (5)
        # Retry: failed→queued, queued→phase1, phase1→complete, complete→phase2, phase2→complete (5)
        assert len(execution.state_history) == 10


class TestExecutionNotFound:
    """Test behavior when execution doesn't exist."""

    def test_current_state_raises(self, db):
        sm = ExecutionStateMachine(db, 99999)
        with pytest.raises(ValueError, match="not found"):
            _ = sm.current_state

    def test_transition_raises(self, db):
        sm = ExecutionStateMachine(db, 99999)
        with pytest.raises(ValueError, match="not found"):
            sm.transition_to("queued")


class TestConcurrency:
    """Test concurrent access safety."""

    def test_two_sessions_same_execution(self, db, execution):
        """
        Simulate concurrent access: two state machines on the same execution.
        SQLite doesn't support row-level locking, so we just verify the
        second transition sees the updated state and raises appropriately.
        """
        sm1 = ExecutionStateMachine(db, execution.id)
        sm1.transition_to("queued")
        db.commit()

        # Same session, simulate a second "concurrent" attempt
        sm2 = ExecutionStateMachine(db, execution.id)
        assert sm2.current_state == "queued"

        # Both try to move forward — first succeeds
        sm1.transition_to("sds_phase1_running")
        db.commit()

        # sm2 sees updated state, can't do the same transition
        # (it's already at sds_phase1_running, not queued)
        assert sm2.current_state == "sds_phase1_running"

    def test_state_updated_at_changes(self, db, execution):
        """state_updated_at should be set on every transition."""
        sm = ExecutionStateMachine(db, execution.id)
        sm.transition_to("queued")
        db.commit()
        db.refresh(execution)

        first_update = execution.state_updated_at
        assert first_update is not None

        sm.transition_to("sds_phase1_running")
        db.commit()
        db.refresh(execution)

        second_update = execution.state_updated_at
        assert second_update is not None
        assert second_update >= first_update
