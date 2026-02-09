import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Download, Loader2, CheckCircle, AlertCircle, Clock, Zap, RefreshCw, RefreshCcw, ClipboardList, RotateCcw, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-react';
import { executions } from '../services/api';
import Navbar from '../components/Navbar';
import Avatar from '../components/ui/Avatar';
import AgentThoughtModal from '../components/AgentThoughtModal';
import SDSv3Generator from '../components/SDSv3Generator';
import TimelineStepper from '../components/TimelineStepper';
import DeliverableViewer from '../components/DeliverableViewer';
import ValidationGatePanel from '../components/ValidationGatePanel';
import { AGENTS } from '../constants';
import type { PhaseInfo } from '../components/TimelineStepper';

// Define Agent type inline - TypeScript types get erased at runtime
interface Agent {
  id: string;
  name: string;
  role: string;
  description: string;
  avatar: string;
  isMandatory?: boolean;
}

interface AgentProgress {
  agent_name: string;
  status: string;
  progress: number;
  current_task?: string;
  output_summary?: string;
  extra_data?: {
    approval_type?: string;
    coverage_score?: number;
    critical_gaps?: Array<{gap: string; severity: string}>;
    uncovered_use_cases?: string[];
    revision_count?: number;
    max_revisions?: number;
  };
}

interface ExecutionProgress {
  execution_id: number;
  project_id: number;
  status: string;
  execution_state?: string;
  overall_progress: number;
  current_phase?: string;
  agent_progress: AgentProgress[];
  sds_document_path?: string;
}

interface BudgetInfo {
  allowed: boolean;
  execution_cost: number;
  project_cost: number;
  remaining_execution: number;
  remaining_project: number;
  limit_type?: string;
  current?: number;
  limit?: number;
  message?: string;
}

// I1.4: Map execution_state to phase number for timeline
function getPhaseFromState(state: string): number {
  if (state.startsWith('sds_phase1') || state.startsWith('waiting_br')) return 1;
  if (state.startsWith('sds_phase2')) return 2;  // includes 2_5
  if (state.startsWith('sds_phase3') || state.startsWith('waiting_arch')) return 3;
  if (state.startsWith('sds_phase4')) return 4;
  if (state.startsWith('sds_phase5') || state === 'sds_complete') return 5;
  if (state.startsWith('build')) return 6;
  return 0;
}

