import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, Loader2, Upload, X, FileText } from 'lucide-react';
import { useLang } from '../contexts/LangContext';
import { auth, projects } from '../services/api';
import StudioInput from '../components/studio/StudioInput';
import StudioTextarea from '../components/studio/StudioTextarea';
import StudioSelect from '../components/studio/StudioSelect';
import StudioRadioGroup from '../components/studio/StudioRadioGroup';
import StudioStepper from '../components/studio/StudioStepper';
import WizardActHeader from '../components/studio/WizardActHeader';
import EnsembleDisplay from '../components/studio/EnsembleDisplay';
import { STUDIO_ENSEMBLE } from '../lib/agents';

type Priority = 'standard' | 'express';

interface WizardData {
  // Act I — The opening
  name: string;
  industry: string;
  salesforce_edition: 'enterprise' | 'unlimited' | 'other';
  user_role: 'admin' | 'consultant' | 'project_lead' | 'other';
  // Act II — The brief
  description: string;
  business_goals: string;
  constraints: string;
  uploaded_file_name: string;
  // Act IV — The schedule
  priority: Priority;
  // Act V — Curtain up
  agreed_terms: boolean;
}

const EMPTY_DATA: WizardData = {
  name: '',
  industry: '',
  salesforce_edition: 'enterprise',
  user_role: 'consultant',
  description: '',
  business_goals: '',
  constraints: '',
  uploaded_file_name: '',
  priority: 'standard',
  agreed_terms: false,
};

const SDS_CREDIT_COST = 800;
const BUILD_CREDIT_COST = 3500;
const EXPRESS_MULTIPLIER = 1.2;

const DRAFT_KEY = (userId: string | number) => `wizard-draft-${userId}`;

interface IndustryOption {
  en: string;
  fr: string;
  value: string;
}

const INDUSTRY_OPTIONS: IndustryOption[] = [
  { en: 'Logistics', fr: 'Logistique', value: 'logistics' },
  { en: 'Pharma', fr: 'Pharma', value: 'pharma' },
  { en: 'Telecom', fr: 'Télécom', value: 'telecom' },
  { en: 'B2B', fr: 'B2B', value: 'b2b' },
  { en: 'Energy', fr: 'Énergie', value: 'energy' },
  { en: 'Retail', fr: 'Retail', value: 'retail' },
  { en: 'Other', fr: 'Autre', value: 'other' },
];

interface BillingTier {
  tier: string;
  available: number;
  included: number;
}

