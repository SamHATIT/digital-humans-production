import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Download, Loader2, MessageCircle, RotateCcw, BarChart3, ClipboardList } from 'lucide-react';
import { executions } from '../services/api';
import { useLang } from '../contexts/LangContext';
import {
  useExecutionStream,
  normalizeStatus,
  isAgentActive,
  type ExecutionProgress,
} from '../hooks/useExecutionStream';
import {
  SDS_STEPS,
  findAgentByLabel,
  getAgentById,
  type StudioAgent,
} from '../lib/agents';
import AgentStage from '../components/studio/AgentStage';
import StudioTimeline, {
  type StepStatus,
  type StudioTimelineEntry,
} from '../components/studio/StudioTimeline';
import AgentLivePreview from '../components/studio/AgentLivePreview';
import ExecutionMetricsStudio from '../components/studio/ExecutionMetricsStudio';
import ChatSidebarStudio from '../components/studio/ChatSidebarStudio';
import CurtainOverlay from '../components/studio/CurtainOverlay';
import DeliverableViewer from '../components/DeliverableViewer';
import ArchitectureReviewPanel from '../components/ArchitectureReviewPanel';
import ValidationGatePanel from '../components/ValidationGatePanel';
import ExecutionMetrics from '../components/ExecutionMetrics';

type WorkPhase = 1 | 2 | 3 | 4 | 5 | 6 | 0;

function phaseFromState(state: string | undefined): WorkPhase {
  if (!state) return 0;
  if (state.startsWith('sds_phase1') || state.startsWith('waiting_br')) return 1;
  if (state.startsWith('sds_phase2')) return 2;
  if (state.startsWith('sds_phase3') || state.startsWith('waiting_arch')) return 3;
  if (state.startsWith('sds_phase4')) return 4;
  if (state.startsWith('sds_phase5') || state === 'sds_complete') return 5;
  if (state.startsWith('build')) return 6;
  return 0;
}

function stepStatusFor(
  stepIdx: number,
  prog: ExecutionProgress,
): StepStatus {
  const status = (prog.status || '').toLowerCase();
  const state = prog.execution_state || '';
  const phase = phaseFromState(state);

  // Map step index → SDS phase (1..5).
  // SDS_STEPS: 0=Sophie/BR, 1=Olivia, 2=Emma coverage, 3=Marcus, 4=Experts, 5=Emma SDS
  const STEP_PHASE: Record<number, WorkPhase> = {
    0: 1,
    1: 2,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
  };
  const stepPhase = STEP_PHASE[stepIdx] ?? 0;

  if (status === 'failed') return stepPhase <= phase ? 'failed' : 'pending';
  if (status === 'cancelled') return 'pending';

  if (status === 'waiting_br_validation' && stepPhase === 1) return 'waiting_hitl';
  if (status === 'waiting_architecture_validation' && stepPhase === 3) return 'waiting_hitl';
  if (status === 'waiting_expert_validation' && stepPhase === 4) return 'waiting_hitl';
  if (status === 'waiting_sds_validation' && stepPhase === 5) return 'waiting_hitl';

  if (state) {
    if (stepPhase < phase) return 'completed';
    if (stepPhase === phase) {
      if (state === 'sds_complete' || state === 'build_complete') return 'completed';
      return 'current';
    }
    return 'pending';
  }

  // Fallback: inspect agent_progress
  const stepAgentId = SDS_STEPS[stepIdx]?.agentId;
  const agent = prog.agent_progress?.find((a) => {
    const found = findAgentByLabel(a.agent_name);
    return found?.id === stepAgentId;
  });
  if (!agent) return 'pending';
  const aStatus = normalizeStatus(agent.status);
  if (aStatus === 'completed') return 'completed';
  if (aStatus === 'failed') return 'failed';
  if (isAgentActive(agent.status)) return 'current';
  return 'pending';
}

