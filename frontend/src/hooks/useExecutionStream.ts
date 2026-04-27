import { useEffect, useRef, useState } from 'react';
import { executions } from '../services/api';

export interface AgentProgress {
  agent_name: string;
  status: string;
  progress: number;
  current_task?: string;
  output_summary?: string;
  extra_data?: {
    approval_type?: string;
    coverage_score?: number;
    critical_gaps?: Array<{ gap: string; severity: string }>;
    uncovered_use_cases?: string[];
    revision_count?: number;
    max_revisions?: number;
  };
  tokens_used?: number;
  cost?: number;
  duration_seconds?: number;
}

export interface ExecutionProgress {
  execution_id: number;
  project_id: number;
  status: string;
  execution_state?: string;
  overall_progress: number;
  current_phase?: string;
  agent_progress: AgentProgress[];
  sds_document_path?: string;
}

export interface BudgetInfo {
  allowed: boolean;
  execution_cost: number;
  project_cost: number;
  remaining_execution: number;
  remaining_project: number;
  limit_type?: string;
  current?: number;
  limit?: number;
  message?: string;
}

const STOP_STATUSES = new Set([
  'completed',
  'failed',
  'cancelled',
  'waiting_br_validation',
  'waiting_architecture_validation',
  'waiting_expert_validation',
  'waiting_sds_validation',
  'waiting_build_validation',
]);

const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled']);

interface UseExecutionStreamResult {
  progress: ExecutionProgress | null;
  budget: BudgetInfo | null;
  error: string | null;
  isInitialLoading: boolean;
  /** Force a refresh (typically after a HITL action). */
  refresh: () => Promise<void>;
}

function progressChanged(
  prev: ExecutionProgress | null,
  next: ExecutionProgress | null,
): boolean {
  if (!prev || !next) return true;
  if (prev.status !== next.status) return true;
  if (prev.execution_state !== next.execution_state) return true;
  if (prev.overall_progress !== next.overall_progress) return true;
  if ((prev.agent_progress?.length || 0) !== (next.agent_progress?.length || 0)) return true;
  for (const a of prev.agent_progress || []) {
    const b = next.agent_progress?.find((x) => x.agent_name === a.agent_name);
    if (!b) return true;
    if (a.status !== b.status || a.progress !== b.progress || a.current_task !== b.current_task) {
      return true;
    }
  }
  return false;
}

/**
 * Polls progress + budget for a Theatre execution. Mirrors the previous
 * inline logic in `ExecutionMonitoringPage` but exposed as a hook so the
 * Studio page stays focused on rendering.
 */
export function useExecutionStream(
  executionId: number | undefined,
  options: { progressIntervalMs?: number; budgetIntervalMs?: number } = {},
): UseExecutionStreamResult {
  const { progressIntervalMs = 3000, budgetIntervalMs = 10000 } = options;

  const [progress, setProgress] = useState<ExecutionProgress | null>(null);
  const [budget, setBudget] = useState<BudgetInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isInitialLoading, setInitialLoading] = useState(true);

  const progressRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const budgetRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const latestRef = useRef<ExecutionProgress | null>(null);
  const idRef = useRef<number | undefined>(executionId);

  const stopProgressPolling = () => {
    if (progressRef.current) {
      clearInterval(progressRef.current);
      progressRef.current = null;
    }
  };
  const stopBudgetPolling = () => {
    if (budgetRef.current) {
      clearInterval(budgetRef.current);
      budgetRef.current = null;
    }
  };

  const fetchProgress = async () => {
    if (!idRef.current) return;
    try {
      const data: ExecutionProgress = await executions.getProgress(idRef.current);
      if (data) {
        if (progressChanged(latestRef.current, data)) {
          latestRef.current = data;
          setProgress(data);
        }
        if (STOP_STATUSES.has(data.status)) {
          stopProgressPolling();
          if (TERMINAL_STATUSES.has(data.status)) stopBudgetPolling();
        }
      }
    } catch (err: any) {
      if (!latestRef.current) {
        setError(err?.message || 'Failed to fetch progress');
      }
    } finally {
      setInitialLoading(false);
    }
  };

  const fetchBudget = async () => {
    if (!idRef.current) return;
    try {
      const data: BudgetInfo = await executions.getBudget(idRef.current);
      if (data) setBudget(data);
    } catch {
      // Budget is optional — silent failure.
    }
  };

  useEffect(() => {
    idRef.current = executionId;
    if (!executionId) return;

    setInitialLoading(true);
    setError(null);
    latestRef.current = null;
    setProgress(null);
    setBudget(null);

    fetchProgress();
    fetchBudget();
    progressRef.current = setInterval(fetchProgress, progressIntervalMs);
    budgetRef.current = setInterval(fetchBudget, budgetIntervalMs);

    return () => {
      stopProgressPolling();
      stopBudgetPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [executionId, progressIntervalMs, budgetIntervalMs]);

  const refresh = async () => {
    stopProgressPolling();
    await fetchProgress();
    if (idRef.current && !TERMINAL_STATUSES.has(latestRef.current?.status || '')) {
      progressRef.current = setInterval(fetchProgress, progressIntervalMs);
    }
  };

  return { progress, budget, error, isInitialLoading, refresh };
}

export function normalizeStatus(status: string | undefined | null): string {
  if (!status) return 'pending';
  const map: Record<string, string> = {
    COMPLETED: 'completed',
    RUNNING: 'running',
    IN_PROGRESS: 'in_progress',
    PENDING: 'pending',
    FAILED: 'failed',
  };
  return map[status.toUpperCase()] || status.toLowerCase();
}

export function isAgentActive(status: string | undefined | null): boolean {
  const s = normalizeStatus(status);
  return s === 'running' || s === 'in_progress';
}