export default function ProjectWizard() {
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId?: string }>();
  const { t, lang } = useLang();

  const [userKey, setUserKey] = useState<string>('anon');
  const [actIndex, setActIndex] = useState(0);
  const [completed, setCompleted] = useState<Set<number>>(new Set());
  const [data, setData] = useState<WizardData>(EMPTY_DATA);
  const [direction, setDirection] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tier, setTier] = useState<BillingTier | null>(null);

  // Identifier l'utilisateur pour la clé de draft localStorage
  useEffect(() => {
    let cancelled = false;
    auth
      .getCurrentUser()
      .then((u) => {
        if (cancelled) return;
        setUserKey(String(u?.id ?? u?.email ?? 'anon'));
      })
      .catch(() => {
        if (!cancelled) setUserKey('anon');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // 1) projet existant via :projectId, 2) draft localStorage, 3) defaults.
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (projectId) {
        try {
          const p = await projects.get(parseInt(projectId, 10));
          if (cancelled) return;
          setData((prev) => ({
            ...prev,
            name: p?.name ?? prev.name,
            description: p?.description ?? prev.description,
            industry: p?.industry ?? prev.industry,
          }));
          return;
        } catch {
          // continue with localStorage
        }
      }
      try {
        const raw = window.localStorage.getItem(DRAFT_KEY(userKey));
        if (raw && !cancelled) {
          const parsed = JSON.parse(raw) as Partial<WizardData>;
          setData((prev) => ({ ...prev, ...parsed }));
        }
      } catch {
        // ignore corrupt draft
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [projectId, userKey]);

  // /api/billing/balance — pour Acte IV
  useEffect(() => {
    let cancelled = false;
    const base = import.meta.env.VITE_API_URL || '';
    fetch(`${base}/api/billing/balance`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token') ?? ''}`,
      },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((b: Record<string, unknown> | null) => {
        if (cancelled || !b) return;
        setTier({
          tier: typeof b.tier === 'string' ? b.tier : 'free',
          available: Number(b.available ?? 0),
          included: Number(b.included_credits ?? 0),
        });
      })
      .catch(() => {
        /* silent fallback */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist draft (uniquement les inputs utilisateur).
  useEffect(() => {
    if (userKey === 'anon') return;
    try {
      window.localStorage.setItem(DRAFT_KEY(userKey), JSON.stringify(data));
    } catch {
      /* quota or disabled storage */
    }
  }, [data, userKey]);

  const update = <K extends keyof WizardData>(key: K, value: WizardData[K]) =>
    setData((prev) => ({ ...prev, [key]: value }));

  // ── Validation par acte ─────────────────────────────────────────────
  const validateAct = (index: number): string | null => {
    if (index === 0) {
      if (!data.name.trim())
        return t('Project name is required.', 'Le nom du projet est requis.');
      if (data.name.trim().length < 3)
        return t('Project name is too short.', 'Le nom du projet est trop court.');
      if (!data.industry) return t('Pick an industry.', 'Sélectionnez un secteur.');
    }
    if (index === 1) {
      if (data.description.trim().length < 20)
        return t(
          'A 20-character description at minimum, please.',
          "Description de 20 caractères minimum, s'il vous plaît.",
        );
      if (data.business_goals.trim().length < 10)
        return t(
          'Tell us at least one outcome you want.',
          'Décrivez au moins un résultat attendu.',
        );
    }
    if (index === 4) {
      if (!data.agreed_terms)
        return t(
          'Agreement to the terms is required to raise the curtain.',
          "L'accord aux conditions est requis pour lever le rideau.",
        );
    }
    return null;
  };

  const goNext = () => {
    const err = validateAct(actIndex);
    if (err) {
      setError(err);
      return;
    }
    setError(null);
    setCompleted((prev) => {
      const next = new Set(prev);
      next.add(actIndex);
      return next;
    });
    setDirection(1);
    setActIndex((i) => Math.min(4, i + 1));
  };

  const goBack = () => {
    setError(null);
    setDirection(-1);
    setActIndex((i) => Math.max(0, i - 1));
  };

  const jumpTo = (idx: number) => {
    if (idx === actIndex) return;
    if (idx < actIndex || completed.has(idx)) {
      setError(null);
      setDirection(idx > actIndex ? 1 : -1);
      setActIndex(idx);
    }
  };

  const handleSubmit = async () => {
    const err = validateAct(4);
    if (err) {
      setError(err);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const businessRequirements = [
        data.description.trim(),
        '\n## Business Goals\n' + data.business_goals.trim(),
        data.constraints.trim()
          ? '\n## Constraints / Non-goals\n' + data.constraints.trim()
          : '',
      ]
        .filter(Boolean)
        .join('\n\n');

      const result = await projects.create({
        name: data.name.trim(),
        description: data.description.trim(),
        salesforce_product:
          data.salesforce_edition === 'enterprise'
            ? 'Sales Cloud'
            : data.salesforce_edition === 'unlimited'
              ? 'Service Cloud'
              : 'Platform',
        organization_type: 'New Implementation',
        industry: data.industry,
        business_requirements: businessRequirements,
        selected_agents: STUDIO_ENSEMBLE.map((a) => a.id),
      });
      try {
        window.localStorage.removeItem(DRAFT_KEY(userKey));
      } catch {
        /* ignore */
      }
      const newId: number | undefined = result?.id ?? result?.project_id;
      if (newId) {
        navigate(`/br-validation/${newId}`);
      } else {
        navigate('/');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t('Submission failed.', "Échec de l'envoi."));
    } finally {
      setSubmitting(false);
    }
  };

  const acts = useMemo(
    () => [
      { id: 'act-1', label: 'Act I', subtitle: t('The opening', "L'ouverture") },
      { id: 'act-2', label: 'Act II', subtitle: t('The brief', 'Le brief') },
      { id: 'act-3', label: 'Act III', subtitle: t('The ensemble', "L'ensemble") },
      { id: 'act-4', label: 'Act IV', subtitle: t('The schedule', 'Le calendrier') },
      { id: 'act-5', label: 'Act V', subtitle: t('Curtain up', 'Lever de rideau') },
    ],
    [t],
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-12">
        {/* Sidebar gauche : stepper + crédits */}
        <aside className="lg:sticky lg:top-24 lg:self-start space-y-10">
          <div>
            <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-4">
              {t('№ 02 · Casting', '№ 02 · Distribution')}
            </p>
            <StudioStepper
              steps={acts}
              currentIndex={actIndex}
              completed={completed}
              onJump={jumpTo}
            />
          </div>

          {tier && (
            <div className="border-t border-bone/5 pt-6">
              <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                {t('Credits', 'Crédits')}
              </p>
              <p className="mt-2 font-mono text-[18px] text-brass">
                {tier.available.toLocaleString()}
              </p>
              <p className="mt-1 font-mono text-[10px] text-bone-4 capitalize">
                {tier.tier} {t('tier', 'palier')}
              </p>
            </div>
          )}
        </aside>

        {/* Contenu droite : acte courant */}
        <section className="min-h-[600px]">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={actIndex}
              custom={direction}
              initial={{ opacity: 0, x: direction * 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -direction * 40 }}
              transition={{ duration: 0.35, ease: 'easeOut' }}
            >
              {actIndex === 0 && <ActOne data={data} update={update} lang={lang} />}
              {actIndex === 1 && <ActTwo data={data} update={update} />}
              {actIndex === 2 && <ActThree />}
              {actIndex === 3 && <ActFour data={data} update={update} tier={tier} />}
              {actIndex === 4 && <ActFive data={data} update={update} acts={acts} />}
            </motion.div>
          </AnimatePresence>

          {/* Footer navigation */}
          <div className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t border-bone/5 pt-6">
            <button
              type="button"
              onClick={goBack}
              disabled={actIndex === 0 || submitting}
              className="inline-flex items-center gap-2 px-4 py-2 font-mono text-[11px] tracking-cta uppercase text-bone-3 hover:text-bone disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              {t('Previous', 'Précédent')}
            </button>

            {error && (
              <p className="flex-1 mx-4 text-center font-mono text-[11px] text-error">
                {error}
              </p>
            )}

            {actIndex < 4 ? (
              <button
                type="button"
                onClick={goNext}
                className="inline-flex items-center gap-2 px-5 py-2.5 border border-brass bg-brass/10 hover:bg-brass/20 transition-colors font-mono text-[11px] tracking-cta uppercase text-brass"
              >
                {t('Continue', 'Continuer')}
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting || !data.agreed_terms}
                className="inline-flex items-center gap-2 px-6 py-3 border border-brass bg-brass text-ink hover:bg-brass-2 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-mono text-[11px] tracking-cta uppercase"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    {t('Raising the curtain…', 'Lever du rideau…')}
                  </>
                ) : (
                  <>{t('◗ Raise the curtain →', '◗ Lever le rideau →')}</>
                )}
              </button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Act I — The opening
// ─────────────────────────────────────────────────────────────────────
interface ActProps {
  data: WizardData;
  update: <K extends keyof WizardData>(key: K, value: WizardData[K]) => void;
}

function ActOne({ data, update, lang }: ActProps & { lang: 'en' | 'fr' }) {
  const { t } = useLang();
  return (
    <>
      <WizardActHeader
        eyebrow={t('Act I · The opening', "Acte I · L'ouverture")}
        title={t('A new project takes shape.', 'Un nouveau projet prend forme.')}
        lede={t(
          'Tell us about the production you are about to commission. The basics, in three short answers.',
          'Dites-nous quelle production vous commandez. Les bases, en trois réponses courtes.',
        )}
      />

      <div className="space-y-6 max-w-2xl">
        <StudioInput
          name="name"
          label={t('Project name', 'Nom du projet')}
          value={data.name}
          onChange={(e) => update('name', e.target.value)}
          placeholder={t(
            'e.g. LogiFleet — Service Cloud',
            'ex. LogiFleet — Service Cloud',
          )}
          autoComplete="off"
        />

        <StudioSelect
          name="industry"
          label={t('Industry', 'Secteur')}
          value={data.industry}
          onChange={(e) => update('industry', e.target.value)}
          placeholder={t('Choose an industry…', 'Choisissez un secteur…')}
          options={INDUSTRY_OPTIONS.map((o) => ({
            value: o.value,
            label: lang === 'fr' ? o.fr : o.en,
          }))}
        />

        <StudioRadioGroup
          name="salesforce_edition"
          label={t('Salesforce edition', 'Édition Salesforce')}
          value={data.salesforce_edition}
          onChange={(v) =>
            update('salesforce_edition', v as WizardData['salesforce_edition'])
          }
          options={[
            { value: 'enterprise', label: 'Enterprise' },
            { value: 'unlimited', label: 'Unlimited' },
            { value: 'other', label: t('Other', 'Autre') },
          ]}
        />

        <StudioRadioGroup
          name="user_role"
          label={t('Your role', 'Votre rôle')}
          value={data.user_role}
          onChange={(v) => update('user_role', v as WizardData['user_role'])}
          options={[
            { value: 'admin', label: t('Salesforce admin', 'Admin Salesforce') },
            { value: 'consultant', label: t('Consultant', 'Consultant·e') },
            { value: 'project_lead', label: t('Project lead', 'Chef·fe de projet') },
            { value: 'other', label: t('Other', 'Autre') },
          ]}
        />
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Act II — The brief
// ─────────────────────────────────────────────────────────────────────
function ActTwo({ data, update }: ActProps) {
  const { t } = useLang();
  const [dragOver, setDragOver] = useState(false);

  const onPickFile = (file: File | null) => {
    update('uploaded_file_name', file ? file.name : '');
  };

  return (
    <>
      <WizardActHeader
        eyebrow={t('Act II · The brief', 'Acte II · Le brief')}
        title={t('What needs to be built.', 'Ce qui doit être construit.')}
        lede={t(
          'Describe the project, the business outcomes, and any constraint we should respect. The longer, the sharper the SDS.',
          "Décrivez le projet, les résultats attendus, et toute contrainte à respecter. Plus c'est précis, plus le SDS est juste.",
        )}
      />

      <div className="space-y-6 max-w-2xl">
        <StudioTextarea
          name="description"
          label={t('Project description', 'Description du projet')}
          rows={5}
          value={data.description}
          onChange={(e) => update('description', e.target.value)}
          placeholder={t(
            'What is the engagement? Context, scope, key actors…',
            'Quelle est la mission ? Contexte, périmètre, acteurs clés…',
          )}
        />

        <StudioTextarea
          name="business_goals"
          label={t('Business goals', 'Objectifs business')}
          rows={4}
          value={data.business_goals}
          onChange={(e) => update('business_goals', e.target.value)}
          placeholder={t(
            'What outcome should this unlock for your business?',
            'Quels résultats cette mission doit-elle débloquer ?',
          )}
        />

        <StudioTextarea
          name="constraints"
          label={t(
            'Constraints / non-goals (optional)',
            'Contraintes / hors-périmètre (optionnel)',
          )}
          rows={3}
          value={data.constraints}
          onChange={(e) => update('constraints', e.target.value)}
          placeholder={t(
            'Anything we must avoid, defer, or comply with?',
            'À éviter, à différer, ou à respecter ?',
          )}
        />

        <div>
          <p className="block font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-2">
            {t('Brief PDF (optional)', 'Brief PDF (optionnel)')}
          </p>
          <label
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files?.[0];
              if (f) onPickFile(f);
            }}
            className={[
              'block border border-dashed bg-ink-2 px-6 py-8 cursor-pointer transition-colors',
              dragOver
                ? 'border-brass bg-ink-3'
                : 'border-bone/15 hover:border-brass/40',
            ].join(' ')}
          >
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
            />
            {data.uploaded_file_name ? (
              <span className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-3 min-w-0">
                  <FileText className="w-4 h-4 text-brass shrink-0" />
                  <span className="font-mono text-[12px] text-bone truncate">
                    {data.uploaded_file_name}
                  </span>
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    onPickFile(null);
                  }}
                  aria-label={t('Remove file', 'Retirer le fichier')}
                  className="p-1 text-bone-4 hover:text-error transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </span>
            ) : (
              <span className="flex items-center gap-3">
                <Upload className="w-4 h-4 text-bone-3" />
                <span className="font-mono text-[11px] tracking-[0.05em] text-bone-3">
                  {t(
                    'Drop a brief PDF here, or click to browse.',
                    'Déposez un PDF ici, ou cliquez pour parcourir.',
                  )}
                </span>
              </span>
            )}
          </label>
          <p className="mt-2 font-mono text-[11px] text-bone-4">
            {t(
              'Optional — Sophie will read it during the casting.',
              'Optionnel — Sophie le lira pendant le casting.',
            )}
          </p>
        </div>
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Act III — The ensemble (read-only)
// ─────────────────────────────────────────────────────────────────────
function ActThree() {
  const { t } = useLang();
  return (
    <>
      <WizardActHeader
        eyebrow={t('Act III · The ensemble', "Acte III · L'ensemble")}
        title={t('Eleven specialists. One studio.', 'Onze spécialistes. Un seul studio.')}
        lede={t(
          'You do not pick the cast — every project earns the full ensemble. They take the stage in turn.',
          "Vous ne choisissez pas la distribution — chaque projet a droit à l'ensemble complet. Ils entrent en scène tour à tour.",
        )}
      />
      <EnsembleDisplay />
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Act IV — The schedule
// ─────────────────────────────────────────────────────────────────────
function ActFour({
  data,
  update,
  tier,
}: ActProps & { tier: BillingTier | null }) {
  const { t } = useLang();
  const baseSds = SDS_CREDIT_COST;
  const baseBuild = BUILD_CREDIT_COST;
  const multiplier = data.priority === 'express' ? EXPRESS_MULTIPLIER : 1;
  const totalEstimate = Math.round((baseSds + baseBuild) * multiplier);

  return (
    <>
      <WizardActHeader
        eyebrow={t('Act IV · The schedule', 'Acte IV · Le calendrier')}
        title={t('When and how much.', 'Quand et combien.')}
        lede={t(
          'We estimate the credits and pace. Express adds 20% to the bill but moves you to the head of the queue.',
          "Estimation des crédits et du rythme. L'express ajoute 20 % à la facture mais vous place en tête de file.",
        )}
      />

      <div className="space-y-8 max-w-2xl">
        <div className="border border-bone/10 bg-ink-2 px-5 py-4 grid grid-cols-2 gap-4">
          <div>
            <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
              {t('Your tier', 'Votre palier')}
            </p>
            <p className="mt-2 font-serif italic text-xl text-bone capitalize">
              {tier?.tier ?? '—'}
            </p>
          </div>
          <div>
            <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
              {t('Available credits', 'Crédits disponibles')}
            </p>
            <p className="mt-2 font-mono text-xl text-brass">
              {tier ? tier.available.toLocaleString() : '—'}
            </p>
          </div>
        </div>

        <div className="border border-bone/10 bg-ink-2 px-5 py-4">
          <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
            {t('Estimated cost in credits', 'Coût estimé en crédits')}
          </p>
          <p className="mt-2 font-mono text-2xl text-brass">
            ~ {totalEstimate.toLocaleString()}
          </p>
          <p className="mt-2 font-mono text-[11px] text-bone-3 leading-relaxed">
            {t(
              `SDS phase ~${baseSds.toLocaleString()} · BUILD phase ~${baseBuild.toLocaleString()}`,
              `Phase SDS ~${baseSds.toLocaleString()} · Phase BUILD ~${baseBuild.toLocaleString()}`,
            )}
            {data.priority === 'express' && t(' · Express +20%', ' · Express +20 %')}
          </p>
        </div>

        <StudioRadioGroup
          name="priority"
          label={t('Priority', 'Priorité')}
          value={data.priority}
          onChange={(v) => update('priority', v as Priority)}
          options={[
            {
              value: 'standard',
              label: t('Standard', 'Standard'),
              description: t('Estimated 5–7 working days.', 'Délai estimé 5 à 7 jours ouvrés.'),
            },
            {
              value: 'express',
              label: t('Express', 'Express'),
              description: t(
                '+20% credits · Estimated 2–3 working days.',
                '+20 % de crédits · Délai estimé 2 à 3 jours ouvrés.',
              ),
            },
          ]}
        />

        <p className="font-mono text-[11px] text-bone-4">
          {t(
            'Estimated completion is indicative — Sophie will refine it during BR validation.',
            "L'estimation est indicative — Sophie l'affinera pendant la validation des BR.",
          )}
        </p>
      </div>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Act V — Curtain up
// ─────────────────────────────────────────────────────────────────────
function ActFive({
  data,
  update,
  acts,
}: ActProps & { acts: { id: string; label: string; subtitle: string }[] }) {
  const { t } = useLang();

  const summary: { label: string; value: string }[] = [
    { label: t('Project name', 'Nom du projet'), value: data.name || '—' },
    { label: t('Industry', 'Secteur'), value: data.industry || '—' },
    {
      label: t('Salesforce edition', 'Édition Salesforce'),
      value: data.salesforce_edition,
    },
    {
      label: t('Priority', 'Priorité'),
      value:
        data.priority === 'express' ? t('Express', 'Express') : t('Standard', 'Standard'),
    },
    {
      label: t('Brief excerpt', 'Extrait du brief'),
      value:
        data.description.length > 140
          ? `${data.description.slice(0, 140).trim()}…`
          : data.description || '—',
    },
  ];

  return (
    <>
      <WizardActHeader
        eyebrow={t('Act V · Curtain up', 'Acte V · Lever de rideau')}
        title={t(
          'One last look before the lights go up.',
          "Un dernier regard avant l'éclairage.",
        )}
        lede={t(
          'Sophie will read your brief, draft a list of business requirements, then hand it back to you for validation.',
          "Sophie lira votre brief, rédigera une liste de business requirements, puis vous la rendra pour validation.",
        )}
      />

      <div className="space-y-8 max-w-2xl">
        <div className="border border-bone/10 bg-ink-2 divide-y divide-bone/5">
          {summary.map((row) => (
            <div key={row.label} className="flex items-baseline gap-4 px-5 py-3">
              <p className="w-48 font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 shrink-0">
                {row.label}
              </p>
              <p className="font-sans text-[13px] text-bone leading-snug">{row.value}</p>
            </div>
          ))}
        </div>

        <p className="font-mono text-[11px] text-bone-3">
          {t(
            `${acts.length} acts ahead — your ensemble is ready.`,
            `${acts.length} actes à venir — votre ensemble est prêt.`,
          )}
        </p>

        <label className="flex items-start gap-3 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={data.agreed_terms}
            onChange={(e) => update('agreed_terms', e.target.checked)}
            className="sr-only peer"
          />
          <span
            aria-hidden
            className="mt-[2px] inline-flex w-4 h-4 border border-bone/30 peer-checked:border-brass peer-checked:bg-brass transition-colors items-center justify-center"
          >
            {data.agreed_terms && <span className="w-2 h-2 bg-ink" />}
          </span>
          <span className="font-mono text-[12px] text-bone-2 leading-relaxed">
            {t(
              'I agree to the terms of service and authorise the studio to begin the production.',
              "J'accepte les conditions de service et autorise le studio à commencer la production.",
            )}
          </span>
        </label>
      </div>
    </>
  );
}
