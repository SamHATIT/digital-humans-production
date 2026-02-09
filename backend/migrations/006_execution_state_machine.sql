-- Migration: I1.2 — Execution State Machine
-- Date: 2026-02-09
-- Description: Add granular execution state tracking columns for phase-level state machine

-- 1. Add execution_state column (granular phase state)
ALTER TABLE executions ADD COLUMN IF NOT EXISTS execution_state VARCHAR(60) DEFAULT 'draft';

-- 2. Add state_updated_at timestamp
ALTER TABLE executions ADD COLUMN IF NOT EXISTS state_updated_at TIMESTAMP WITH TIME ZONE;

-- 3. Add state_history JSONB column (transition audit log)
ALTER TABLE executions ADD COLUMN IF NOT EXISTS state_history JSONB DEFAULT '[]';

-- 4. Create index for filtering by execution state
CREATE INDEX IF NOT EXISTS ix_executions_execution_state ON executions (execution_state);

-- 5. Backfill existing executions: map legacy status to new execution_state
UPDATE executions SET execution_state = CASE
    WHEN status = 'pending' THEN 'draft'
    WHEN status = 'running' THEN 'queued'
    WHEN status = 'completed' THEN 'sds_complete'
    WHEN status = 'failed' THEN 'failed'
    WHEN status = 'cancelled' THEN 'cancelled'
    WHEN status = 'waiting_br_validation' THEN 'waiting_br_validation'
    WHEN status = 'waiting_architecture_validation' THEN 'waiting_architecture_validation'
    ELSE 'draft'
END
WHERE execution_state IS NULL OR execution_state = 'draft';

-- Done
SELECT 'Migration 006_execution_state_machine completed' as status;
