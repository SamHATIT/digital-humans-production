import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Loader2 } from 'lucide-react';
import { executions, projects } from '../services/api';
import { useLang } from '../contexts/LangContext';
import WizardActHeader from '../components/studio/WizardActHeader';
import { ACCENT_BORDER, ACCENT_TEXT, type AccentToken } from '../lib/agents';

interface Project {
  id: number;
  name: string;
  description?: string;
  business_requirements?: string;
  salesforce_product?: string;
  organization_type?: string;
  status: string;
  selected_agents?: string[];
}

interface PhaseCardProps {
  index: '01' | '02';
  eyebrow: { en: string; fr: string };
  title: { en: string; fr: string };
  lede: { en: string; fr: string };
  estimate: { en: string; fr: string };
  accent: AccentToken;
  ready: boolean;
  ctaLabel?: { en: string; fr: string };
  onCta?: () => void;
  loading?: boolean;
  hint?: { en: string; fr: string };
}

function PhaseCard({
  index,
  eyebrow,
  title,
  lede,
  estimate,
  accent,
  ready,
  ctaLabel,
  onCta,
  loading,
  hint,
}: PhaseCardProps) {
  const { t } = useLang();
  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className={[
        'relative bg-ink-2 border p-7 md:p-9 flex flex-col',
        ACCENT_BORDER[accent],
        ready ? 'opacity-100' : 'opacity-60',
      ].join(' ')}
    >
      <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
        № {index}
      </p>
      <p className={`mt-2 font-mono text-[10px] tracking-eyebrow uppercase ${ACCENT_TEXT[accent]}`}>
        {t(eyebrow.en, eyebrow.fr)}
      </p>
      <h3 className="mt-3 font-serif italic text-3xl text-bone leading-tight">
        {t(title.en, title.fr)}
      </h3>
      <p className="mt-4 font-mono text-[12px] text-bone-3 leading-relaxed">
        {t(lede.en, lede.fr)}
      </p>

      <div className="mt-6 flex items-center justify-between border-t border-bone/10 pt-4">
        <span className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
          {t(estimate.en, estimate.fr)}
        </span>
        <span
          className={[
            'font-mono text-[10px] tracking-eyebrow uppercase',
            ready ? ACCENT_TEXT[accent] : 'text-bone-4',
          ].join(' ')}
        >
          {ready
            ? t('Ready', 'Prêt')
            : t('Pending SDS', 'En attente du SDS')}
        </span>
      </div>

      {ctaLabel && onCta && (
        <button
          type="button"
          onClick={onCta}
          disabled={!ready || !!loading}
          className={[
            'mt-6 self-start inline-flex items-center gap-3 px-6 py-3 font-mono text-[11px] tracking-cta uppercase transition-colors',
            ready
              ? 'bg-brass text-ink hover:bg-brass-2 disabled:opacity-50'
              : 'bg-ink-3 text-bone-4 cursor-not-allowed',
          ].join(' ')}
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
          {loading ? t('Curtain rising…', 'Le rideau se lève…') : t(ctaLabel.en, ctaLabel.fr)}
          {!loading && <ArrowRight className="w-3.5 h-3.5" />}
        </button>
      )}

      {hint && (
        <p className="mt-4 font-mono text-[10px] text-bone-4 leading-relaxed">
          {t(hint.en, hint.fr)}
        </p>
      )}
    </motion.article>
  );
}

