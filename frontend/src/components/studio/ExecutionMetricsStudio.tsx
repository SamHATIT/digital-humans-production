import { useEffect, useState } from 'react';
import { useLang } from '../../contexts/LangContext';
import type { BudgetInfo } from '../../hooks/useExecutionStream';

interface ExecutionMetricsStudioProps {
  /** Optional cents/dollars from the backend. */
  budget: BudgetInfo | null;
  /** Backend execution_state — used for the iteration counter. */
  executionState?: string;
  /** Number of revisions already played (architecture, etc.). */
  revisionCount?: number;
  /** Started timestamp (ISO) — for elapsed counter. */
  startedAt?: string | null;
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm > 0 ? `${h}h ${rm}m` : `${h}h`;
}

/**
 * Left-rail vital signs of a Theatre execution.
 * Credits + elapsed time + iteration count, in Studio palette.
 */
export default function ExecutionMetricsStudio({
  budget,
  executionState,
  revisionCount = 0,
  startedAt,
}: ExecutionMetricsStudioProps) {
  const { t } = useLang();
  const [now, setNow] = useState<number>(() => Date.now());

  useEffect(() => {
    if (!startedAt) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  const elapsedSec = startedAt
    ? Math.max(0, (now - new Date(startedAt).getTime()) / 1000)
    : null;

  const cost = budget?.execution_cost ?? 0;
  const limit = budget?.limit ?? 50;
  const remaining = Math.max(0, limit - cost);
  const overBudget = cost > limit;
  const warnBudget = cost > limit * 0.8;

  return (
    <aside className="bg-ink-2 border border-bone/10 sticky top-20">
      <div className="border-b border-bone/10 px-5 py-3">
        <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
          {t('Box office', 'Caisse du théâtre')}
        </p>
      </div>

      <dl className="px-5 py-5 space-y-5">
        <div>
          <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
            {t('Credits used', 'Crédits utilisés')}
          </dt>
          <dd className="mt-1 flex items-baseline gap-2">
            <span
              className={[
                'font-serif text-2xl',
                overBudget ? 'text-error' : warnBudget ? 'text-warning' : 'text-bone',
              ].join(' ')}
            >
              ${cost.toFixed(2)}
            </span>
            <span className="font-mono text-[10px] text-bone-4">
              / ${limit.toFixed(2)}
            </span>
          </dd>
          <div className="mt-2 h-[2px] bg-bone/10 overflow-hidden">
            <div
              className={[
                'h-full transition-all duration-500',
                overBudget ? 'bg-error' : warnBudget ? 'bg-warning' : 'bg-brass',
              ].join(' ')}
              style={{ width: `${Math.min(100, (cost / limit) * 100)}%` }}
            />
          </div>
          <p className="mt-1 font-mono text-[10px] text-bone-4">
            {t('Remaining', 'Reste')}: ${remaining.toFixed(2)}
          </p>
        </div>

        <div>
          <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
            {t('Elapsed', 'Durée')}
          </dt>
          <dd className="mt-1 font-serif text-2xl text-bone">
            {elapsedSec != null ? formatElapsed(elapsedSec) : '—'}
          </dd>
        </div>

        <div>
          <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
            {t('Revisions', 'Révisions')}
          </dt>
          <dd className="mt-1 font-serif text-2xl text-bone">
            {revisionCount > 0 ? `× ${revisionCount}` : t('first take', '1ère prise')}
          </dd>
        </div>

        {executionState && (
          <div>
            <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
              {t('State', 'État')}
            </dt>
            <dd className="mt-1 font-mono text-[11px] text-bone-3 break-all">
              {executionState}
            </dd>
          </div>
        )}
      </dl>
    </aside>
  );
}
