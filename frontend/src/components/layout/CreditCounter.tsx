import { useEffect, useState } from 'react';
import { Star } from 'lucide-react';
import { api } from '../../services/api';
import { useLang } from '../../contexts/LangContext';

interface BillingBalance {
  credits_remaining: number;
  monthly_quota: number;
  tier?: string;
}

const REFRESH_MS = 60_000;

const FALLBACK: BillingBalance = {
  credits_remaining: 0,
  monthly_quota: 0,
  tier: 'free',
};

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
          credits_remaining: Number(data?.credits_remaining ?? 0),
          monthly_quota: Number(data?.monthly_quota ?? 0),
          tier: data?.tier ?? 'free',
        });
        setError(false);
      } catch {
        if (!mounted) return;
        // Endpoint absent → on garde un placeholder discret, pas un crash.
        setBalance(FALLBACK);
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

  const remaining = balance?.credits_remaining ?? 0;
  const quota = balance?.monthly_quota ?? 0;
  const ratio = quota > 0 ? Math.min(1, Math.max(0, remaining / quota)) : 0;

  return (
    <div className="hidden md:flex items-center gap-3 px-3 py-1.5 border border-brass/30">
      <Star className="w-3.5 h-3.5 text-brass" />
      <div className="flex flex-col leading-tight">
        <span className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
          {t('Credits', 'Crédits')}
        </span>
        <span className="font-mono text-sm text-brass">
          {loading
            ? '— —'
            : error
              ? t('offline', 'hors-ligne')
              : quota > 0
                ? `${remaining.toLocaleString()} / ${quota.toLocaleString()}`
                : remaining.toLocaleString()}
        </span>
      </div>
      {quota > 0 && !error && (
        <div className="w-16 h-[3px] bg-ink-3 overflow-hidden" aria-hidden>
          <div
            className="h-full bg-brass transition-[width] duration-500"
            style={{ width: `${ratio * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}
