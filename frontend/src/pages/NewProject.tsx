import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import { projects } from '../services/api';
import { useLang } from '../contexts/LangContext';

interface RecentProject {
  id: number;
  name: string;
  status: string;
  industry?: string;
  client_name?: string;
  updated_at?: string;
  created_at?: string;
}

const HUMAN_STATUS = (status: string, lang: 'en' | 'fr'): string => {
  const map: Record<string, { en: string; fr: string }> = {
    draft: { en: 'In casting', fr: 'En distribution' },
    in_progress: { en: 'On stage', fr: 'En scène' },
    sds_in_review: { en: 'Reviewing the brief', fr: 'Brief en revue' },
    sds_approved: { en: 'SDS approved', fr: 'SDS approuvé' },
    sds_generated: { en: 'SDS ready', fr: 'SDS prêt' },
    build_ready: { en: 'Ready to build', fr: 'Prêt à bâtir' },
    completed: { en: 'Finished', fr: 'Terminé' },
    failed: { en: 'Halted', fr: 'Interrompu' },
  };
  const entry = map[status];
  if (!entry) return status;
  return lang === 'fr' ? entry.fr : entry.en;
};

function formatRelative(iso: string | undefined, lang: 'en' | 'fr'): string {
  if (!iso) return lang === 'fr' ? 'date inconnue' : 'unknown date';
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return iso;
  const minutes = Math.max(1, Math.round((Date.now() - ts) / 60000));
  const hours = Math.round(minutes / 60);
  const days = Math.round(hours / 24);
  if (lang === 'fr') {
    if (minutes < 60) return `il y a ${minutes} min`;
    if (hours < 24) return `il y a ${hours} h`;
    if (days < 30) return `il y a ${days} j`;
    return new Date(ts).toLocaleDateString('fr-FR');
  }
  if (minutes < 60) return `${minutes} min ago`;
  if (hours < 24) return `${hours} h ago`;
  if (days < 30) return `${days} d ago`;
  return new Date(ts).toLocaleDateString('en-US');
}

export default function NewProject() {
  const { t, lang } = useLang();
  const [recent, setRecent] = useState<RecentProject[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    projects
      .list(0, 5)
      .then((data: { projects?: RecentProject[] } | RecentProject[]) => {
        if (cancelled) return;
        const rows = Array.isArray(data) ? data : (data?.projects ?? []);
        setRecent(Array.isArray(rows) ? rows.slice(0, 3) : []);
      })
      .catch(() => {
        if (!cancelled) setRecent([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      >
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
          {t('№ 02 · Casting', '№ 02 · Distribution')}
        </p>
        <h1 className="mt-5 font-serif italic text-[44px] md:text-[56px] leading-[1.05] text-bone max-w-3xl">
          {t('A new production begins.', 'Une nouvelle production commence.')}
        </h1>
        <p className="mt-6 max-w-2xl font-mono text-[12px] tracking-[0.04em] text-bone-3 leading-relaxed">
          {t(
            'Each project assembles its own ensemble. Tell us about your engagement, and the studio will compose accordingly.',
            "Chaque projet rassemble son propre ensemble. Parlez-nous de votre mission, le studio composera en conséquence.",
          )}
        </p>

        <div className="mt-10 flex flex-wrap items-center gap-4">
          <Link
            to="/wizard"
            className="inline-flex items-center gap-2 px-6 py-3 border border-brass bg-brass/10 hover:bg-brass/20 transition-colors font-mono text-[12px] tracking-cta uppercase text-brass"
          >
            {t('◗ Begin the casting →', '◗ Commencer le casting →')}
          </Link>
          <Link
            to="/"
            className="font-mono text-[11px] tracking-cta uppercase text-bone-4 hover:text-bone-2 transition-colors"
          >
            {t('Back to studio', 'Retour au studio')}
          </Link>
        </div>
      </motion.section>

      <hr className="my-16 border-bone/5" />

      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.2 }}
      >
        <header className="mb-6 flex items-baseline justify-between">
          <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
            {t('Recent productions', 'Productions récentes')}
          </p>
          <Link
            to="/projects"
            className="font-mono text-[11px] tracking-cta uppercase text-bone-4 hover:text-brass"
          >
            {t('View all →', 'Voir tout →')}
          </Link>
        </header>

        {loading ? (
          <div className="flex items-center gap-3 px-1 py-4">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-brass" />
            <span className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
              {t('Reading the repertoire…', 'Lecture du répertoire…')}
            </span>
          </div>
        ) : recent.length === 0 ? (
          <p className="font-mono text-[11px] text-bone-4">
            {t(
              'No previous production. The stage is yours.',
              'Aucune production précédente. La scène est à vous.',
            )}
          </p>
        ) : (
          <ul className="divide-y divide-bone/5 border-t border-bone/5">
            {recent.map((p) => (
              <li key={p.id} className="py-4 flex flex-wrap items-baseline gap-4">
                <span className="font-serif italic text-bone text-lg flex-1 min-w-[200px]">
                  {p.name}
                </span>
                <span className="font-mono text-[11px] text-bone-3">
                  {p.industry ?? p.client_name ?? t('Studio', 'Studio')}
                </span>
                <span className="font-mono text-[11px] text-bone-4">
                  · {HUMAN_STATUS(p.status, lang)}
                </span>
                <span className="font-mono text-[11px] text-bone-4">
                  · {formatRelative(p.updated_at ?? p.created_at, lang)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </motion.section>
    </div>
  );
}
