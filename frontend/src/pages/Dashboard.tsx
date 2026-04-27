import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, AlertTriangle, Loader2, Activity } from 'lucide-react';
import { api, projects } from '../services/api';
import { useLang } from '../contexts/LangContext';
import StudioPlaceholderCover from '../components/layout/StudioPlaceholderCover';

interface ProjectRow {
  id: number;
  name: string;
  description?: string;
  status: string;
  industry?: string;
  client_name?: string;
  cover_image?: string;
  created_at: string;
  updated_at?: string;
}

interface CurrentUser {
  email?: string;
  name?: string;
  first_name?: string;
}

interface ExecutionRow {
  id: number;
  project_id?: number;
  project_name?: string;
  status: string;
  current_agent?: string;
  progress_percent?: number;
  started_at?: string;
}

interface EmptyCard {
  index: string;
  title: { en: string; fr: string };
  body: { en: string; fr: string };
  cta: { en: string; fr: string };
  href: string;
  external?: boolean;
}

const EMPTY_CARDS: EmptyCard[] = [
  {
    index: '№ 01',
    title: { en: 'Cast your first ensemble', fr: 'Distribuez votre premier ensemble' },
    body: {
      en: 'Pick a brief, summon eleven agents and let the studio begin.',
      fr: 'Choisissez un brief, convoquez les onze agents, laissez le studio jouer.',
    },
    cta: { en: 'Open the wizard →', fr: 'Ouvrir le wizard →' },
    href: '/wizard',
  },
  {
    index: '№ 02',
    title: { en: 'Browse the gallery', fr: 'Parcourir la galerie' },
    body: {
      en: 'Six exhibition pieces, six finished plays — see what the agents have already shipped.',
      fr: 'Six pièces d’exposition, six pièces achevées — découvrez ce que les agents ont déjà livré.',
    },
    cta: { en: 'Visit the gallery →', fr: 'Visiter la galerie →' },
    href: '/preview',
    external: true,
  },
  {
    index: '№ 03',
    title: { en: 'Read the manifesto', fr: 'Lire le manifeste' },
    body: {
      en: 'Eleven agents, one studio, no slop. Our founding text in twelve minutes.',
      fr: 'Onze agents, un studio, aucune complaisance. Le texte fondateur en douze minutes.',
    },
    cta: { en: 'Read the manifesto →', fr: 'Lire le manifeste →' },
    href: 'https://digital-humans.fr/journal/manifesto',
    external: true,
  },
];

function deriveFirstName(user: CurrentUser | null): string {
  if (!user) return '';
  if (user.first_name) return user.first_name;
  if (user.name) return user.name.split(/\s+/)[0] ?? user.name;
  if (user.email) return user.email.split('@')[0] ?? '';
  return '';
}