export default function ExecutionMonitoringPage() {
  const { executionId } = useParams<{ executionId: string }>();
  const navigate = useNavigate();
  const [progress, setProgress] = useState<ExecutionProgress | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Thought modal state
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [selectedAgentTask, setSelectedAgentTask] = useState<string>('');
  const [selectedAgentOutput, setSelectedAgentOutput] = useState<string>('');
  const [selectedAgentStatus, setSelectedAgentStatus] = useState<string>('');

  // ORCH-04: Retry state
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');

  // H12: Architecture validation state
  const [isArchAction, setIsArchAction] = useState(false);

  // P2-Full: Configurable gate validation state
  const [pendingGateData, setPendingGateData] = useState<any>(null);

  // UX1: Timeline + Deliverable viewer state
  const [selectedPhase, setSelectedPhase] = useState<number | null>(null);
  const [allAgentsExpanded, setAllAgentsExpanded] = useState(false);

  // I1.4: Budget tracking
  const [budget, setBudget] = useState<BudgetInfo | null>(null);
  const budgetPollingRef = useRef<NodeJS.Timeout | null>(null);

  // FRNT-02 + I1.4: Compare progress using execution_state first, fallback to agent-level diff
  const hasProgressChanged = (oldData: ExecutionProgress | null, newData: ExecutionProgress | null): boolean => {
    if (!oldData || !newData) return true;
    if (oldData.status !== newData.status) return true;
    // I1.4: Primary comparison on execution_state
    if (oldData.execution_state !== newData.execution_state) return true;
    if (oldData.overall_progress !== newData.overall_progress) return true;
    if (oldData.agent_progress?.length !== newData.agent_progress?.length) return true;
    // Fallback: check agent-level changes
    for (let i = 0; i < (oldData.agent_progress?.length || 0); i++) {
      const oldAgent = oldData.agent_progress[i];
      const newAgent = newData.agent_progress?.find(a => a.agent_name === oldAgent.agent_name);
      if (!newAgent) return true;
      if (oldAgent.status !== newAgent.status || oldAgent.progress !== newAgent.progress || oldAgent.current_task !== newAgent.current_task) return true;
    }
    return false;
  };

  useEffect(() => {
    const fetchProgress = async () => {
      try {
        const data = await executions.getProgress(Number(executionId));

        // FRNT-02: Only update if data actually changed (prevents scroll jumps)
        if (data && data.agent_progress && data.agent_progress.length > 0) {
          setProgress(prevProgress => {
            if (hasProgressChanged(prevProgress, data)) {
              return data;
            }
            return prevProgress;
          });
        } else if (data) {
          setProgress(prevProgress => prevProgress || data);
        }

        // Stop polling if completed, failed, or waiting for validation
        const stopStatuses = [
          'completed', 'failed', 'cancelled',
          'waiting_br_validation', 'waiting_architecture_validation',
          'waiting_expert_validation', 'waiting_sds_validation', 'waiting_build_validation',
        ];
        if (stopStatuses.includes(data?.status)) {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          // Also stop budget polling on terminal states
          if (budgetPollingRef.current && (data?.status === 'completed' || data?.status === 'failed' || data?.status === 'cancelled')) {
            clearInterval(budgetPollingRef.current);
            budgetPollingRef.current = null;
          }
        }
      } catch (err: any) {
        console.error('Failed to fetch progress:', err);
        // FRNT-02: Don't set error on poll failures if we already have data
        if (!progress) {
          setError(err.message || 'Failed to fetch progress');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchProgress();

    // Start polling every 3 seconds
    pollingRef.current = setInterval(fetchProgress, 3000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [executionId]);

// I1.4: Budget polling every 10 seconds
  useEffect(() => {
    if (!executionId) return;

    const fetchBudget = async () => {
      try {
        const data = await executions.getBudget(Number(executionId));
        setBudget(data);
      } catch {
        // Budget endpoint is optional — don't block UI
      }
    };

    fetchBudget();
    budgetPollingRef.current = setInterval(fetchBudget, 10000);

    return () => {
      if (budgetPollingRef.current) {
        clearInterval(budgetPollingRef.current);
      }
    };
  }, [executionId]);

  // P2-Full: Fetch pending gate data when in a configurable gate state
  useEffect(() => {
    const waitingGateStatuses = [
      'waiting_expert_validation',
      'waiting_sds_validation',
      'waiting_build_validation',
    ];
    const status = progress?.status?.toLowerCase() || '';
    if (waitingGateStatuses.includes(status) && executionId) {
      executions.getValidationGate(Number(executionId))
        .then((data) => setPendingGateData(data?.pending || null))
        .catch((err) => console.error('Failed to fetch validation gate:', err));
    } else {
      setPendingGateData(null);
    }
  }, [progress?.status, executionId]);

  const handleDownload = () => {
    if (!executionId) return;
    const downloadUrl = executions.getResultFile(Number(executionId));
    window.open(downloadUrl, '_blank');
  };

  const handleAgentClick = (agentProgress: AgentProgress) => {
    // Extract just the name part before " (" - e.g. "Sophie (PM)" -> "Sophie"
    const agentNameOnly = agentProgress.agent_name.split(' (')[0].toLowerCase();
    const agent = AGENTS.find((a) => a.name.toLowerCase() === agentNameOnly);
    if (agent) {
      setSelectedAgent(agent as Agent);
      setSelectedAgentTask(agentProgress.current_task || '');
      setSelectedAgentOutput(agentProgress.output_summary || '');
      setSelectedAgentStatus(agentProgress.status || '');
    } else {
      console.warn('Agent not found for:', agentProgress.agent_name, '-> extracted:', agentNameOnly);
    }
  };

  // ORCH-04: Handle retry
  const handleRetry = async () => {
    if (!executionId) return;
    setIsRetrying(true);
    setRetryError('');

    try {
      await executions.retry(Number(executionId));
      // Restart polling
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
      pollingRef.current = setInterval(async () => {
        const data = await executions.getProgress(Number(executionId));
        setProgress(data);
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
          if (pollingRef.current) clearInterval(pollingRef.current);
        }
      }, 3000);
    } catch (err: any) {
      setRetryError(err.message || 'Failed to retry execution');
    } finally {
      setIsRetrying(false);
    }
  };

  const getStatusConfig = (status: string) => {
    const configs: Record<string, { color: string; bgColor: string; icon: typeof CheckCircle }> = {
      completed: { color: 'text-green-400', bgColor: 'bg-green-500', icon: CheckCircle },
      in_progress: { color: 'text-cyan-400', bgColor: 'bg-cyan-500', icon: Zap },
      running: { color: 'text-cyan-400', bgColor: 'bg-cyan-500', icon: Zap },
      pending: { color: 'text-slate-400', bgColor: 'bg-slate-500', icon: Clock },
      failed: { color: 'text-red-400', bgColor: 'bg-red-500', icon: AlertCircle },
    };
    return configs[status] || configs.pending;
  };

  const normalizeStatus = (status: string): string => {
    const statusMap: Record<string, string> = {
      COMPLETED: 'completed',
      RUNNING: 'running',
      IN_PROGRESS: 'in_progress',
      PENDING: 'pending',
      FAILED: 'failed',
    };
    return statusMap[status?.toUpperCase()] || status?.toLowerCase() || 'pending';
  };

  // UX1 + I1.4: Map execution progress to timeline phases
  // Uses execution_state (state machine) when available, falls back to agent-based logic
  const getPhaseStatus = (prog: ExecutionProgress): PhaseInfo[] => {
    const agentStatus = (name: string) =>
      prog.agent_progress?.find(a => a.agent_name.includes(name))?.status;

    const normalizedStatus = prog.status?.toLowerCase() || '';
    const execState = prog.execution_state || '';
    const statePhase = execState ? getPhaseFromState(execState) : 0;

    // I1.4: State machine–driven phase status when execution_state is available
    const phaseStatusFromState = (phaseNum: number): 'completed' | 'active' | 'waiting_hitl' | 'pending' | 'failed' => {
      if (!execState || statePhase === 0) return 'pending'; // fallback handled below
      if (execState === 'failed') return phaseNum <= statePhase ? 'failed' : 'pending';
      if (execState === 'cancelled') return 'pending';

      // HITL gates
      if (execState === 'waiting_br_validation' && phaseNum === 1) return 'waiting_hitl';
      if (execState === 'waiting_architecture_validation' && phaseNum === 3) return 'waiting_hitl';

      if (phaseNum < statePhase) return 'completed';
      if (phaseNum === statePhase) {
        // Check if this phase is a "complete" state
        if (execState.endsWith('_complete') || execState === 'sds_complete' || execState === 'build_complete') {
          return 'completed';
        }
        return 'active';
      }
      return 'pending';
    };

    // Build phases array — use state machine when available
    const useStateMachine = !!execState && statePhase > 0;

    const phases: PhaseInfo[] = [
      {
        number: 1,
        label: 'Business Req.',
        agents: 'Sophie',
        status: useStateMachine ? phaseStatusFromState(1) : (
          normalizeStatus(agentStatus('Sophie') || '') === 'completed' ? 'completed' :
          normalizedStatus === 'waiting_br_validation' ? 'waiting_hitl' :
          ['in_progress', 'running'].includes(normalizeStatus(agentStatus('Sophie') || '')) ? 'active' : 'pending'
        ),
        hasDeliverables: useStateMachine ? statePhase > 1 : normalizeStatus(agentStatus('Sophie') || '') === 'completed',
      },
      {
        number: 2,
        label: 'Use Cases',
        agents: 'Olivia & Emma',
        status: useStateMachine ? phaseStatusFromState(2) : (
          normalizeStatus(agentStatus('Olivia') || '') === 'completed' ? 'completed' :
          ['in_progress', 'running'].includes(normalizeStatus(agentStatus('Olivia') || '')) ? 'active' : 'pending'
        ),
        hasDeliverables: useStateMachine ? statePhase > 2 : normalizeStatus(agentStatus('Olivia') || '') === 'completed',
      },
      {
        number: 3,
        label: 'Architecture',
        agents: 'Marcus & Emma',
        status: useStateMachine ? phaseStatusFromState(3) : (
          normalizeStatus(agentStatus('Marcus') || '') === 'completed' ? 'completed' :
          normalizedStatus.includes('waiting_architecture') ? 'waiting_hitl' :
          ['in_progress', 'running'].includes(normalizeStatus(agentStatus('Marcus') || '')) ? 'active' : 'pending'
        ),
        hasDeliverables: useStateMachine ? statePhase > 3 : normalizeStatus(agentStatus('Marcus') || '') === 'completed',
      },
      {
        number: 4,
        label: 'Expert Specs',
        agents: 'Elena, Jordan, Aisha, Lucas',
        status: normalizedStatus === 'waiting_expert_validation' ? 'waiting_hitl' :
                useStateMachine ? phaseStatusFromState(4) : (
          ['Elena', 'Jordan', 'Aisha', 'Lucas'].every(
            n => normalizeStatus(agentStatus(n) || '') === 'completed') ? 'completed' :
          ['Elena', 'Jordan', 'Aisha', 'Lucas'].some(
            n => ['in_progress', 'running'].includes(normalizeStatus(agentStatus(n) || ''))) ? 'active' : 'pending'
        ),
        hasDeliverables: useStateMachine ? statePhase > 4 : ['Elena', 'Jordan', 'Aisha', 'Lucas'].some(
                  n => normalizeStatus(agentStatus(n) || '') === 'completed'),
      },
      {
        number: 5,
        label: 'SDS Final',
        agents: 'Emma',
        status: normalizedStatus === 'waiting_sds_validation' ? 'waiting_hitl' :
                useStateMachine ? phaseStatusFromState(5) : (
          normalizedStatus === 'completed' ? 'completed' :
          normalizeStatus(
            prog.agent_progress?.find(
              a => a.agent_name.includes('Emma') &&
              a.current_task?.toLowerCase().includes('sds'))?.status || ''
          ) === 'in_progress' ? 'active' : 'pending'
        ),
        hasDeliverables: useStateMachine
          ? (execState === 'sds_complete' || statePhase > 5)
          : normalizedStatus === 'completed',
      },
    ];

    // I1.4: Add BUILD phase when state machine shows build activity
    if (useStateMachine && statePhase >= 6) {
      phases.push({
        number: 6,
        label: 'BUILD',
        agents: 'Diego, Zara, Raj',
        status: phaseStatusFromState(6),
        hasDeliverables: execState === 'build_complete' || execState === 'deployed',
      });
    }

    // Check for failed agents (fallback: only when not using state machine)
    if (!useStateMachine) {
      for (const phase of phases) {
        if (phase.status === 'pending' || phase.status === 'active') {
          const phaseAgentNames: Record<number, string[]> = {
            1: ['Sophie'],
            2: ['Olivia'],
            3: ['Marcus'],
            4: ['Elena', 'Jordan', 'Aisha', 'Lucas'],
            5: ['Emma'],
          };
          const agents = phaseAgentNames[phase.number] || [];
          if (agents.some(n => normalizeStatus(agentStatus(n) || '') === 'failed')) {
            phase.status = 'failed';
          }
        }
      }
    }

    return phases;
  };

  // UX1: Handle phase click from timeline
  const handlePhaseClick = (phaseNumber: number) => {
    // If clicking a HITL phase, don't open deliverables (HITL panel is already visible)
    const phases = progress ? getPhaseStatus(progress) : [];
    const phase = phases.find(p => p.number === phaseNumber);
    if (phase?.status === 'waiting_hitl') return;
    // Toggle deliverable viewer
    setSelectedPhase(prev => prev === phaseNumber ? null : phaseNumber);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0B1120] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-cyan-500 animate-spin mx-auto" />
          <p className="text-slate-400 mt-4">Loading execution progress...</p>
        </div>
      </div>
    );
  }

  const normalizedMainStatus = progress?.status?.toLowerCase() || '';
  const isCompleted = normalizedMainStatus === 'completed';
  const isFailed = normalizedMainStatus === 'failed';
  const isCancelled = normalizedMainStatus === 'cancelled';
  const isWaitingBRValidation = normalizedMainStatus === 'waiting_br_validation';
  const isWaitingArchitectureValidation = normalizedMainStatus === 'waiting_architecture_validation';
  // P2-Full: Configurable validation gates
  const isWaitingConfigurableGate = [
    'waiting_expert_validation',
    'waiting_sds_validation',
    'waiting_build_validation',
  ].includes(normalizedMainStatus);
  const canDownload = isCompleted && progress?.sds_document_path;

  // H15-FE FIX 3: Compute granular progress from individual agent progress values.
  // Backend overall_progress uses binary completed/total count (e.g. 2/11 = 18%).
  // Individual agent progress values (0-100) give a more accurate picture.
  const effectiveProgress = (() => {
    const backendProgress = progress?.overall_progress || 0;
    if (!progress?.agent_progress?.length) return backendProgress;
    const agents = progress.agent_progress;
    const granular = Math.round(
      agents.reduce((sum, a) => {
        const p = normalizeStatus(a.status) === 'completed' ? 100 : (a.progress || 0);
        return sum + p;
      }, 0) / agents.length
    );
    return Math.max(backendProgress, granular);
  })();

  // H12: Extract architecture coverage data from agent progress
  const getArchitectureCoverageData = () => {
    if (!isWaitingArchitectureValidation || !progress) return null;
    const researchAgent = progress.agent_progress?.find(
      (a) => a.agent_name?.includes('Emma') || a.agent_name?.includes('Research')
    );
    // The extra_data is embedded in the progress response from backend
    return researchAgent || null;
  };

  const handleArchitectureAction = async (action: 'approve_architecture' | 'revise_architecture') => {
    if (!executionId) return;
    setIsArchAction(true);
    try {
      await executions.resume(Number(executionId), action);
      // Restart polling
      if (pollingRef.current) clearInterval(pollingRef.current);
      pollingRef.current = setInterval(async () => {
        const data = await executions.getProgress(Number(executionId));
        setProgress(data);
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled' || data.status === 'waiting_architecture_validation') {
          if (pollingRef.current) clearInterval(pollingRef.current);
        }
      }, 3000);
    } catch (err: any) {
      setError(err.message || `Failed to ${action}`);
    } finally {
      setIsArchAction(false);
    }
  };

  // P2-Full: Handle resume after configurable gate validation
  const handleGateResume = () => {
    setPendingGateData(null);
    // Restart polling
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        const data = await executions.getProgress(Number(executionId));
        setProgress(data);
        const stopStatuses = [
          'completed', 'failed', 'cancelled',
          'waiting_br_validation', 'waiting_architecture_validation',
          'waiting_expert_validation', 'waiting_sds_validation', 'waiting_build_validation',
        ];
        if (stopStatuses.includes(data?.status)) {
          if (pollingRef.current) clearInterval(pollingRef.current);
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 3000);
  };

  // H7: BUILD agents to hide during SDS phase (they show "Waiting..." which is confusing)
  const BUILD_AGENT_IDS = ['apex', 'lwc', 'admin'];
  const isExecutionDone = isCompleted || isFailed || isCancelled;

  const filteredAgentProgress = progress?.agent_progress?.filter((agentProg) => {
    if (isExecutionDone) return true; // Show all agents when execution is finished
    const agentNameLower = agentProg.agent_name.toLowerCase();
    const matchedAgent = AGENTS.find((a) => agentNameLower.startsWith(a.name.toLowerCase()));
    // Hide BUILD agents that are still pending during active execution (SDS phase)
    if (matchedAgent && BUILD_AGENT_IDS.includes(matchedAgent.id) && normalizeStatus(agentProg.status) === 'pending') {
      return false;
    }
    return true;
  });

  // UX1: Find the active agent (currently running)
  const activeAgentProgress = filteredAgentProgress?.find(
    (a) => normalizeStatus(a.status) === 'in_progress' || normalizeStatus(a.status) === 'running'
  );

  // UX1: Compute timeline phases
  const timelinePhases = progress ? getPhaseStatus(progress) : [];

  return (
    <div className="min-h-screen bg-[#0B1120]">
      <Navbar />

      {/* Background Effects */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
        <div className="absolute top-[-20%] right-[-10%] w-[600px] h-[600px] bg-purple-900/20 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-20%] left-[-10%] w-[600px] h-[600px] bg-cyan-900/15 rounded-full blur-[150px]" />
      </div>

      <main className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-extrabold text-white">Execution Monitor</h1>
            <p className="text-slate-400 mt-1">
              {isCancelled ? 'Execution Cancelled' : (progress?.current_phase || 'Initializing...')}
            </p>
          </div>

          {canDownload && (
            <button
              onClick={handleDownload}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white font-medium rounded-xl hover:from-green-600 hover:to-emerald-700 transition-all shadow-lg shadow-green-500/25"
            >
              <Download className="w-5 h-5" />
              Download SDS
            </button>
          )}
        </div>

        {error && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400">
            {error}
          </div>
        )}

        {/* UX1: Timeline Stepper — always visible */}
        <TimelineStepper phases={timelinePhases} onPhaseClick={handlePhaseClick} />

        {/* BR Validation Required */}
        {isWaitingBRValidation && (
          <div className="mb-6 bg-amber-500/10 border border-amber-500/30 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                <ClipboardList className="w-6 h-6 text-amber-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-amber-400 mb-2">
                  Business Requirements Validation Required
                </h3>
                <p className="text-slate-300 mb-4">
                  Sophie has extracted the Business Requirements from your project.
                  Please review, modify, add or remove requirements before continuing with the analysis.
                </p>
                <button
                  onClick={() => navigate(`/br-validation/${progress?.project_id}?executionId=${progress?.execution_id}`)}
                  className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-amber-500 to-orange-600 text-white font-medium rounded-xl hover:from-amber-600 hover:to-orange-700 transition-all shadow-lg shadow-amber-500/25"
                >
                  <ClipboardList className="w-5 h-5" />
                  Review & Validate Requirements
                </button>
              </div>
            </div>
          </div>
        )}

        {/* H12: Architecture Coverage Validation */}
        {isWaitingArchitectureValidation && (
          <div className="mb-6 bg-blue-500/10 border border-blue-500/30 rounded-xl p-6">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                <ShieldCheck className="w-6 h-6 text-blue-400" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-blue-400 mb-2">
                  Architecture Coverage Validation
                </h3>
                <p className="text-slate-300 mb-4">
                  Emma (Research Analyst) has validated the solution architecture against your use cases.
                  The coverage score is between 70-94%. Please review and decide whether to approve or request a revision.
                </p>

                {/* Coverage info from agent progress */}
                {(() => {
                  const researchAgent = getArchitectureCoverageData();
                  const extraData = researchAgent?.extra_data;
                  const score = extraData?.coverage_score ?? null;
                  const criticalGaps = extraData?.critical_gaps || [];
                  const uncoveredUCs = extraData?.uncovered_use_cases || [];
                  const revisionCount = extraData?.revision_count ?? 0;

                  return (
                    <div className="mb-4 space-y-3">
                      {score !== null && (
                        <div>
                          <div className="flex items-center gap-3">
                            <span className="text-slate-400">
                              {revisionCount > 0
                                ? `Score after ${revisionCount} revision${revisionCount > 1 ? 's' : ''}:`
                                : 'Coverage Score:'}
                            </span>
                            <span className={`text-2xl font-bold ${
                              score >= 85 ? 'text-green-400' : score >= 70 ? 'text-orange-400' : 'text-red-400'
                            }`}>
                              {Math.round(score)}%
                            </span>
                          </div>
                          <p className={`text-sm mt-1 ${
                            score >= 85 ? 'text-green-400' : score >= 70 ? 'text-orange-400' : 'text-red-400'
                          }`}>
                            {score >= 85
                              ? 'Good coverage'
                              : score >= 70
                              ? 'Acceptable — review gaps below'
                              : 'Insufficient — revision recommended'}
                          </p>
                        </div>
                      )}
                      {criticalGaps.length > 0 && (
                        <div>
                          <p className="text-slate-400 text-sm font-medium mb-1">Critical Gaps ({criticalGaps.length}):</p>
                          <ul className="space-y-1">
                            {criticalGaps.map((gap, i) => (
                              <li key={i} className="text-slate-300 text-sm flex items-start gap-2">
                                <span className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${
                                  gap.severity === 'high' ? 'bg-red-400' : gap.severity === 'medium' ? 'bg-orange-400' : 'bg-yellow-400'
                                }`} />
                                <span>
                                  <span className={`font-medium ${
                                    gap.severity === 'high' ? 'text-red-400' : gap.severity === 'medium' ? 'text-orange-400' : 'text-yellow-400'
                                  }`}>[{gap.severity}]</span>{' '}
                                  {gap.gap}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {uncoveredUCs.length > 0 && (
                        <div>
                          <p className="text-slate-400 text-sm font-medium mb-1">Uncovered Use Cases ({uncoveredUCs.length}):</p>
                          <ul className="space-y-1">
                            {uncoveredUCs.map((uc, i) => (
                              <li key={i} className="text-slate-300 text-sm">&bull; {uc}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })()}

                <div className="flex gap-3">
                  <button
                    onClick={() => handleArchitectureAction('approve_architecture')}
                    disabled={isArchAction}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-green-500 to-emerald-600 text-white font-medium rounded-xl hover:from-green-600 hover:to-emerald-700 transition-all shadow-lg shadow-green-500/25 disabled:opacity-50"
                  >
                    <CheckCircle className="w-4 h-4" />
                    {isArchAction ? 'Processing...' : 'Approve Architecture'}
                  </button>
                  <button
                    onClick={() => handleArchitectureAction('revise_architecture')}
                    disabled={isArchAction}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-indigo-700 transition-all shadow-lg shadow-blue-500/25 disabled:opacity-50"
                  >
                    <RefreshCcw className="w-4 h-4" />
                    {isArchAction ? 'Processing...' : 'Revise Architecture'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* P2-Full: Configurable validation gate panel */}
        {isWaitingConfigurableGate && pendingGateData && progress?.execution_id && (
          <ValidationGatePanel
            executionId={progress.execution_id}
            pending={pendingGateData}
            onResume={handleGateResume}
          />
        )}

        {/* UX1: Deliverable Viewer — shown when a completed phase is clicked */}
        {selectedPhase !== null && progress?.execution_id && (
          <DeliverableViewer
            executionId={progress.execution_id}
            phaseNumber={selectedPhase}
            onClose={() => setSelectedPhase(null)}
          />
        )}

        {/* H6: SDS v3 Generator - Show only when SDS standard execution is done */}
        {(isCompleted || normalizedMainStatus === 'sds_generated') && progress?.execution_id && (
          <div className="mb-8">
            <SDSv3Generator
              executionId={progress.execution_id}
              projectName={`Project_${progress.project_id}`}
              onComplete={() => {
                // Refresh progress after generation
                window.location.reload();
              }}
            />
          </div>
        )}

        {/* Overall Progress */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <span className="text-white font-medium">Overall Progress</span>
            <span className="text-cyan-400 font-bold">{effectiveProgress}%</span>
          </div>
          <div className="h-4 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                isFailed
                  ? 'bg-gradient-to-r from-red-500 to-red-600'
                  : isCompleted
                  ? 'bg-gradient-to-r from-green-500 to-emerald-500'
                  : 'bg-gradient-to-r from-cyan-500 to-purple-500'
              }`}
              style={{ width: `${effectiveProgress}%` }}
            />
          </div>
          {/* I1.4: Cost badge */}
          {budget && (
            <div className="mt-2 flex items-center justify-end">
              <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium ${
                (budget.execution_cost || 0) > 40
                  ? 'bg-red-500/15 text-red-400 border border-red-500/30'
                  : (budget.execution_cost || 0) > 20
                  ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                  : 'bg-slate-700/50 text-slate-400 border border-slate-600'
              }`}>
                Cost: ${(budget.execution_cost || 0).toFixed(2)} / $50.00
              </span>
            </div>
          )}
          <div className="mt-4 flex items-center gap-2">
            {isCompleted && (
              <span className="inline-flex items-center gap-1 text-green-400 text-sm">
                <CheckCircle className="w-4 h-4" /> Completed successfully
              </span>
            )}
            {isFailed && (
              <div className="flex items-center gap-4">
                <span className="inline-flex items-center gap-1 text-red-400 text-sm">
                  <AlertCircle className="w-4 h-4" /> Execution failed
                </span>
                <button
                  onClick={handleRetry}
                  disabled={isRetrying}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-600 text-white font-medium rounded-lg hover:from-amber-600 hover:to-orange-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isRetrying ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Retrying...
                    </>
                  ) : (
                    <>
                      <RotateCcw className="w-4 h-4" />
                      Retry Execution
                    </>
                  )}
                </button>
              </div>
            )}
            {retryError && (
              <span className="text-red-400 text-sm ml-4">{retryError}</span>
            )}
            {!isCompleted && !isFailed && (
              <span className="inline-flex items-center gap-1 text-cyan-400 text-sm">
                {isCancelled ? 'Cancelled' : <><RefreshCw className="w-4 h-4 animate-spin" /> Processing...</>}
              </span>
            )}
          </div>
        </div>

        {/* UX1: Active Agent Detail — highlight the currently running agent */}
        {activeAgentProgress && !isExecutionDone && (() => {
          const agentNameLower = activeAgentProgress.agent_name.toLowerCase();
          const agent = AGENTS.find((a) => {
            const nameMatch = agentNameLower.startsWith(a.name.toLowerCase());
            const idFromName = agentNameLower.includes('(')
              ? agentNameLower.split('(')[1]?.replace(')', '').trim().replace(' ', '_')
              : '';
            const idMatch = a.id === idFromName || agentNameLower === a.id;
            return nameMatch || idMatch;
          });
          const status = normalizeStatus(activeAgentProgress.status);
          const config = getStatusConfig(status);
          const StatusIcon = config.icon;

          return (
            <div className="bg-slate-800/50 backdrop-blur-sm border border-cyan-500/30 rounded-2xl p-6 mb-8">
              <h2 className="text-lg font-bold text-white mb-4">Active Agent</h2>
              <div
                onClick={() => handleAgentClick(activeAgentProgress)}
                className="flex items-center gap-4 cursor-pointer group"
              >
                <Avatar
                  src={agent?.avatar || '/avatars/default.png'}
                  alt={activeAgentProgress.agent_name}
                  size="md"
                  isActive={true}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-white group-hover:text-cyan-400 transition-colors">
                      {activeAgentProgress.agent_name}
                    </p>
                    <StatusIcon className={`w-4 h-4 ${config.color}`} />
                  </div>
                  <p className="text-sm text-slate-400">{agent?.role || 'Agent'}</p>
                  <p className="text-sm text-slate-500 mt-1 break-words">
                    {activeAgentProgress.current_task || 'Working...'}
                  </p>
                </div>
                <div className="w-32 flex-shrink-0">
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${config.bgColor} transition-all duration-300`}
                      style={{ width: `${activeAgentProgress.progress}%` }}
                    />
                  </div>
                  <p className="text-xs text-slate-500 text-right mt-1">{activeAgentProgress.progress}%</p>
                </div>
              </div>
            </div>
          );
        })()}

        {/* UX1: All Agents — collapsible accordion */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl overflow-hidden">
          <button
            onClick={() => setAllAgentsExpanded(!allAgentsExpanded)}
            className="w-full flex items-center justify-between p-6 text-left hover:bg-slate-700/20 transition-colors"
          >
            <div>
              <h2 className="text-xl font-bold text-white">All Agents</h2>
              <p className="text-sm text-slate-400 mt-1">
                {filteredAgentProgress?.length || 0} agents &middot; Click to {allAgentsExpanded ? 'collapse' : 'expand'}
              </p>
            </div>
            {allAgentsExpanded ? (
              <ChevronUp className="w-5 h-5 text-slate-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-slate-400" />
            )}
          </button>

          {allAgentsExpanded && (
            <div className="px-6 pb-6">
              <p className="text-sm text-slate-400 mb-4">Click on an agent to see their thought process</p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredAgentProgress?.map((agentProg) => {
                  // Flexible agent matching: by name prefix or by ID extracted from parentheses
                  const agentNameLower = agentProg.agent_name.toLowerCase();
                  const agent = AGENTS.find((a) => {
                    const nameMatch = agentNameLower.startsWith(a.name.toLowerCase());
                    const idFromName = agentNameLower.includes('(')
                      ? agentNameLower.split('(')[1]?.replace(')', '').trim().replace(' ', '_')
                      : '';
                    const idMatch = a.id === idFromName || agentNameLower === a.id;
                    return nameMatch || idMatch;
                  });
                  const status = normalizeStatus(agentProg.status);
                  const config = getStatusConfig(status);
                  const StatusIcon = config.icon;

                  return (
                    <div
                      key={agentProg.agent_name}
                      onClick={() => handleAgentClick(agentProg)}
                      className="bg-slate-900/50 border border-slate-600 rounded-xl p-4 hover:border-cyan-500/50 cursor-pointer transition-all group"
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <Avatar
                          src={agent?.avatar || '/avatars/default.png'}
                          alt={agentProg.agent_name}
                          size="md"
                          isActive={status === 'running' || status === 'in_progress'}
                        />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-white truncate group-hover:text-cyan-400 transition-colors">
                            {agentProg.agent_name}
                          </p>
                          <p className="text-xs text-slate-400">{agent?.role || 'Agent'}</p>
                        </div>
                        <StatusIcon className={`w-5 h-5 ${config.color}`} />
                      </div>

                      {/* Progress bar */}
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden mb-2">
                        <div
                          className={`h-full ${config.bgColor} transition-all duration-300`}
                          style={{ width: `${agentProg.progress}%` }}
                        />
                      </div>

                      <p className="text-xs text-slate-500 break-words">
                        {agentProg.current_task || agentProg.output_summary || 'Waiting...'}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Agent Thought Modal */}
      {selectedAgent && (
        <AgentThoughtModal
          agent={selectedAgent}
          isOpen={!!selectedAgent}
          onClose={() => setSelectedAgent(null)}
          currentTask={selectedAgentTask}
          outputSummary={selectedAgentOutput}
          status={selectedAgentStatus}
        />
      )}
    </div>
  );
}
