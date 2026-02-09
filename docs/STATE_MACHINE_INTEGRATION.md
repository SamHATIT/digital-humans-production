# State Machine Integration Guide

## Overview

The `ExecutionStateMachine` (I1.2) provides explicit phase tracking for SDS and BUILD
pipelines. This document explains how to integrate it into the orchestrator.

## Location

```
backend/app/services/execution_state.py
```

## Quick Start

```python
from app.services.execution_state import ExecutionStateMachine, InvalidTransitionError
```

## Integration Pattern

Each phase in `pm_orchestrator_service_v2.py` should bracket its work with
`transition_to()` calls. The caller is responsible for `db.commit()`.

### Phase 1 — Sophie: BR Extraction

```python
# At the start of Phase 1
sm = ExecutionStateMachine(self.db, execution_id)
sm.transition_to("sds_phase1_running")
self.db.commit()

# ... existing Phase 1 code (Sophie agent call) ...

# On success
sm.transition_to("sds_phase1_complete")
self.db.commit()
```

### Phase 1 → BR Validation (HITL)

```python
# If BR validation is required
sm.transition_to("waiting_br_validation")
self.db.commit()
# Execution pauses here — user validates BRs via frontend

# When user approves (in the validation endpoint)
sm = ExecutionStateMachine(db, execution_id)
sm.transition_to("sds_phase2_running")
db.commit()
```

### Phase 2 — Olivia: Use Cases

```python
sm.transition_to("sds_phase2_running")
self.db.commit()

# ... existing Phase 2 code (Olivia agent call, N times per BR) ...

sm.transition_to("sds_phase2_complete")
self.db.commit()
```

### Phase 2.5 — Emma: UC Digest

```python
sm.transition_to("sds_phase2_5_running")
self.db.commit()

# ... existing Phase 2.5 code (Emma analyze mode) ...

sm.transition_to("sds_phase2_5_complete")
self.db.commit()
```

### Phase 3 — Marcus: Architecture

```python
sm.transition_to("sds_phase3_running")
self.db.commit()

# ... existing Phase 3 code (Marcus: as_is, gap, design, wbs) ...

sm.transition_to("sds_phase3_complete")
self.db.commit()
```

### Phase 3.3 — Architecture Validation (HITL)

```python
# If architecture validation is required
sm.transition_to("waiting_architecture_validation")
self.db.commit()

# When user approves → phase 4
sm.transition_to("sds_phase4_running")
db.commit()

# When user requests revision → re-run phase 3
sm.transition_to("sds_phase3_running")
db.commit()
```

### Phase 4 — Experts (Elena, Jordan, Aisha, Lucas)

```python
sm.transition_to("sds_phase4_running")
self.db.commit()

# ... existing Phase 4 code (parallel expert calls) ...

sm.transition_to("sds_phase4_complete")
self.db.commit()
```

### Phase 5 — Emma: Write SDS

```python
sm.transition_to("sds_phase5_running")
self.db.commit()

# ... existing Phase 5 code (Emma write_sds mode) ...

sm.transition_to("sds_complete")
self.db.commit()
```

## Error Handling

On any agent failure, transition to `failed` with metadata:

```python
try:
    # ... agent call ...
    sm.transition_to("sds_phase2_complete")
except Exception as e:
    sm.transition_to("failed", metadata={"error": str(e), "phase": "phase2"})
    self.db.commit()
    raise
```

## Retry After Failure

```python
# From the retry endpoint
sm = ExecutionStateMachine(db, execution_id)
# current_state is "failed"
sm.transition_to("queued")  # Valid: failed -> queued
db.commit()
```

## Frontend Phase Display

Use `get_current_phase_number()` to show timeline progress:

```python
sm = ExecutionStateMachine(db, execution_id)
phase = sm.get_current_phase_number()  # Returns 1-5 for SDS phases, 0 otherwise
```

## Checking Transitions

Before attempting a transition, you can check validity:

```python
if sm.can_transition_to("sds_phase2_running"):
    sm.transition_to("sds_phase2_running")
```

## Legacy Compatibility

The state machine automatically maps granular states to the legacy `ExecutionStatus`
values (`pending`, `running`, `completed`, `failed`, `cancelled`, `waiting_*`).
Existing code reading `execution.status` continues to work unchanged.

## State Diagram

```
draft → queued → sds_phase1_running → sds_phase1_complete → sds_phase2_running
                                    ↘ waiting_br_validation ↗

sds_phase2_running → sds_phase2_complete → sds_phase2_5_running → sds_phase2_5_complete

→ sds_phase3_running → sds_phase3_complete → sds_phase4_running
                     ↘ waiting_architecture_validation ↗ (approve)
                       ↻ sds_phase3_running (revise)

sds_phase4_running → sds_phase4_complete → sds_phase5_running → sds_complete

sds_complete → build_queued → build_running → build_complete → deploying → deployed

Any running/complete state → failed → queued (retry)
Any waiting state → cancelled → queued (restart)
```

## Migration

Run the SQL migration before deploying:

```bash
psql -U digital_humans -d digital_humans -f backend/migrations/006_execution_state_machine.sql
```

## Dependencies

- Requires the `execution_state`, `state_updated_at`, and `state_history` columns
  on the `executions` table (added in migration 006).
- No dependency on P3 (subprocess refactor) — works with current agent executor.
- Should be integrated AFTER Stream A merge to avoid conflicts in `pm_orchestrator_service_v2.py`.
