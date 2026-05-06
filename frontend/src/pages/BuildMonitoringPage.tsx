/**
 * BuildMonitoringPage — Theatre · Act III · Builders
 *
 * Layout 2-pane (validé sur mockup_v1) :
 *  - Sidebar sticky (Stage Progress + interactive Score timeline + Hands at Work)
 *  - Right pane (Curtain rising hero + Live Preview + Detail view piloté par
 *    la sélection de la sidebar : phase OU agent).
 *
 * La timeline et la liste des agents sont cliquables : la sélection met à jour
 * `focus` qui pilote l'affichage du Detail view dans la colonne droite.
 *
 * Photos d'agents : `/avatars/small/<slug>.png` (sidebar) + `/avatars/large/`
 * (hero) — fournies par le studio nginx (root /var/www/app-studio).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Download,
  AlertCircle,
  CheckCircle,
  Clock,
} from 'lucide-react';
import { api, executions } from '../services/api';
import { useLang } from '../contexts/LangContext';
import {
  BUILD_STEPS,
  STUDIO_ENSEMBLE,
  findAgentByLabel,
  getAgentById,
  getAgentAvatar,
  ACCENT_TEXT,
  ACCENT_BORDER,
  type AccentToken,
} from '../lib/agents';
import AgentStage from '../components/studio/AgentStage';
import AgentLivePreview from '../components/studio/AgentLivePreview';
import CurtainOverlay from '../components/studio/CurtainOverlay';
import type { PhaseExecution } from '../components/BuildPhasesPanel';
import { useExecutionTracker } from '../contexts/ExecutionTrackerContext';

// ─── Types ─────────────────────────────────────────────────────────

interface TaskInfo {
  task_id: string;
  task_name: string;
  phase_name: string;
  assigned_agent: string;
  status: string;
  attempt_count: number;
  last_error?: string;
  started_at?: string;
  completed_at?: string;
  git_commit_sha?: string;
}

interface BuildPhaseStats {
  total_tasks: number;
  completed: number;
  running: number;
  failed: number;
  pending: number;
  progress_percent: number;
}

interface BuildTasksResponse {
  execution_id: number;
  execution_status: string;
  build_phase: BuildPhaseStats;
  tasks_by_agent: Record<string, TaskInfo[]>;
  all_tasks: TaskInfo[];
  metadata?: any;
}

/** What the right pane focuses on. */
type Focus =
  | { type: 'phase'; phase: number }
  | { type: 'agent'; agentId: string };

const PHASE_NUMBERS = [1, 2, 3, 4, 5, 6];

// ─── Helpers ───────────────────────────────────────────────────────

