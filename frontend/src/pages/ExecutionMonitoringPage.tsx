import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Download, Loader2, CheckCircle, AlertCircle, Clock, Zap, RefreshCw, RefreshCcw, ClipboardList, RotateCcw } from 'lucide-react';
import { executions } from '../services/api';
import Navbar from '../components/Navbar';
import Avatar from '../components/ui/Avatar';
import AgentThoughtModal from '../components/AgentThoughtModal';
import { AGENTS } from '../constants';

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
}

interface ExecutionProgress {
  execution_id: number;
  project_id: number;
  status: string;
  overall_progress: number;
  current_phase?: string;
  agent_progress: AgentProgress[];
  sds_document_path?: string;
}

export default function ExecutionMonitoringPage() {
  const { executionId } = useParams<{ executionId: string }>();
  const navigate = useNavigate();
  const [progress, setProgress] = useState<ExecutionProgress | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  // Thought modal state
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [selectedAgentTask, setSelectedAgentTask] = useState<string>('');
  const [selectedAgentOutput, setSelectedAgentOutput] = useState<string>('');
  const [selectedAgentStatus, setSelectedAgentStatus] = useState<string>('');
  
  // ORCH-04: Retry state
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');

  // FRNT-02: Compare progress to avoid unnecessary re-renders that cause scroll jumps
  const hasProgressChanged = (oldData: ExecutionProgress | null, newData: ExecutionProgress | null): boolean => {
    if (!oldData || !newData) return true;
    if (oldData.status !== newData.status) return true;
    if (oldData.overall_progress !== newData.overall_progress) return true;
    if (oldData.agent_progress?.length !== newData.agent_progress?.length) return true;
    // Check if any agent status or progress changed
    for (let i = 0; i < (oldData.agent_progress?.length || 0); i++) {
      const oldAgent = oldData.agent_progress[i];
      const newAgent = newData.agent_progress?.find(a => a.agent_name === oldAgent.agent_name);
      if (!newAgent) return true;
      if (oldAgent.status !== newAgent.status || oldAgent.progress !== newAgent.progress) return true;
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

        // Stop polling if completed or failed
        if (data?.status === 'completed' || data?.status === 'failed' || data?.status === 'cancelled' || data?.status === 'waiting_br_validation') {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
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
      const result = await executions.retry(Number(executionId));
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
  const canDownload = isCompleted && progress?.sds_document_path;

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
        <div className="mb-10 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-extrabold text-white">Execution Monitor</h1>
            <p className="text-slate-400 mt-1">
              {isCancelled ? '❌ Execution Cancelled' : (progress?.current_phase || 'Initializing...')}
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

        {/* Overall Progress */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <span className="text-white font-medium">Overall Progress</span>
            <span className="text-cyan-400 font-bold">{progress?.overall_progress || 0}%</span>
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
              style={{ width: `${progress?.overall_progress || 0}%` }}
            />
          </div>
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
                {isCancelled ? '❌ Cancelled' : <><RefreshCw className="w-4 h-4 animate-spin" /> Processing...</>}
              </span>
            )}
          </div>
        </div>

        {/* Agent Progress Grid */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6">
          <h2 className="text-xl font-bold text-white mb-6">Agent Activity</h2>
          <p className="text-sm text-slate-400 mb-6">Click on an agent to see their thought process</p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {progress?.agent_progress?.map((agentProg) => {
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

                  <p className="text-xs text-slate-500 truncate">
                    {agentProg.current_task || agentProg.output_summary || 'Waiting...'}
                  </p>
                </div>
              );
            })}
          </div>
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
