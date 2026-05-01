import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Loader2,
  Pause,
  Play,
  RefreshCw,
  Download,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle,
  Clock,
} from 'lucide-react';
import { api, executions } from '../services/api';
import { useLang } from '../contexts/LangContext';
import {
  BUILD_STEPS,
  findAgentByLabel,
  getAgentById,
  ACCENT_TEXT,
  ACCENT_BORDER,
  type AccentToken,
} from '../lib/agents';
import AgentStage from '../components/studio/AgentStage';
import StudioTimeline, {
  type StepStatus,
  type StudioTimelineEntry,
} from '../components/studio/StudioTimeline';
import AgentLivePreview from '../components/studio/AgentLivePreview';
import CurtainOverlay from '../components/studio/CurtainOverlay';
import BuildPhasesPanel, { type PhaseExecution } from '../components/BuildPhasesPanel';

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

function statusFromTasks(tasks: TaskInfo[]): StepStatus {
  if (!tasks || tasks.length === 0) return 'pending';
  if (tasks.some((t) => t.status === 'failed')) return 'failed';
  const completed = tasks.filter(
    (t) => t.status === 'completed' || t.status === 'passed',
  ).length;
  if (completed === tasks.length) return 'completed';
  if (tasks.some((t) => ['running', 'deploying', 'committing', 'testing'].includes(t.status))) {
    return 'current';
  }
  return 'pending';
}

