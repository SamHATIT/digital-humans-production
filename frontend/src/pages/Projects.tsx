/**
 * Projects — listing Studio (A5.4).
 * № 02 · THE WORKS — your productions to date.
 * Réutilise les patterns de cards du Dashboard (A5.1).
 */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLang } from '../contexts/LangContext';
import { projects } from '../services/api';
import StudioPlaceholderCover from '../components/layout/StudioPlaceholderCover';

interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  created_at: string;
}

type Filter = 'all' | 'casting' | 'live' | 'archived';

const SDS_REVIEW_STATUSES = ['sds_generated', 'sds_in_review', 'sds_approved', 'build_ready'];

function classifyStatus(status: string): Filter {
  const s = status.toLowerCase();
  if (s === 'completed') return 'live';
  if (s === 'archived' || s === 'failed') return 'archived';
  if (SDS_REVIEW_STATUSES.includes(s) || s === 'in_progress' || s === 'ready') return 'live';
  return 'casting';
}

function statusEyebrow(status: string, t: <T>(en: T, fr: T) => T): string {
  const map: Record<string, { en: string; fr: string }> = {
    draft:          { en: 'In casting',     fr: 'En casting' },
    in_progress:    { en: 'In progress',    fr: 'En cours' },
    ready:          { en: 'Ready',          fr: 'Prêt' },
    sds_generated:  { en: 'SDS phase',      fr: 'Phase SDS' },
    sds_in_review:  { en: 'SDS review',     fr: 'SDS en revue' },
    sds_approved:   { en: 'SDS approved',   fr: 'SDS approuvé' },
    build_ready:    { en: 'Build phase',    fr: 'Phase BUILD' },
    completed:      { en: 'Live',           fr: 'En production' },
    failed:         { en: 'Failed',         fr: 'Échoué' },
    archived:       { en: 'Archived',       fr: 'Archivé' },
  };
  const entry = map[status.toLowerCase()];
  if (!entry) return status.toUpperCase();
  return t(entry.en, entry.fr).toUpperCase();
}

