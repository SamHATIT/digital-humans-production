/**
 * ExecutionTrackerContext — partage l'execution courante entre la page
 * d'exécution (Monitor / Build) et le header global, pour que le
 * CreditCounter puisse afficher l'elapsed à côté des crédits compte.
 *
 * Pas de fetch ici — la page set/clear le tracker via setActiveExecution().
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

interface ActiveExecution {
  executionId: number;
  startedAt: string;
}

interface ExecutionTrackerCtx {
  active: ActiveExecution | null;
  setActiveExecution: (exec: ActiveExecution | null) => void;
}

const Ctx = createContext<ExecutionTrackerCtx>({
  active: null,
  setActiveExecution: () => {},
});

export function ExecutionTrackerProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<ActiveExecution | null>(null);

  const setActiveExecution = useCallback((exec: ActiveExecution | null) => {
    setActive(exec);
  }, []);

  const value = useMemo(() => ({ active, setActiveExecution }), [active, setActiveExecution]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Read the current active execution. */
export function useExecutionTracker() {
  return useContext(Ctx);
}

/**
 * Helper hook for execution pages. Sets the active execution on mount when
 * `startedAt` is available, clears it on unmount.
 */
export function useTrackExecution(executionId: number | undefined, startedAt: string | null) {
  const { setActiveExecution } = useExecutionTracker();
  useEffect(() => {
    if (!executionId || !startedAt) return;
    setActiveExecution({ executionId, startedAt });
    return () => setActiveExecution(null);
  }, [executionId, startedAt, setActiveExecution]);
}
