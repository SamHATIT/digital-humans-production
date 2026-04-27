import { useEffect, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface RedesignedBannerProps {
  /** Identifiant unique de la page, sert de clé de dismiss localStorage. */
  pageKey: string;
  /** Sprint qui livrera la refonte. */
  sprint?: string;
}

const STORAGE_PREFIX = 'studio.redesigned-banner.dismissed.';

/**
 * Bandeau discret signalant qu'une page legacy est en attente de refonte
 * Studio (A5.2 / A5.3 / A5.4). Dismissable, mémoire localStorage par page.
 *
 * Le bandeau utilise les tokens Studio (`bg-ink-3`, `text-bone-3`) et
 * fonctionne aussi bien sur fond Studio que sur fond legacy slate.
 */
export default function RedesignedBanner({ pageKey, sprint = 'next sprint' }: RedesignedBannerProps) {
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const stored = window.localStorage.getItem(STORAGE_PREFIX + pageKey);
    setDismissed(stored === 'true');
  }, [pageKey]);

  const handleDismiss = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_PREFIX + pageKey, 'true');
    }
    setDismissed(true);
  };

  if (dismissed) return null;

  return (
    <div
      role="status"
      className="bg-[#1C1C1F] border-b border-[#C8A97E33] text-[#B5B0A4]"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex items-center gap-3">
        <AlertTriangle className="w-4 h-4 text-[#B88B3F] shrink-0" />
        <p className="font-mono text-[11px] tracking-[0.12em] uppercase flex-1 leading-relaxed">
          This page is being redesigned. New Studio version coming in {sprint}.
        </p>
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Dismiss redesign notice"
          className="p-1 text-[#6F6B62] hover:text-[#F5F2EC] transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
