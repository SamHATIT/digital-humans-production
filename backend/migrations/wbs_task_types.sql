-- Migration: Phase 6 - WBS Task Types
-- Date: 2025-12-12
-- Description: Add task_type and is_automatable columns to task_executions

-- Add columns
ALTER TABLE task_executions ADD COLUMN IF NOT EXISTS task_type VARCHAR(50);
ALTER TABLE task_executions ADD COLUMN IF NOT EXISTS is_automatable BOOLEAN DEFAULT TRUE;

-- Index for filtering by task_type
CREATE INDEX IF NOT EXISTS idx_task_executions_task_type 
ON task_executions(task_type);

-- Index for filtering automatable tasks
CREATE INDEX IF NOT EXISTS idx_task_executions_automatable 
ON task_executions(is_automatable);

-- Done
SELECT 'Migration wbs_task_types completed' as status;