function timelineFromProgress(prog: ExecutionProgress | null): StudioTimelineEntry[] {
  if (!prog) {
    return SDS_STEPS.map((step) => ({ ...step, status: 'pending', hasDeliverables: false }));
  }
  return SDS_STEPS.map((step, idx) => {
    const status = stepStatusFor(idx, prog);
    return {
      ...step,
      status,
      hasDeliverables: status === 'completed' || status === 'waiting_hitl',
    };
  });
}

function activeAgentFrom(prog: ExecutionProgress | null): {
  agent: StudioAgent | null;
  task?: string;
  output?: string;
  progress: number;
} {
  if (!prog) return { agent: null, progress: 0 };

  // 1) Find a running agent in progress array.
  const running = prog.agent_progress?.find((a) => isAgentActive(a.status));
  if (running) {
    return {
      agent: findAgentByLabel(running.agent_name),
      task: running.current_task,
      output: running.output_summary,
      progress: running.progress ?? 0,
    };
  }

  // 2) Otherwise, derive from execution_state phase.
  const phase = phaseFromState(prog.execution_state);
  const phaseAgentId =
    phase === 1
      ? 'pm'
      : phase === 2
        ? 'ba'
        : phase === 3
          ? 'architect'
          : phase === 4
            ? 'qa'
            : phase === 5
              ? 'research_analyst'
              : phase === 6
                ? 'apex'
                : null;
  if (phaseAgentId) {
    return {
      agent: getAgentById(phaseAgentId),
      task: prog.current_phase,
      progress: prog.overall_progress ?? 0,
    };
  }

  // 3) Final fallback — last completed agent.
  const completed = [...(prog.agent_progress || [])]
    .reverse()
    .find((a) => normalizeStatus(a.status) === 'completed');
  return {
    agent: completed ? findAgentByLabel(completed.agent_name) : null,
    output: completed?.output_summary,
    progress: prog.overall_progress ?? 0,
  };
}

function pageStateFor(prog: ExecutionProgress | null): {
  stage: 'idle' | 'active' | 'completed' | 'failed' | 'waiting';
  isHitl: boolean;
} {
  if (!prog) return { stage: 'idle', isHitl: false };
  const status = (prog.status || '').toLowerCase();
  const hitl = status.startsWith('waiting_');
  if (hitl) return { stage: 'waiting', isHitl: true };
  if (status === 'completed') return { stage: 'completed', isHitl: false };
  if (status === 'failed') return { stage: 'failed', isHitl: false };
  if (status === 'cancelled') return { stage: 'idle', isHitl: false };
  return { stage: 'active', isHitl: false };
}