function formatDuration(start?: string, end?: string): string {
  if (!start) return '—';
  const startDate = new Date(start);
  const endDate = end ? new Date(end) : new Date();
  const seconds = Math.floor((endDate.getTime() - startDate.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}

type TimelineStatus = 'pending' | 'current' | 'completed' | 'failed';

function timelineStatusFromPhase(p?: PhaseExecution): TimelineStatus {
  if (!p) return 'pending';
  const s = p.status?.toLowerCase();
  if (s === 'completed') return 'completed';
  if (s === 'failed') return 'failed';
  if (s === 'pending' || !s) return 'pending';
  return 'current';
}

function timelineStatusFromTasks(tasks: TaskInfo[]): TimelineStatus {
  if (!tasks || tasks.length === 0) return 'pending';
  if (tasks.some((t) => t.status === 'failed')) return 'failed';
  const completed = tasks.filter(
    (t) => t.status === 'completed' || t.status === 'passed',
  ).length;
  if (completed === tasks.length) return 'completed';
  if (
    tasks.some((t) =>
      ['running', 'deploying', 'committing', 'testing', 'generating'].includes(t.status),
    )
  ) {
    return 'current';
  }
  return 'pending';
}

// ─── Page ──────────────────────────────────────────────────────────

export default function BuildMonitoringPage() {
  const { executionId } = useParams<{ executionId: string }>();
  const navigate = useNavigate();
  const { t } = useLang();

  const [data, setData] = useState<BuildTasksResponse | null>(null);
  const [phases, setPhases] = useState<PhaseExecution[]>([]);
  const [currentPhaseNumber, setCurrentPhaseNumber] = useState<number | undefined>();
  const [focus, setFocus] = useState<Focus | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [isActioning, setIsActioning] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ─── Track this execution so the header CreditCounter shows elapsed.
  const { setActiveExecution } = useExecutionTracker();
  useEffect(() => {
    const id = executionId ? Number(executionId) : undefined;
    if (!id) return;
    const key = `dh_exec_started_${id}`;
    const status = (data?.execution_status || '').toLowerCase();
    let startedAt = window.localStorage.getItem(key);
    const isLive = !!data && status !== 'completed' && status !== 'failed' && status !== 'cancelled';
    if (isLive && !startedAt) {
      startedAt = new Date().toISOString();
      window.localStorage.setItem(key, startedAt);
    }
    if (isLive && startedAt) {
      setActiveExecution({ executionId: id, startedAt });
    } else if (!isLive) {
      setActiveExecution(null);
      if (status === 'completed' || status === 'failed' || status === 'cancelled') {
        window.localStorage.removeItem(key);
      }
    }
    return () => setActiveExecution(null);
  }, [executionId, data, setActiveExecution]);

  const fetchTasks = async () => {
    if (!executionId) return;
    try {
      const response = await api.get(
        `/api/pm-orchestrator/execute/${executionId}/build-tasks`,
      );
      setData(response);
      setIsPaused(
        response?.execution_status === 'paused' ||
          response?.metadata?.build_paused === true,
      );
      if (
        response?.execution_status === 'COMPLETED' ||
        response?.execution_status === 'FAILED'
      ) {
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      }
    } catch (err: any) {
      if (!data) setError(err?.message || 'Failed to load build tasks');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchPhases = async () => {
    if (!executionId) return;
    try {
      const response = await api.get(
        `/api/pm-orchestrator/execute/${executionId}/build-phases`,
      );
      setPhases(response?.phases || []);
      setCurrentPhaseNumber(response?.current_phase);
    } catch {
      // BUILD v2 may not be active — silent.
    }
  };

  useEffect(() => {
    fetchTasks();
    fetchPhases();
    pollingRef.current = setInterval(() => {
      fetchTasks();
      fetchPhases();
    }, 3000);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [executionId]);

  // Default focus = current running phase, otherwise phase 1.
  useEffect(() => {
    if (focus !== null) return;
    if (currentPhaseNumber) {
      setFocus({ type: 'phase', phase: currentPhaseNumber });
    } else if (phases.length > 0) {
      setFocus({ type: 'phase', phase: phases[0].phase_number });
    } else {
      setFocus({ type: 'phase', phase: 1 });
    }
  }, [currentPhaseNumber, phases, focus]);

  const tasksByAgent = data?.tasks_by_agent || {};
  const allTasks = data?.all_tasks || [];
  const stats = data?.build_phase;
  const status = (data?.execution_status || '').toLowerCase();

  const runningTask = allTasks.find((t) =>
    ['running', 'deploying', 'committing', 'testing', 'generating'].includes(t.status),
  );
  const runningAgent = runningTask
    ? findAgentByLabel(runningTask.assigned_agent) ?? getAgentById(runningTask.assigned_agent)
    : null;

  const stage: 'idle' | 'active' | 'completed' | 'failed' | 'waiting' =
    status === 'completed'
      ? 'completed'
      : status === 'failed'
        ? 'failed'
        : isPaused
          ? 'waiting'
          : runningTask
            ? 'active'
            : 'idle';

  const phaseStatus = useMemo(() => {
    const map = new Map<number, TimelineStatus>();
    PHASE_NUMBERS.forEach((n) => map.set(n, 'pending'));
    phases.forEach((p) => map.set(p.phase_number, timelineStatusFromPhase(p)));
    if (phases.length === 0) {
      BUILD_STEPS.forEach((step, idx) => {
        const tk = tasksByAgent[step.agentId] || [];
        map.set(PHASE_NUMBERS[idx], timelineStatusFromTasks(tk));
      });
    }
    return map;
  }, [phases, tasksByAgent]);

  const handlePause = async () => {
    if (!executionId) return;
    setIsActioning(true);
    try {
      await api.post(`/api/pm-orchestrator/execute/${executionId}/pause-build`);
      setIsPaused(true);
    } catch (err: any) {
      setError(err?.message || 'Failed to pause');
    } finally {
      setIsActioning(false);
    }
  };

  const handleResume = async () => {
    if (!executionId) return;
    setIsActioning(true);
    try {
      await api.post(`/api/pm-orchestrator/execute/${executionId}/resume-build`);
      setIsPaused(false);
    } catch (err: any) {
      setError(err?.message || 'Failed to resume');
    } finally {
      setIsActioning(false);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-ink min-h-[calc(100vh-4rem)] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-6 h-6 text-terra animate-spin mx-auto" />
          <p className="mt-4 font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
            {t('Backstage warming up…', 'En coulisses…')}
          </p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="bg-ink min-h-[calc(100vh-4rem)] flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-6 h-6 text-error mx-auto" />
          <p className="mt-3 font-serif italic text-bone-3">{error}</p>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="mt-4 inline-flex items-center gap-2 px-5 py-2 border border-bone/15 text-bone-3 hover:text-bone hover:border-bone/30 font-mono text-[10px] tracking-cta uppercase"
          >
            {t('Go back', 'Retour')}
          </button>
        </div>
      </div>
    );
  }

  // Focus resolution → hero + live preview + detail view
  const focusedPhase: PhaseExecution | undefined =
    focus?.type === 'phase'
      ? phases.find((p) => p.phase_number === focus.phase)
      : undefined;

  const focusedPhaseStep =
    focus?.type === 'phase' ? BUILD_STEPS[focus.phase - 1] : undefined;

  const focusedAgent =
    focus?.type === 'agent'
      ? getAgentById(focus.agentId)
      : focusedPhaseStep
        ? getAgentById(focusedPhaseStep.agentId)
        : null;

  const heroAgent = runningAgent ?? focusedAgent;
  const heroAccent: AccentToken = (heroAgent?.accent as AccentToken) ?? 'terra';

  const focusedTasks: TaskInfo[] = (() => {
    if (!focus) return [];
    if (focus.type === 'phase') {
      const step = BUILD_STEPS[focus.phase - 1];
      if (!step) return [];
      const list = tasksByAgent[step.agentId] || [];
      return list.filter(
        (tk) =>
          tk.phase_name?.toLowerCase().includes(`phase ${focus.phase}`) ||
          !tk.phase_name,
      );
    }
    return tasksByAgent[focus.agentId] || [];
  })();

  return (
    <div className="bg-ink min-h-[calc(100vh-4rem)]">
      <CurtainOverlay
        storageKey={`build-${executionId}`}
        eyebrow={t('No 04 · BUILD', 'Nº 04 · BUILD')}
        title={{
          en: 'The builders take the stage',
          fr: 'Les bâtisseurs entrent en scène',
        }}
      />

      <main className="max-w-[1480px] mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-14">
        <header className="mb-8 pb-6 border-b border-bone/10 flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <p className={`font-mono text-[11px] tracking-eyebrow uppercase ${ACCENT_TEXT['terra']}`}>
              {t('Act III · Builders', 'Acte III · Bâtisseurs')}
            </p>
            <h1 className="mt-3 font-serif italic text-bone text-[34px] md:text-[42px] leading-tight">
              {t(
                'Construction of the Salesforce stage',
                'Construction de la scène Salesforce',
              )}
            </h1>
            <p className="mt-2 font-mono text-[12px] text-bone-3 leading-relaxed">
              {t(
                `Execution # ${executionId} · ${data?.execution_status ?? 'pending'}`,
                `Exécution nº ${executionId} · ${data?.execution_status ?? 'en attente'}`,
              )}
            </p>
          </div>

          <div className="flex items-center gap-3">
            {(status === 'running' || status === 'building') && (
              isPaused ? (
                <button
                  type="button"
                  onClick={handleResume}
                  disabled={isActioning}
                  className="inline-flex items-center gap-2 px-5 py-2 bg-sage text-ink hover:bg-sage/80 font-mono text-[10px] tracking-cta uppercase disabled:opacity-50"
                >
                  <Play className="w-3.5 h-3.5" />
                  {t('Resume', 'Reprendre')}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handlePause}
                  disabled={isActioning}
                  className="inline-flex items-center gap-2 px-5 py-2 bg-warning text-ink hover:bg-warning/80 font-mono text-[10px] tracking-cta uppercase disabled:opacity-50"
                >
                  <Pause className="w-3.5 h-3.5" />
                  {t('Pause', 'Pause')}
                </button>
              )
            )}
            <button
              type="button"
              onClick={() => { fetchTasks(); fetchPhases(); }}
              className="inline-flex items-center gap-2 px-4 py-2 border border-bone/15 text-bone-3 hover:text-bone hover:border-bone/30 font-mono text-[10px] tracking-eyebrow uppercase"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              {t('Refresh', 'Actualiser')}
            </button>
            {status === 'completed' && executionId && (
              <button
                type="button"
                onClick={() => window.open(executions.getSdsHtmlUrl(Number(executionId)), '_blank')}
                className="inline-flex items-center gap-2 px-5 py-2 bg-brass text-ink hover:bg-brass-2 font-mono text-[10px] tracking-cta uppercase"
              >
                <Download className="w-3.5 h-3.5" />
                {t('View SDS →', 'Voir le SDS →')}
              </button>
            )}
          </div>
        </header>

        {error && (
          <div className="mb-8 border border-error/40 bg-error/10 px-4 py-3 font-mono text-[12px] text-error">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6 items-start">

          {/* ─── Sidebar (sticky) ─── */}
          <aside className="lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto flex flex-col gap-4 pr-1">

            {/* Stage progress */}
            {stats && (
              <section className="bg-ink-2 border border-bone/10">
                <header className="px-4 py-2.5 border-b border-bone/10 flex items-center justify-between">
                  <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                    {t('Stage Progress', 'Avancement')}
                  </p>
                  {stage === 'active' && (
                    <span className="inline-flex items-center gap-1.5 font-mono text-[9px] tracking-eyebrow uppercase text-brass">
                      <span className="w-1 h-1 rounded-full bg-brass animate-pulse" />
                      {t('live', 'live')}
                    </span>
                  )}
                </header>
                <div className="px-4 py-4">
                  <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                    {t('Overall', 'Total')}
                  </p>
                  <p className="mt-1 font-serif text-2xl text-bone">{stats.progress_percent}%</p>
                  <div className="mt-2 h-[2px] bg-bone/10 overflow-hidden">
                    <motion.div
                      className="h-full bg-terra"
                      initial={{ width: 0 }}
                      animate={{ width: `${stats.progress_percent}%` }}
                      transition={{ duration: 0.4, ease: 'easeOut' }}
                    />
                  </div>
                  <dl className="grid grid-cols-2 gap-3.5 mt-4">
                    <div>
                      <dt className="font-mono text-[9px] tracking-eyebrow uppercase text-bone-4">{t('Done', 'Faits')}</dt>
                      <dd className="mt-0.5 font-serif text-lg text-sage">{stats.completed}</dd>
                    </div>
                    <div>
                      <dt className="font-mono text-[9px] tracking-eyebrow uppercase text-bone-4">{t('Running', 'En cours')}</dt>
                      <dd className="mt-0.5 font-serif text-lg text-brass">{stats.running}</dd>
                    </div>
                    <div>
                      <dt className="font-mono text-[9px] tracking-eyebrow uppercase text-bone-4">{t('Failed', 'Échecs')}</dt>
                      <dd className="mt-0.5 font-serif text-lg text-error">{stats.failed}</dd>
                    </div>
                    <div>
                      <dt className="font-mono text-[9px] tracking-eyebrow uppercase text-bone-4">{t('Pending', 'À faire')}</dt>
                      <dd className="mt-0.5 font-serif text-lg text-bone-4">{stats.pending}</dd>
                    </div>
                  </dl>
                </div>
              </section>
            )}

            {/* The Score (interactive timeline) */}
            <section className="bg-ink-2 border border-bone/10">
              <header className="px-4 py-2.5 border-b border-bone/10">
                <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                  {t('BUILD · The Score', 'BUILD · La Partition')}
                </p>
              </header>
              <ul className="py-1">
                {BUILD_STEPS.map((step, idx) => {
                  const phaseNum = PHASE_NUMBERS[idx];
                  const ps = phaseStatus.get(phaseNum) ?? 'pending';
                  const agent = getAgentById(step.agentId);
                  const isActive = focus?.type === 'phase' && focus.phase === phaseNum;
                  const borderClass = isActive
                    ? 'border-l-terra bg-terra/[0.07]'
                    : ps === 'completed' ? 'border-l-sage'
                    : ps === 'failed' ? 'border-l-error'
                    : ps === 'current' ? 'border-l-brass'
                    : 'border-l-transparent';
                  const badgeClass =
                    ps === 'current' ? 'text-brass border-brass'
                    : ps === 'completed' ? 'text-sage border-sage'
                    : ps === 'failed' ? 'text-error border-error'
                    : 'text-bone-4 border-bone/15';
                  return (
                    <li key={step.id}>
                      <button
                        type="button"
                        onClick={() => setFocus({ type: 'phase', phase: phaseNum })}
                        className={`w-full text-left px-4 py-2.5 border-l-2 transition-colors hover:bg-bone/[0.025] relative ${borderClass}`}
                      >
                        <span className={`absolute top-2.5 right-3 inline-block px-1.5 py-0.5 border font-mono text-[8px] tracking-eyebrow uppercase ${badgeClass}`}>
                          {ps === 'current' ? t('Running', 'En cours')
                            : ps === 'completed' ? t('Done', 'Faite')
                            : ps === 'failed' ? t('Failed', 'Échec')
                            : t('Pending', 'En attente')}
                        </span>
                        <p className="font-mono text-[9px] tracking-eyebrow uppercase text-bone-4">
                          {`Phase 0${phaseNum}`}
                        </p>
                        <p className="mt-0.5 font-serif italic text-[15px] text-bone-2 leading-tight">
                          {t(step.label.en.replace(/^Phase \d+ · /, ''), step.label.fr.replace(/^Phase \d+ · /, ''))}
                        </p>
                        <p className="mt-1 font-mono text-[10px] text-bone-4">
                          {agent?.name.en}
                        </p>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>

            {/* Hands at Work (interactive agents) */}
            <section className="bg-ink-2 border border-bone/10">
              <header className="px-4 py-2.5 border-b border-bone/10">
                <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                  {t('Hands at Work', "À l'ouvrage")}
                </p>
              </header>
              <ul>
                {STUDIO_ENSEMBLE.filter((a) =>
                  ['admin', 'apex', 'lwc', 'qa', 'devops', 'data'].includes(a.id),
                ).map((agent) => {
                  const tasks = tasksByAgent[agent.id] || [];
                  const completed = tasks.filter(
                    (tk) => tk.status === 'completed' || tk.status === 'passed',
                  ).length;
                  const running = tasks.filter((tk) =>
                    ['running', 'deploying', 'committing', 'testing', 'generating'].includes(tk.status),
                  ).length;
                  const total = tasks.length;
                  const pct = total > 0 ? (completed / total) * 100 : 0;
                  const isActive = focus?.type === 'agent' && focus.agentId === agent.id;
                  const borderClass = isActive
                    ? 'border-l-terra bg-terra/[0.07]'
                    : 'border-l-transparent';
                  return (
                    <li key={agent.id}>
                      <button
                        type="button"
                        onClick={() => setFocus({ type: 'agent', agentId: agent.id })}
                        className={`w-full text-left flex items-center gap-3 px-4 py-2.5 border-l-2 transition-colors hover:bg-bone/[0.025] ${borderClass}`}
                      >
                        <img
                          src={getAgentAvatar(agent.id, 'small')}
                          alt={agent.name.en}
                          className={`w-9 h-11 object-cover border ${ACCENT_BORDER[agent.accent]} flex-shrink-0`}
                        />
                        <div className="flex-1 min-w-0">
                          <p className={`font-mono text-[9px] tracking-eyebrow uppercase ${ACCENT_TEXT[agent.accent]}`}>
                            {agent.role.en}
                          </p>
                          <p className="font-serif italic text-[14px] text-bone-2 leading-tight">
                            {agent.name.en}
                          </p>
                        </div>
                        <div className="flex flex-col items-end gap-1 flex-shrink-0">
                          <span className="font-mono text-[10px] text-bone-3">
                            {completed}/{total || '—'}
                          </span>
                          {running > 0 && (
                            <span className="inline-flex items-center gap-1 font-mono text-[9px] text-brass">
                              <Loader2 className="w-2.5 h-2.5 animate-spin" />
                              {running}
                            </span>
                          )}
                        </div>
                        <div className="w-8 h-[2px] bg-bone/10 overflow-hidden flex-shrink-0">
                          <div className="h-full bg-sage" style={{ width: `${pct}%` }} />
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          </aside>

          {/* ─── Right pane (focus area) ─── */}
          <div className="flex flex-col gap-5 min-w-0">

            <AgentStage
              agent={heroAgent}
              currentTask={runningTask?.task_name}
              state={stage}
              accent={heroAccent}
              eyebrow={t('Act III · Builders', 'Acte III · Bâtisseurs')}
            />

            <AgentLivePreview
              agent={heroAgent}
              currentTask={runningTask?.task_name}
              excerpt={runningTask?.last_error ? `Error: ${runningTask.last_error}` : null}
              progress={
                stats
                  ? Math.round((stats.completed / Math.max(1, stats.total_tasks)) * 100)
                  : 0
              }
              state={stage}
            />

            <DetailView
              focus={focus}
              focusedPhase={focusedPhase}
              focusedAgent={focusedAgent}
              tasks={focusedTasks}
              t={t}
            />

            <div className="px-4 py-2.5 bg-ink-3 border border-bone/10">
              <p className="font-mono text-[10px] text-bone-4 tracking-[0.04em]">
                {t(
                  '↳ Click any phase or agent in the sidebar to focus this pane on it. The score and the hands stay visible at all times.',
                  '↳ Cliquez sur une phase ou un agent à gauche pour orienter ce panneau. La partition et les mains restent visibles en permanence.',
                )}
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

// ─── Detail view sub-component ─────────────────────────────────────

interface DetailViewProps {
  focus: Focus | null;
  focusedPhase?: PhaseExecution;
  focusedAgent: ReturnType<typeof getAgentById>;
  tasks: TaskInfo[];
  t: (en: string, fr: string) => string;
}

function DetailView({ focus, focusedAgent, tasks, t }: DetailViewProps) {
  if (!focus) return null;

  let eyebrow: string;
  let title: string;
  let lede: string;
  let accent: AccentToken;

  if (focus.type === 'phase') {
    const step = BUILD_STEPS[focus.phase - 1];
    accent = (focusedAgent?.accent as AccentToken) ?? 'terra';
    eyebrow = t(
      `Phase 0${focus.phase} · ${step?.label.en.replace(/^Phase \d+ · /, '')}`,
      `Phase 0${focus.phase} · ${step?.label.fr.replace(/^Phase \d+ · /, '')}`,
    );
    title = step ? t(step.cue.en, step.cue.fr) : `Phase 0${focus.phase}`;
    lede = focusedAgent
      ? t(
          `${focusedAgent.name.en} owns this phase · ${focusedAgent.role.en}.`,
          `${focusedAgent.name.fr} pilote cette phase · ${focusedAgent.role.fr}.`,
        )
      : '';
  } else {
    accent = (focusedAgent?.accent as AccentToken) ?? 'terra';
    eyebrow = focusedAgent ? t(focusedAgent.role.en, focusedAgent.role.fr) : focus.agentId;
    title = focusedAgent
      ? t(`${focusedAgent.name.en} — tasks on the board`, `${focusedAgent.name.fr} — tâches en scène`)
      : focus.agentId;
    lede = focusedAgent ? t(focusedAgent.tagline.en, focusedAgent.tagline.fr) : '';
  }

  const completed = tasks.filter(
    (tk) => tk.status === 'completed' || tk.status === 'passed',
  ).length;
  const running = tasks.filter((tk) =>
    ['running', 'deploying', 'committing', 'testing', 'generating'].includes(tk.status),
  ).length;
  const total = tasks.length;
  const earliest = tasks.map((tk) => tk.started_at).filter(Boolean).sort()[0];
  const lastEnd = tasks.map((tk) => tk.completed_at).filter(Boolean).sort().reverse()[0];
  const elapsed = formatDuration(earliest, lastEnd);
  const avgAttempt =
    tasks.length > 0
      ? (tasks.reduce((s, tk) => s + (tk.attempt_count || 1), 0) / tasks.length).toFixed(1)
      : '—';

  return (
    <section className="bg-ink-2 border border-bone/10 px-7 py-7">
      <p className={`font-mono text-[10px] tracking-eyebrow uppercase ${ACCENT_TEXT[accent]}`}>
        {eyebrow}
      </p>
      <h3 className="mt-2 font-serif italic text-[24px] text-bone leading-tight">{title}</h3>
      {lede && (
        <p className="mt-3 font-mono text-[12px] text-bone-3 leading-relaxed max-w-[68ch]">{lede}</p>
      )}

      <dl className="mt-5 grid grid-cols-3 gap-3">
        <div className="px-4 py-3 bg-ink-3 border border-bone/10">
          <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
            {t('Tasks done', 'Tâches faites')}
          </dt>
          <dd className={`mt-1 font-serif text-xl ${total > 0 && completed > 0 ? 'text-sage' : 'text-bone-4'}`}>
            {completed} / {total || 0}
          </dd>
        </div>
        <div className="px-4 py-3 bg-ink-3 border border-bone/10">
          <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
            {t('Time elapsed', 'Temps écoulé')}
          </dt>
          <dd className="mt-1 font-serif text-xl text-bone">{elapsed}</dd>
        </div>
        <div className="px-4 py-3 bg-ink-3 border border-bone/10">
          <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
            {focus.type === 'phase' ? t('Running now', 'En cours') : t('Avg attempt', 'Tentatives moy.')}
          </dt>
          <dd className="mt-1 font-serif text-xl text-bone">
            {focus.type === 'phase' ? running : `${avgAttempt}×`}
          </dd>
        </div>
      </dl>

      <div className="mt-6">
        <div className="flex items-center justify-between pb-2 border-b border-bone/10">
          <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
            {t('Tasks on the board', 'Tâches en scène')}
          </p>
          <p className="font-mono text-[10px] text-bone-4">
            {tasks.length} {t('total', 'au total')}
          </p>
        </div>
        {tasks.length === 0 ? (
          <div className="py-12 text-center">
            <Clock className="w-5 h-5 text-bone-4 mx-auto" />
            <p className="mt-3 font-serif italic text-bone-3 text-[13px]">
              {focus.type === 'phase'
                ? t(
                    'The curtain has not opened on this phase yet.',
                    "Le rideau n'est pas encore levé sur cette phase.",
                  )
                : t(
                    'No tasks assigned to this agent yet.',
                    "Aucune tâche assignée à cet agent pour l'instant.",
                  )}
            </p>
          </div>
        ) : (
          <ul>
            {tasks.map((task) => (
              <li key={task.task_id} className="grid grid-cols-[1fr_auto] gap-4 py-3 border-b border-bone/5 last:border-b-0">
                <div className="min-w-0">
                  <p className="font-serif text-[15px] text-bone leading-snug">{task.task_name}</p>
                  <p className="font-mono text-[10px] text-bone-4 mt-1">
                    {task.task_id} · {task.phase_name}
                    {task.assigned_agent ? ` · ${task.assigned_agent}` : ''}
                    {task.git_commit_sha ? ` · git: ${task.git_commit_sha.slice(0, 7)}` : ''}
                  </p>
                  {task.last_error && task.status === 'failed' && (
                    <p className="mt-2 font-mono text-[10px] text-error border-l border-error pl-2">
                      {task.last_error.slice(0, 200)}…
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  {task.attempt_count > 1 && (
                    <span className="font-mono text-[10px] text-warning">×{task.attempt_count}</span>
                  )}
                  <StatusBadge status={task.status} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

// ─── Status badge ──────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { tone: 'sage' | 'brass' | 'warning' | 'error' | 'bone'; label: string; Icon: typeof CheckCircle }> = {
    pending: { tone: 'bone', label: 'pending', Icon: Clock },
    running: { tone: 'brass', label: 'running', Icon: Loader2 },
    generating: { tone: 'brass', label: 'generating', Icon: Loader2 },
    deploying: { tone: 'warning', label: 'deploying', Icon: Play },
    testing: { tone: 'brass', label: 'testing', Icon: Loader2 },
    passed: { tone: 'sage', label: 'passed', Icon: CheckCircle },
    committing: { tone: 'brass', label: 'committing', Icon: Loader2 },
    completed: { tone: 'sage', label: 'completed', Icon: CheckCircle },
    failed: { tone: 'error', label: 'failed', Icon: AlertCircle },
    skipped: { tone: 'bone', label: 'skipped', Icon: Pause },
    blocked: { tone: 'warning', label: 'blocked', Icon: Clock },
  };
  const cfg = map[status] || map.pending;
  const toneClass: Record<string, string> = {
    sage: 'border-sage/40 text-sage',
    brass: 'border-brass/40 text-brass',
    warning: 'border-warning/40 text-warning',
    error: 'border-error/40 text-error',
    bone: 'border-bone/15 text-bone-4',
  };
  const Icon = cfg.Icon;
  const isSpinning = ['running', 'generating', 'testing', 'committing'].includes(status);
  return (
    <span className={['inline-flex items-center gap-1.5 px-2 py-1 border font-mono text-[9px] tracking-eyebrow uppercase', toneClass[cfg.tone]].join(' ')}>
      <Icon className={`w-3 h-3 ${isSpinning ? 'animate-spin' : ''}`} />
      {cfg.label}
    </span>
  );
}
