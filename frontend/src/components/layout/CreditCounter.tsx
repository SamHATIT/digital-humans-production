import { useEffect, useState } from 'react';
import { Clock, Star } from 'lucide-react';
import { api } from '../../services/api';
import { useLang } from '../../contexts/LangContext';
import { useExecutionTracker } from '../../contexts/ExecutionTrackerContext';

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
 * Backend `/api/billing/balance` shape (CreditService.get_balance) :
 *   - tier              : str
 *   - included_credits  : int (monthly allowance)
 *   - used_credits      : int
 *   - overage_credits   : int
 *   - available         : int (current spendable balance)
 *   - daily_cap         : int | null
 *   - daily_used        : int
 *   - last_reset_at, next_reset_at
 *
 * Le précédent `CreditCounter` lisait `credits_remaining` / `monthly_quota`,
 * qui n'existent pas — d'où le silent fallback "hors-ligne".
 */
interface BillingBalance {
  available: number;
  included_credits: number;
  used_credits: number;
  daily_cap: number | null;
  daily_used: number;
  tier: string;
}

const REFRESH_MS = 60_000;

export default function CreditCounter() {
  const { t } = useLang();
  const [balance, setBalance] = useState<BillingBalance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;

    const fetchBalance = async () => {
      try {
        const data = await api.get('/api/billing/balance');
        if (!mounted) return;
        setBalance({
          available: Number(data?.available ?? 0),
          included_credits: Number(data?.included_credits ?? 0),
          used_credits: Number(data?.used_credits ?? 0),
          daily_cap: data?.daily_cap == null ? null : Number(data.daily_cap),
          daily_used: Number(data?.daily_used ?? 0),
          tier: typeof data?.tier === 'string' ? data.tier : 'free',
        });
        setError(false);
      } catch {
        if (!mounted) return;
        setBalance(null);
        setError(true);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchBalance();
    const id = window.setInterval(fetchBalance, REFRESH_MS);
    return () => {
      mounted = false;
      window.clearInterval(id);
    };
  }, []);

  // Free tier : daily cap is the meaningful "quota" (included_credits = 0).
  // Paid tier : monthly included_credits is the quota.
  const isFreeTier = balance ? balance.daily_cap != null && balance.included_credits === 0 : false;
  const remaining = balance?.available ?? 0;
  const quota = balance
    ? isFreeTier
      ? balance.daily_cap ?? 0
      : balance.included_credits
    : 0;
  const ratio = quota > 0 ? Math.min(1, Math.max(0, remaining / quota)) : 0;

  // Active execution tracker → live elapsed counter (1s tick)
  const { active } = useExecutionTracker();
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    if (!active?.startedAt) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active?.startedAt]);
  const elapsedSec = active?.startedAt
    ? Math.max(0, (now - new Date(active.startedAt).getTime()) / 1000)
    : null;

  return (
    <div className="hidden md:flex items-center gap-3 px-3 py-1.5 border border-brass/30">
      <Star className="w-3.5 h-3.5 text-brass" />
      <div className="flex flex-col leading-tight min-w-[88px]">
        <span className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
          {t('Credits', 'Crédits')}
        </span>
        <span className="font-mono text-sm text-brass whitespace-nowrap">
          {loading
            ? '— —'
            : error
              ? t('offline', 'hors-ligne')
              : quota > 0
                ? `${remaining.toLocaleString()} / ${quota.toLocaleString()}`
                : remaining.toLocaleString()}
        </span>
        {quota > 0 && !error && (
          <div className="mt-1 w-full h-[2px] bg-bone/15 overflow-hidden" aria-hidden>
            <div
              className="h-full bg-sage transition-[width] duration-500"
              style={{ width: `${ratio * 100}%` }}
            />
          </div>
        )}
      </div>
      {elapsedSec !== null && (
        <span className="flex items-center gap-2 pl-2">
          <span className="w-px h-6 bg-brass/20" aria-hidden />
          <Clock className="w-3 h-3 text-brass/70" />
          <span className="flex flex-col leading-tight min-w-[64px]">
            <span className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
              {t('Elapsed', 'Écoulé')}
            </span>
            <span className="font-mono text-sm text-bone-2 whitespace-nowrap">
              {formatElapsed(elapsedSec)}
            </span>
          </span>
        </span>
      )}
    </div>
  );
}