export default function ExecutionMonitoringPage() {
  const { executionId } = useParams<{ executionId: string }>();
  const navigate = useNavigate();
  const { t } = useLang();

  const id = executionId ? Number(executionId) : undefined;
  const { progress, budget, error: streamError, isInitialLoading, refresh } = useExecutionStream(id);

  const [chatOpen, setChatOpen] = useState(false);
  const [showMetrics, setShowMetrics] = useState(false);
  const [selectedDeliverablePhase, setSelectedDeliverablePhase] = useState<number | null>(null);
  const [pendingGate, setPendingGate] = useState<any>(null);
  const [isArchAction, setIsArchAction] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [actionError, setActionError] = useState('');

  const status = (progress?.status || '').toLowerCase();
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';
  const canDownload = isCompleted && !!progress?.sds_document_path;

  const { stage, isHitl } = pageStateFor(progress);
  const { agent: activeAgent, task, output, progress: agentProgress } = activeAgentFrom(progress);
  const timeline = useMemo(() => timelineFromProgress(progress), [progress]);

  // Configurable gate fetch.
  useEffect(() => {
    const gateStatuses = ['waiting_expert_validation', 'waiting_sds_validation', 'waiting_build_validation'];
    if (id && gateStatuses.includes(status)) {
      executions
        .getValidationGate(id)
        .then((data) => setPendingGate(data?.pending || null))
        .catch(() => setPendingGate(null));
    } else {
      setPendingGate(null);
    }
  }, [status, id]);

  const handleArchitectureAction = async (action: 'approve_architecture' | 'revise_architecture') => {
    if (!id) return;
    setIsArchAction(true);
    try {
      await executions.resume(id, action);
      await refresh();
    } catch (err: any) {
      setActionError(err?.message || `Failed to ${action}`);
    } finally {
      setIsArchAction(false);
    }
  };

  const handleGateResume = async () => {
    setPendingGate(null);
    await refresh();
  };

  const handleRetry = async () => {
    if (!id) return;
    setIsRetrying(true);
    try {
      await executions.retry(id);
      await refresh();
    } catch (err: any) {
      setActionError(err?.message || 'Failed to retry');
    } finally {
      setIsRetrying(false);
    }
  };

  const handleDownload = () => {
    if (!id) return;
    // The SDS HTML is the canonical deliverable: rendered from DB via Jinja2,
    // with an in-page PRINT · PDF button. The legacy /download endpoint
    // returns a Word doc that just prints raw HTML markup.
    window.open(executions.getSdsHtmlUrl(id), '_blank');
  };

  const handleSelectStep = (step: { id: string }) => {
    const PHASE_FOR_STEP_ID: Record<string, number> = {
      'sds-1': 1,
      'sds-2': 2,
      'sds-2b': 2,
      'sds-3': 3,
      'sds-4': 4,
      'sds-5': 5,
    };
    const phase = PHASE_FOR_STEP_ID[step.id];
    if (phase) setSelectedDeliverablePhase((prev) => (prev === phase ? null : phase));
  };

  if (isInitialLoading) {
    return (
      <div className="bg-ink min-h-[calc(100vh-4rem)] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-6 h-6 text-brass animate-spin mx-auto" />
          <p className="mt-4 font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
            {t('Curtain rising…', 'Le rideau se lève…')}
          </p>
        </div>
      </div>
    );
  }

  if (streamError && !progress) {
    return (
      <div className="bg-ink min-h-[calc(100vh-4rem)] flex items-center justify-center">
        <p className="font-serif italic text-error">{streamError}</p>
      </div>
    );
  }

  // Active step → eyebrow override.
  const currentStep = timeline.find((s) => s.status === 'current') || timeline.find((s) => s.status === 'waiting_hitl');

  // Header eyebrow + title.
  const eyebrow = stage === 'completed'
    ? t('No 04 · Curtain call', 'Nº 04 · Saluts')
    : stage === 'failed'
      ? t('No 04 · Performance interrupted', 'Nº 04 · Représentation interrompue')
      : t('No 04 · The Theatre', 'Nº 04 · Le Théâtre');

  return (
    <div className="bg-ink min-h-[calc(100vh-4rem)]">
      <CurtainOverlay
        storageKey={String(id)}
        eyebrow={eyebrow as string}
        title={{
          en: 'The ensemble takes the stage',
          fr: 'L’ensemble entre en scène',
        }}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-14">
        {/* Header */}
        <header className="mb-10 flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
              {eyebrow}
            </p>
            <h1 className="mt-3 font-serif italic text-bone text-[34px] md:text-[42px] leading-tight">
              {currentStep
                ? t(currentStep.label.en, currentStep.label.fr)
                : t('In rehearsal', 'En répétition')}
            </h1>
            {currentStep && (
              <p className="mt-2 font-mono text-[12px] text-bone-3 max-w-xl leading-relaxed">
                {t(currentStep.cue.en, currentStep.cue.fr)}
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowMetrics((v) => !v)}
              className={[
                'inline-flex items-center gap-2 px-4 py-2 border font-mono text-[10px] tracking-eyebrow uppercase transition-colors',
                showMetrics
                  ? 'border-brass text-brass'
                  : 'border-bone/15 text-bone-3 hover:text-bone hover:border-bone/30',
              ].join(' ')}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              {t('Metrics', 'Métriques')}
            </button>
            <button
              type="button"
              onClick={() => setChatOpen((v) => !v)}
              className={[
                'inline-flex items-center gap-2 px-4 py-2 border font-mono text-[10px] tracking-eyebrow uppercase transition-colors relative',
                chatOpen
                  ? 'border-brass text-brass'
                  : 'border-bone/15 text-bone-3 hover:text-bone hover:border-bone/30',
              ].join(' ')}
            >
              <MessageCircle className="w-3.5 h-3.5" />
              {t('Chat', 'Chat')}
              {isHitl && (
                <motion.span
                  className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-warning"
                  animate={{ opacity: [0.5, 1, 0.5] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
                />
              )}
            </button>
            {canDownload && (
              <button
                type="button"
                onClick={handleDownload}
                className="inline-flex items-center gap-2 px-5 py-2 bg-brass text-ink hover:bg-brass-2 font-mono text-[10px] tracking-cta uppercase"
              >
                <Download className="w-3.5 h-3.5" />
                {t('Download SDS', 'Télécharger le SDS')}
              </button>
            )}
          </div>
        </header>

        {(streamError || actionError) && (
          <div className="mb-8 border border-error/40 bg-error/10 px-4 py-3 font-mono text-[12px] text-error">
            {streamError || actionError}
          </div>
        )}

        {/* HITL banners */}
        {status === 'waiting_br_validation' && progress && (
          <section className="mb-8 border border-warning/40 bg-warning/10 p-6">
            <div className="flex items-start gap-4">
              <ClipboardList className="w-5 h-5 text-warning shrink-0 mt-1" />
              <div className="flex-1">
                <p className="font-mono text-[10px] tracking-eyebrow uppercase text-warning">
                  {t('Act I · Pause for review', 'Acte I · Pause pour validation')}
                </p>
                <h3 className="mt-2 font-serif italic text-bone text-2xl">
                  {t(
                    'Sophie hands you the Business Requirements.',
                    'Sophie vous remet les exigences métier.',
                  )}
                </h3>
                <p className="mt-2 font-mono text-[12px] text-bone-3 max-w-2xl leading-relaxed">
                  {t(
                    'Review, edit or add requirements before the analysis continues.',
                    'Relisez, modifiez ou ajoutez des exigences avant que l’analyse ne reprenne.',
                  )}
                </p>
                <button
                  type="button"
                  onClick={() => navigate(`/br-validation/${progress.project_id}?executionId=${progress.execution_id}`)}
                  className="mt-4 inline-flex items-center gap-2 px-5 py-2 bg-warning text-ink hover:bg-warning/80 font-mono text-[10px] tracking-cta uppercase"
                >
                  <ClipboardList className="w-3.5 h-3.5" />
                  {t('Review requirements', 'Réviser les exigences')}
                </button>
              </div>
            </div>
          </section>
        )}

        {status === 'waiting_architecture_validation' && progress?.execution_id && (() => {
          const research = progress.agent_progress?.find(
            (a) => a.agent_name?.includes('Emma') || a.agent_name?.includes('Research'),
          );
          const extra = research?.extra_data;
          return (
            <section className="mb-8">
              <ArchitectureReviewPanel
                executionId={progress.execution_id}
                onApprove={() => handleArchitectureAction('approve_architecture')}
                onRevise={() => handleArchitectureAction('revise_architecture')}
                isActioning={isArchAction}
                coverageScore={extra?.coverage_score ?? null}
                criticalGaps={extra?.critical_gaps || []}
                uncoveredUseCases={extra?.uncovered_use_cases || []}
                revisionCount={extra?.revision_count ?? 0}
              />
            </section>
          );
        })()}

        {pendingGate && progress?.execution_id && (
          <section className="mb-8">
            <ValidationGatePanel
              executionId={progress.execution_id}
              pending={pendingGate}
              onResume={handleGateResume}
            />
          </section>
        )}

        {/* Theatre layout : timeline / stage / sidebar */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-3 space-y-6">
            <ExecutionMetricsStudio
              budget={budget}
              executionState={progress?.execution_state}
              revisionCount={
                progress?.agent_progress?.find(
                  (a) => a.agent_name?.includes('Emma') || a.agent_name?.includes('Research'),
                )?.extra_data?.revision_count ?? 0
              }
              startedAt={null}
            />
            <StudioTimeline
              steps={timeline}
              onSelect={handleSelectStep}
              selectedId={null}
              title={t('SDS · The score', 'SDS · La partition')}
            />
          </div>

          <div className="lg:col-span-9 space-y-6">
            <AgentStage
              agent={activeAgent}
              currentTask={task}
              state={stage}
            />

            <AgentLivePreview
              agent={activeAgent}
              currentTask={task}
              excerpt={output}
              progress={agentProgress}
              state={stage}
            />

            {selectedDeliverablePhase !== null && progress?.execution_id && (
              <DeliverableViewer
                executionId={progress.execution_id}
                phaseNumber={selectedDeliverablePhase}
                onClose={() => setSelectedDeliverablePhase(null)}
              />
            )}

            {/* Failure rescue */}
            {isFailed && (
              <div className="border border-error/40 bg-error/5 p-5 flex items-center justify-between gap-4">
                <p className="font-serif italic text-error text-lg">
                  {t(
                    'The performance was interrupted.',
                    'La représentation a été interrompue.',
                  )}
                </p>
                <button
                  type="button"
                  onClick={handleRetry}
                  disabled={isRetrying}
                  className="inline-flex items-center gap-2 px-5 py-2 bg-warning text-ink hover:bg-warning/80 font-mono text-[10px] tracking-cta uppercase disabled:opacity-50"
                >
                  {isRetrying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                  {t('Retry the act', 'Rejouer l’acte')}
                </button>
              </div>
            )}

            {/* Successful complete */}
            {isCompleted && progress && (
              <div className="border border-sage/40 bg-sage/10 p-5">
                <p className="font-mono text-[10px] tracking-eyebrow uppercase text-sage">
                  {t('Curtain call', 'Saluts')}
                </p>
                <p className="mt-2 font-serif italic text-bone text-xl">
                  {t(
                    'The SDS is ready. The ensemble bows.',
                    'Le SDS est prêt. L’ensemble salue.',
                  )}
                </p>
                <div className="mt-4 flex items-center gap-3">
                  {canDownload && (
                    <button
                      type="button"
                      onClick={handleDownload}
                      className="inline-flex items-center gap-2 px-5 py-2 bg-brass text-ink hover:bg-brass-2 font-mono text-[10px] tracking-cta uppercase"
                    >
                      <Download className="w-3.5 h-3.5" />
                      {t('View SDS →', 'Voir le SDS →')}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => navigate(`/execution/${progress.execution_id}/build`)}
                    className="inline-flex items-center gap-2 px-5 py-2 border border-terra text-terra hover:bg-terra/10 font-mono text-[10px] tracking-cta uppercase"
                  >
                    {t('Open the BUILD →', 'Ouvrir le BUILD →')}
                  </button>
                </div>
              </div>
            )}

            {showMetrics && progress?.agent_progress && (
              <ExecutionMetrics
                agents={progress.agent_progress.map((a) => ({
                  agent_name: a.agent_name,
                  tokens_used: (a as any).tokens_used || 0,
                  cost: (a as any).cost || 0,
                  duration_seconds: (a as any).duration_seconds || 0,
                  status: a.status,
                }))}
                totalCost={budget?.execution_cost}
              />
            )}
          </div>
        </div>
      </main>

      {/* Chat sidebar (HITL) */}
      {progress?.execution_id && (
        <ChatSidebarStudio
          executionId={progress.execution_id}
          isOpen={chatOpen}
          onClose={() => setChatOpen(false)}
          alert={isHitl}
          initialAgent={activeAgent?.id || 'pm'}
        />
      )}
    </div>
  );
}