export default function ExecutionPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { t, lang } = useLang();

  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    projects
      .get(Number(projectId))
      .then((data) => {
        if (!cancelled) setProject(data);
      })
      .catch((err) => {
        console.error('Failed to fetch project:', err);
        if (!cancelled) setError(err?.message || 'Failed to load project');
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const handleBegin = async () => {
    if (!project) return;
    setIsStarting(true);
    setError('');
    try {
      const agents = project.selected_agents && project.selected_agents.length > 0
        ? project.selected_agents
        : [
            'pm',
            'ba',
            'research_analyst',
            'architect',
            'apex',
            'lwc',
            'admin',
            'qa',
            'devops',
            'data',
            'trainer',
          ];
      const result = await executions.start(project.id, agents);
      navigate(`/execution/${result.execution_id}/monitor`);
    } catch (err: any) {
      setError(
        err?.detail
          ? typeof err.detail === 'string'
            ? err.detail
            : JSON.stringify(err.detail)
          : err?.message || 'Failed to start execution',
      );
    } finally {
      setIsStarting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-brass animate-spin" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <p className="font-serif italic text-bone-3">
          {t('Project not found.', 'Projet introuvable.')}
        </p>
      </div>
    );
  }

  const projectName = project.name || 'Untitled';

  return (
    <div className="bg-ink min-h-[calc(100vh-4rem)]">
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
        <WizardActHeader
          eyebrow={t('No 04 · Curtain Up', 'Nº 04 · Le rideau se lève')}
          title={t('The ensemble takes the stage', 'L’ensemble entre en scène')}
          lede={
            lang === 'fr' ? (
              <>
                Le brief est validé. <span className="text-bone">{projectName}</span> est sur la
                scène. Choisissez l’acte qui s’ouvre&nbsp;: l’écriture du SDS, ou plus tard le BUILD.
              </>
            ) : (
              <>
                The brief is approved. <span className="text-bone">{projectName}</span> stands at the
                edge of the stage. Open the curtain on the SDS now — BUILD waits in the wings.
              </>
            )
          }
        />

        {error && (
          <div className="mb-8 border border-error/40 bg-error/10 px-4 py-3 font-mono text-[12px] text-error">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <PhaseCard
            index="01"
            accent="plum"
            ready
            eyebrow={{ en: 'Act II · Visionaries', fr: 'Acte II · Visionnaires' }}
            title={{
              en: 'Specifications · The SDS',
              fr: 'Spécifications · Le SDS',
            }}
            lede={{
              en: 'Sophie, Olivia, Emma and Marcus rehearse the brief, draw the architecture and write the SDS document.',
              fr: 'Sophie, Olivia, Emma et Marcus relisent le brief, dessinent l’architecture et rédigent le SDS.',
            }}
            estimate={{
              en: '≈ $0.11 · 3 to 5 minutes',
              fr: '≈ 0,11 $ · 3 à 5 minutes',
            }}
            ctaLabel={{ en: 'Begin SDS', fr: 'Lancer le SDS' }}
            onCta={handleBegin}
            loading={isStarting}
          />
          <PhaseCard
            index="02"
            accent="terra"
            ready={false}
            eyebrow={{ en: 'Act III · Builders', fr: 'Acte III · Bâtisseurs' }}
            title={{
              en: 'Construction · The BUILD',
              fr: 'Construction · Le BUILD',
            }}
            lede={{
              en: 'Diego, Zara and Raj turn the SDS into Apex, LWC and admin configuration ready for deployment.',
              fr: 'Diego, Zara et Raj transforment le SDS en Apex, LWC et configuration prêts au déploiement.',
            }}
            estimate={{
              en: '≈ $0.40 · 6 to 12 minutes',
              fr: '≈ 0,40 $ · 6 à 12 minutes',
            }}
            hint={{
              en: 'BUILD opens after the SDS has been approved.',
              fr: 'Le BUILD s’ouvre après validation du SDS.',
            }}
          />
        </div>

        {project.business_requirements && (
          <section className="mt-12">
            <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
              {t('Notes from the brief', 'Notes du brief')}
            </p>
            <p className="mt-3 font-serif italic text-bone-3 text-[15px] leading-relaxed max-h-40 overflow-y-auto border-l-2 border-bone/15 pl-4">
              {project.business_requirements}
            </p>
          </section>
        )}
      </main>
    </div>
  );
}