export default function BuildMonitoringPage() {
  const { executionId } = useParams<{ executionId: string }>();
  const navigate = useNavigate();
  const { t } = useLang();

  const [data, setData] = useState<BuildTasksResponse | null>(null);
  const [phases, setPhases] = useState<PhaseExecution[]>([]);
  const [currentPhaseNumber, setCurrentPhaseNumber] = useState<number | undefined>();
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [isActioning, setIsActioning] = useState(false);
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set(['apex', 'lwc', 'admin']));
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTasks = async () => {
    if (!executionId) return;
    try {
      const response = await api.get(`/api/pm-orchestrator/execute/${executionId}/build-tasks`);
      setData(response);
      setIsPaused(response?.execution_status === 'paused' || response?.metadata?.build_paused === true);
      if (response?.execution_status === 'COMPLETED' || response?.execution_status === 'FAILED') {
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
      const response = await api.get(`/api/pm-orchestrator/execute/${executionId}/build-phases`);
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

  const tasksByAgent = data?.tasks_by_agent || {};
  const allTasks = data?.all_tasks || [];
  const stats = data?.build_phase;
  const status = (data?.execution_status || '').toLowerCase();

  // Build timeline.
  const timeline = useMemo<StudioTimelineEntry[]>(() => {
    return BUILD_STEPS.map((step) => {
      // Match agent id ↔ tasks_by_agent.
      const agentTasks = tasksByAgent[step.agentId] || [];
      const status = statusFromTasks(agentTasks);
      return {
        ...step,
        status,
        hasDeliverables: status === 'completed',
      };
    });
  }, [tasksByAgent]);

  // Active agent.
  const runningTask = allTasks.find((t) =>
    ['running', 'deploying', 'committing', 'testing'].includes(t.status),
  );
  const activeAgent = runningTask
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

  const tone: AccentToken = activeAgent?.accent ?? 'terra';

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

  const toggleAgent = (id: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
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

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-14">
        {/* Header */}
        <header className="mb-10 flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <p className={`font-mono text-[11px] tracking-eyebrow uppercase ${ACCENT_TEXT['terra']}`}>
              {t('Act III · Builders', 'Acte III · Bâtisseurs')}
            </p>
            <h1 className="mt-3 font-serif italic text-bone text-[34px] md:text-[42px] leading-tight">
              {t('Construction of the Salesforce stage', 'Construction de la scène Salesforce')}
            </h1>
            <p className="mt-2 font-mono text-[12px] text-bone-3 max-w-xl leading-relaxed">
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
              onClick={() => {
                fetchTasks();
                fetchPhases();
              }}
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

        {/* Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-3 space-y-6">
            {stats && (
              <aside className="bg-ink-2 border border-bone/10 sticky top-20">
                <div className="px-5 py-3 border-b border-bone/10">
                  <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                    {t('Stage progress', 'Avancement')}
                  </p>
                </div>
                <div className="px-5 py-5 space-y-5">
                  <div>
                    <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                      {t('Overall', 'Total')}
                    </dt>
                    <dd className="mt-1 font-serif text-2xl text-bone">
                      {stats.progress_percent}%
                    </dd>
                    <div className="mt-2 h-[2px] bg-bone/10 overflow-hidden">
                      <motion.div
                        className="h-full bg-terra"
                        initial={{ width: 0 }}
                        animate={{ width: `${stats.progress_percent}%` }}
                        transition={{ duration: 0.4, ease: 'easeOut' }}
                      />
                    </div>
                  </div>
                  <dl className="grid grid-cols-2 gap-4 text-bone-3">
                    <div>
                      <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                        {t('Done', 'Faits')}
                      </dt>
                      <dd className="font-serif text-xl text-sage">{stats.completed}</dd>
                    </div>
                    <div>
                      <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                        {t('Running', 'En cours')}
                      </dt>
                      <dd className="font-serif text-xl text-brass">{stats.running}</dd>
                    </div>
                    <div>
                      <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                        {t('Failed', 'Échecs')}
                      </dt>
                      <dd className="font-serif text-xl text-error">{stats.failed}</dd>
                    </div>
                    <div>
                      <dt className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                        {t('Pending', 'À faire')}
                      </dt>
                      <dd className="font-serif text-xl text-bone-4">{stats.pending}</dd>
                    </div>
                  </dl>
                </div>
              </aside>
            )}
            <StudioTimeline
              steps={timeline}
              title={t('BUILD · The score', 'BUILD · La partition')}
            />
          </div>

          <div className="lg:col-span-9 space-y-6">
            <AgentStage
              agent={activeAgent}
              currentTask={runningTask?.task_name}
              state={stage}
              accent={tone}
              eyebrow={t('Act III · Builders', 'Acte III · Bâtisseurs')}
            />

            <AgentLivePreview
              agent={activeAgent}
              currentTask={runningTask?.task_name}
              excerpt={runningTask?.last_error ? `Error: ${runningTask.last_error}` : null}
              progress={
                stats ? Math.round((stats.completed / Math.max(1, stats.total_tasks)) * 100) : 0
              }
              state={stage}
            />

            {phases.length > 0 && (
              <BuildPhasesPanel phases={phases} currentPhase={currentPhaseNumber} />
            )}

            {/* Tasks by agent — Studio cards */}
            <section className="space-y-3">
              <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                {t('Hands at work', 'À l’ouvrage')}
              </p>
              {Object.entries(tasksByAgent).map(([agentId, tasks]) => {
                const agent = getAgentById(agentId) || findAgentByLabel(agentId);
                const agentAccent: AccentToken = agent?.accent ?? 'terra';
                const isExpanded = expandedAgents.has(agentId);
                const completed = tasks.filter(
                  (tk) => tk.status === 'completed' || tk.status === 'passed',
                ).length;
                const running = tasks.filter((tk) => tk.status === 'running').length;
                return (
                  <div key={agentId} className={`bg-ink-2 border ${ACCENT_BORDER[agentAccent]}`}>
                    <button
                      type="button"
                      onClick={() => toggleAgent(agentId)}
                      className="w-full flex items-center justify-between px-5 py-3 hover:bg-ink-3/30"
                    >
                      <div className="flex items-center gap-3">
                        {agent ? (
                          <img
                            src={`/avatars/small/${agent.slug}.png`}
                            alt={agent.name.en}
                            className={`w-9 h-9 object-cover border ${ACCENT_BORDER[agentAccent]}`}
                          />
                        ) : (
                          <div className="w-9 h-9 border border-bone/15" />
                        )}
                        <div className="text-left">
                          <p className={`font-mono text-[10px] tracking-eyebrow uppercase ${ACCENT_TEXT[agentAccent]}`}>
                            {agent?.role.en || 'Agent'}
                          </p>
                          <p className="font-serif italic text-bone text-base">
                            {agent?.name.en || agentId}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="font-mono text-[10px] text-bone-3">
                          {completed}/{tasks.length}
                        </span>
                        {running > 0 && (
                          <span className="inline-flex items-center gap-1 font-mono text-[10px] text-brass">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            {running}
                          </span>
                        )}
                        <div className="w-20 h-[2px] bg-bone/10 overflow-hidden">
                          <div
                            className="h-full bg-sage"
                            style={{ width: `${(completed / Math.max(1, tasks.length)) * 100}%` }}
                          />
                        </div>
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4 text-bone-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-bone-4" />
                        )}
                      </div>
                    </button>
                    {isExpanded && (
                      <div className="border-t border-bone/10">
                        {tasks.map((task) => (
                          <div
                            key={task.task_id}
                            className="flex items-start justify-between px-5 py-3 border-b border-bone/5 last:border-b-0"
                          >
                            <div className="min-w-0">
                              <p className="font-serif text-bone text-sm leading-snug">
                                {task.task_name}
                              </p>
                              <p className="font-mono text-[10px] text-bone-4 mt-1">
                                {task.task_id} · {task.phase_name}
                              </p>
                              {task.last_error && task.status === 'failed' && (
                                <p className="mt-2 font-mono text-[10px] text-error border-l border-error pl-2">
                                  {task.last_error.slice(0, 160)}…
                                </p>
                              )}
                            </div>
                            <div className="flex items-center gap-3 shrink-0">
                              {task.attempt_count > 1 && (
                                <span className="font-mono text-[10px] text-warning">
                                  ×{task.attempt_count}
                                </span>
                              )}
                              {task.git_commit_sha && (
                                <span className="font-mono text-[10px] text-bone-4">
                                  {task.git_commit_sha.slice(0, 7)}
                                </span>
                              )}
                              <StatusBadge status={task.status} />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}

              {Object.keys(tasksByAgent).length === 0 && (
                <div className="bg-ink-2 border border-bone/10 p-12 text-center">
                  <Clock className="w-6 h-6 text-bone-4 mx-auto" />
                  <p className="mt-4 font-serif italic text-bone-3">
                    {t(
                      'No BUILD tasks yet — the SDS approval opens the curtain.',
                      'Aucune tâche BUILD encore — l’approbation du SDS ouvre le rideau.',
                    )}
                  </p>
                </div>
              )}
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { tone: 'sage' | 'brass' | 'warning' | 'error' | 'bone'; label: string; Icon: typeof CheckCircle }> = {
    pending: { tone: 'bone', label: 'pending', Icon: Clock },
    running: { tone: 'brass', label: 'running', Icon: Loader2 },
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
  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 px-2 py-1 border font-mono text-[9px] tracking-eyebrow uppercase',
        toneClass[cfg.tone],
      ].join(' ')}
    >
      <cfg.Icon className={`w-3 h-3 ${cfg.label.includes('ing') && cfg.tone === 'brass' ? 'animate-spin' : ''}`} />
      {cfg.label}
    </span>
  );
}