export default function Projects() {
  const navigate = useNavigate();
  const { t, lang } = useLang();
  const [list, setList] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('all');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data: any = await projects.list(0, 100);
        if (cancelled) return;
        const items: Project[] = (data?.projects || data || []) as Project[];
        setList(items);
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? 'Failed to load projects');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const counts = useMemo(() => {
    const c: Record<Filter, number> = { all: list.length, casting: 0, live: 0, archived: 0 };
    for (const p of list) c[classifyStatus(p.status)]++;
    return c;
  }, [list]);

  const visible = useMemo(() => {
    if (filter === 'all') return list;
    return list.filter((p) => classifyStatus(p.status) === filter);
  }, [list, filter]);

  const handleOpen = (p: Project) => {
    if (SDS_REVIEW_STATUSES.includes(p.status.toLowerCase())) {
      navigate(`/project/${p.id}`);
    } else {
      navigate(`/execution/${p.id}`);
    }
  };

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const sure = window.confirm(
      t('Delete this production? This cannot be undone.', 'Supprimer cette production ? Action irréversible.'),
    );
    if (!sure) return;
    try {
      await projects.delete(id);
      setList((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      window.alert(t('Could not delete.', 'Suppression impossible.'));
    }
  };

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return iso;
    }
  };

  const filterLabel = (id: Filter): string => {
    const labels: Record<Filter, { en: string; fr: string }> = {
      all:      { en: 'All',         fr: 'Toutes' },
      casting:  { en: 'In casting',  fr: 'En casting' },
      live:     { en: 'Live',        fr: 'Actives' },
      archived: { en: 'Archived',    fr: 'Archivées' },
    };
    return t(labels[id].en, labels[id].fr);
  };

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6 mb-12">
        <div>
          <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-3">
            № 02 · {t('The works', 'Les œuvres')}
          </p>
          <h1 className="font-serif italic text-4xl md:text-5xl text-bone leading-[1.05]">
            {t('Your productions to date.', 'Vos productions à ce jour.')}
          </h1>
        </div>
        <button
          type="button"
          onClick={() => navigate('/projects/new')}
          className="inline-flex items-center gap-2 px-5 py-3 bg-brass text-ink font-mono text-[11px] tracking-cta uppercase hover:bg-brass-2 transition-colors self-start md:self-auto"
        >
          + {t('Begin a new production', 'Démarrer une production')}
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-1 border-b border-bone/10 mb-8 overflow-x-auto">
        {(['all', 'casting', 'live', 'archived'] as Filter[]).map((f) => {
          const active = f === filter;
          return (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`relative px-4 py-3 font-mono text-[11px] tracking-eyebrow uppercase whitespace-nowrap transition-colors ${
                active ? 'text-brass' : 'text-bone-3 hover:text-bone'
              }`}
            >
              <span className="inline-flex items-center gap-2">
                {filterLabel(f)}
                <span
                  className={`inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] tabular-nums ${
                    active ? 'bg-brass/20 text-brass' : 'bg-ink-3 text-bone-4'
                  }`}
                >
                  {counts[f]}
                </span>
              </span>
              {active && (
                <span aria-hidden="true" className="absolute left-0 right-0 -bottom-px h-px bg-brass" />
              )}
            </button>
          );
        })}
      </div>

      {/* States */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-ink-2 border border-bone/10 h-72 animate-pulse" />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="bg-ink-2 border border-error/30 p-6">
          <p className="font-mono text-[11px] tracking-eyebrow uppercase text-error mb-2">
            {t('Error', 'Erreur')}
          </p>
          <p className="font-mono text-[12px] text-bone-2">{error}</p>
        </div>
      )}

      {!loading && !error && visible.length === 0 && (
        <div className="bg-ink-2 border border-bone/10 p-16 text-center">
          <p className="font-serif italic text-2xl text-bone-2 mb-3">
            {t('No productions yet.', 'Aucune production pour le moment.')}
          </p>
          <p className="font-mono text-[12px] text-bone-3 mb-8">
            {t('Cast your first ensemble.', 'Lancez votre premier casting.')}
          </p>
          <button
            type="button"
            onClick={() => navigate('/projects/new')}
            className="inline-flex items-center gap-2 px-5 py-3 bg-brass text-ink font-mono text-[11px] tracking-cta uppercase hover:bg-brass-2 transition-colors"
          >
            + {t('Begin a new production', 'Démarrer une production')}
          </button>
        </div>
      )}

      {!loading && !error && visible.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {visible.map((p) => (
            <article
              key={p.id}
              onClick={() => handleOpen(p)}
              className="group relative cursor-pointer bg-ink-2 border border-bone/10 hover:border-brass/40 transition-colors overflow-hidden"
            >
              {/* Cover */}
              <div className="aspect-[5/3] bg-ink-3 border-b border-bone/10 overflow-hidden">
                <StudioPlaceholderCover monogram={p.name.split(/\s+/).slice(0,2).map(w=>w[0]?.toUpperCase()??"").join("")||"DH"} className="w-full h-full" />
              </div>

              {/* Body */}
              <div className="p-5">
                <p className="font-mono text-[10px] tracking-eyebrow uppercase text-brass mb-2">
                  {statusEyebrow(p.status, t)}
                </p>
                <h2 className="font-serif italic text-xl text-bone leading-tight mb-2 line-clamp-2">
                  {p.name}
                </h2>
                {p.description && (
                  <p className="font-mono text-[11px] text-bone-3 line-clamp-2 mb-3">
                    {p.description}
                  </p>
                )}
                <p className="font-mono text-[10px] text-bone-4">
                  {t('Created', 'Créé le')} · {formatDate(p.created_at)}
                </p>
              </div>

              {/* Hover panel — actions */}
              <div className="absolute inset-x-0 bottom-0 translate-y-full group-hover:translate-y-0 transition-transform duration-300 bg-ink-3/95 backdrop-blur-sm border-t border-brass/30 px-5 py-3 flex items-center justify-between">
                <span className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
                  {t('Open', 'Ouvrir')} →
                </span>
                <button
                  type="button"
                  onClick={(e) => handleDelete(p.id, e)}
                  className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 hover:text-error transition-colors"
                  aria-label={t('Delete', 'Supprimer')}
                >
                  {t('Delete', 'Supprimer')}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
