import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { useLang } from '../../contexts/LangContext';

/**
 * WelcomeBanner — shown once after signup (ONBOARDING-001).
 *
 * Reads `sessionStorage.onboarding:justSignedUp` set by SignupPage and
 * displays a tier-aware welcome message on the Dashboard. Auto-clears the
 * flag on mount so it never shows twice.
 */
const TIER_COPY: Record<
  string,
  {
    label: string;
    title: { en: string; fr: string };
    body: { en: string; fr: string };
    cta: { en: string; fr: string };
    next: string;
  }
> = {
  free: {
    label: 'Free',
    title: {
      en: 'Welcome to the studio.',
      fr: 'Bienvenue dans le studio.',
    },
    body: {
      en: 'Sophie reads briefs. Olivia turns them into use cases. Tell Sophie about your first project — she\u2019ll take it from there.',
      fr: 'Sophie lit les briefs. Olivia les traduit en use cases. Parle à Sophie de ton premier projet — elle s\u2019occupe du reste.',
    },
    cta: {
      en: 'Start a project',
      fr: 'Démarrer un projet',
    },
    next: '/projects/new',
  },
};

export default function WelcomeBanner() {
  const { t } = useLang();
  const [tier, setTier] = useState<string | null>(null);

  useEffect(() => {
    const flag = sessionStorage.getItem('onboarding:justSignedUp');
    if (flag && flag in TIER_COPY) {
      setTier(flag);
      // Clear immediately so a refresh / re-mount won't show it again.
      sessionStorage.removeItem('onboarding:justSignedUp');
    }
  }, []);

  if (!tier) return null;
  const copy = TIER_COPY[tier];

  return (
    <div className="relative bg-ink-2 border border-brass/30 px-6 py-5 mb-6 flex items-start gap-5">
      {/* Brass rim accent */}
      <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-brass" aria-hidden />

      <div className="flex-1 min-w-0">
        <p className="font-mono text-[10px] tracking-eyebrow uppercase text-brass">
          {t('Starting tier', 'Tier de départ')} · {copy.label}
        </p>
        <p className="mt-1.5 font-serif italic text-2xl text-bone leading-snug">
          {t(copy.title.en, copy.title.fr)}
        </p>
        <p className="mt-2 font-mono text-[12px] leading-relaxed text-bone-3 max-w-2xl">
          {t(copy.body.en, copy.body.fr)}
        </p>
        <a
          href={copy.next}
          className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-brass text-ink font-mono text-[11px] tracking-cta uppercase hover:bg-brass-2 transition-colors"
        >
          {t(copy.cta.en, copy.cta.fr)}
          <span aria-hidden>→</span>
        </a>
      </div>

      <button
        type="button"
        onClick={() => setTier(null)}
        className="text-bone-4 hover:text-bone transition-colors p-1"
        aria-label={t('Dismiss', 'Fermer')}
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