function formatRelative(iso: string | undefined, lang: 'en' | 'fr'): string {
  if (!iso) return lang === 'fr' ? 'date inconnue' : 'unknown date';
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return iso;
  const seconds = Math.max(1, Math.round((Date.now() - ts) / 1000));
  const minutes = Math.round(seconds / 60);
  const hours = Math.round(minutes / 60);
  const days = Math.round(hours / 24);
  if (lang === 'fr') {
    if (seconds < 60) return `il y a ${seconds}s`;
    if (minutes < 60) return `il y a ${minutes} min`;
    if (hours < 24) return `il y a ${hours} h`;
    if (days < 30) return `il y a ${days} j`;
    return new Date(ts).toLocaleDateString('fr-FR');
  }
  if (seconds < 60) return `${seconds}s ago`;
  if (minutes < 60) return `${minutes} min ago`;
  if (hours < 24) return `${hours} h ago`;
  if (days < 30) return `${days} d ago`;
  return new Date(ts).toLocaleDateString('en-US');
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { lang, t } = useLang();

  const [user, setUser] = useState<CurrentUser | null>(null);
  const [projectList, setProjectList] = useState<ProjectRow[]>([]);
  const [activeExecutions, setActiveExecutions] = useState<ExecutionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(null);

      // 1. Profil utilisateur (best-effort)
      try {
        const me = await api.get('/api/auth/me');
        if (!cancelled) setUser({
          email: me?.email,
          name: me?.name,
          first_name: me?.first_name,
        });
      } catch {
        if (!cancelled) setUser(null);
      }

      // 2. Projets (source : pm-orchestrator/projects)
      try {
        const data = await projects.list(0, 50);
        const rows: ProjectRow[] = (data?.projects ?? data ?? []) as ProjectRow[];
        if (!cancelled) setProjectList(Array.isArray(rows) ? rows : []);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unable to load projects.';
        if (!cancelled) setError(msg);
      }

      // 3. Exécutions actives — endpoint optionnel, fallback silencieux
      try {
        const data = await api.get('/api/executions?status=running');
        const rows: ExecutionRow[] = (data?.executions ?? data ?? []) as ExecutionRow[];
        if (!cancelled) setActiveExecutions(Array.isArray(rows) ? rows : []);
      } catch {
        if (!cancelled) setActiveExecutions([]);
      }

      if (!cancelled) setLoading(false);
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const firstName = deriveFirstName(user);
  const hasProjects = projectList.length > 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Hero */}
      <section className="mb-16">
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
          № 01 · Studio
        </p>
        <h1 className="mt-4 font-serif italic text-4xl md:text-5xl text-bone leading-tight">
          {firstName
            ? t(`Welcome back, ${firstName}.`, `Bon retour, ${firstName}.`)
            : t('Welcome back.', 'Bon retour.')}
        </h1>
        <p className="mt-4 max-w-xl font-mono text-[12px] tracking-[0.04em] text-bone-3 leading-relaxed">
          {t(
            'Eleven agents stand by. Cast a project, brief them, and watch the studio at work.',
            'Onze agents en coulisses. Distribuez un projet, briefez-les, et regardez le studio à l’œuvre.',
          )}
        </p>
      </section>

      {/* Loading */}
      {loading && (
        <div className="border border-bone/5 bg-ink-2 px-6 py-16 flex items-center justify-center gap-3">
          <Loader2 className="w-4 h-4 animate-spin text-brass" />
          <span className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
            {t('Loading the studio…', 'Chargement du studio…')}
          </span>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="border border-error/40 bg-ink-2 px-6 py-6 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-error mt-[2px] shrink-0" />
          <div>
            <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-2">
              {t('Could not load projects', 'Impossible de charger les projets')}
            </p>
            <p className="mt-1 font-mono text-[11px] text-bone-4">{error}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-3 font-mono text-[11px] tracking-cta uppercase text-brass hover:text-brass-2"
            >
              {t('Retry', 'Réessayer')} →
            </button>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && !hasProjects && (
        <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {EMPTY_CARDS.map((card) => {
            const cardInner = (
              <article className="group border border-bone/5 bg-ink-2 p-8 h-full flex flex-col transition-colors hover:border-brass/40">
                <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
                  {card.index} · Studio
                </p>
                <h2 className="mt-4 font-serif italic text-2xl text-bone leading-snug">
                  {t(card.title.en, card.title.fr)}
                </h2>
                <p className="mt-3 font-mono text-[11px] tracking-[0.04em] text-bone-3 leading-relaxed flex-1">
                  {t(card.body.en, card.body.fr)}
                </p>
                <span className="mt-6 inline-flex items-center gap-2 font-mono text-[11px] tracking-cta uppercase text-brass group-hover:text-brass-2">
                  {t(card.cta.en, card.cta.fr)}
                </span>
              </article>
            );
            return card.external ? (
              <a key={card.index} href={card.href} target="_blank" rel="noreferrer" className="block">
                {cardInner}
              </a>
            ) : (
              <Link key={card.index} to={card.href} className="block">
                {cardInner}
              </Link>
            );
          })}
        </section>
      )}

      {/* Projects grid */}
      {!loading && !error && hasProjects && (
        <section>
          <header className="flex items-end justify-between mb-6 border-b border-bone/5 pb-4">
            <div>
              <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
                № 02 · Repertoire
              </p>
              <h2 className="mt-2 font-serif italic text-2xl text-bone">
                {t('Your productions', 'Vos productions')}
              </h2>
            </div>
            <Link
              to="/wizard"
              className="font-mono text-[11px] tracking-cta uppercase text-brass hover:text-brass-2"
            >
              {t('+ New production', '+ Nouvelle production')}
            </Link>
          </header>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projectList.map((project) => {
              const monogram = project.name
                ?.split(/\s+/)
                .map((w) => w[0])
                .filter(Boolean)
                .slice(0, 2)
                .join('')
                .toUpperCase() || 'DH';

              return (
                <button
                  key={project.id}
                  type="button"
                  onClick={() => {
                    const sdsStatuses = ['sds_generated', 'sds_in_review', 'sds_approved', 'build_ready'];
                    if (sdsStatuses.includes(project.status)) {
                      navigate(`/project/${project.id}`);
                    } else {
                      navigate(`/execution/${project.id}`);
                    }
                  }}
                  className="text-left group border border-bone/5 bg-ink-2 hover:border-brass/40 transition-colors flex flex-col"
                >
                  <div className="aspect-[16/10] overflow-hidden bg-ink-3 border-b border-bone/5">
                    {project.cover_image ? (
                      <img
                        src={project.cover_image}
                        alt=""
                        className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-[1.02]"
                      />
                    ) : (
                      <StudioPlaceholderCover monogram={monogram} className="w-full h-full" />
                    )}
                  </div>
                  <div className="p-5 flex flex-col gap-2 flex-1">
                    <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                      {project.industry ?? project.client_name ?? t('Studio', 'Studio')}
                    </p>
                    <h3 className="font-serif italic text-xl text-bone leading-snug">
                      {project.name}
                    </h3>
                    <p className="mt-auto font-mono text-[11px] text-bone-3 flex items-center justify-between">
                      <span>
                        {t('Last activity', 'Dernière activité')} ·{' '}
                        {formatRelative(project.updated_at ?? project.created_at, lang)}
                      </span>
                      <ArrowRight className="w-3.5 h-3.5 text-brass opacity-0 group-hover:opacity-100 transition-opacity" />
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* Work in progress */}
      {!loading && !error && (
        <section className="mt-20">
          <header className="mb-6 border-b border-bone/5 pb-4">
            <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
              № 03 · Backstage
            </p>
            <h2 className="mt-2 font-serif italic text-2xl text-bone">
              {t('The work in progress', 'L’ouvrage en cours')}
            </h2>
          </header>

          {activeExecutions.length === 0 ? (
            <div className="border border-bone/5 bg-ink-2 px-6 py-10 text-center">
              <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
                {t('No active performance right now.', 'Aucune représentation en cours.')}
              </p>
            </div>
          ) : (
            <ol className="relative border-l border-brass/20 pl-6 space-y-6">
              {activeExecutions.slice(0, 6).map((exec) => (
                <li key={exec.id} className="relative">
                  <span className="absolute -left-[31px] top-1.5 w-2 h-2 bg-brass animate-pulse-dot" />
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <span className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                      Exec № {exec.id}
                    </span>
                    <h3 className="font-serif italic text-lg text-bone">
                      {exec.project_name ?? `Project #${exec.project_id ?? '—'}`}
                    </h3>
                  </div>
                  <p className="mt-1 font-mono text-[11px] text-bone-3 flex items-center gap-2">
                    <Activity className="w-3 h-3 text-brass" />
                    {exec.current_agent ?? t('on stage', 'en scène')}
                    {typeof exec.progress_percent === 'number' && (
                      <span className="text-bone-4">· {Math.round(exec.progress_percent)}%</span>
                    )}
                    <span className="text-bone-4">
                      · {formatRelative(exec.started_at, lang)}
                    </span>
                  </p>
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </div>
  );
}
