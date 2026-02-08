import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Loader2, CheckCircle, AlertCircle, Clock, Play, Pause, 
  Code, Database, Wrench, TestTube, Rocket, GraduationCap,
  RefreshCw, ChevronDown, ChevronUp, Terminal, GitCommit
} from 'lucide-react';
import Navbar from '../components/Navbar';
import Avatar from '../components/ui/Avatar';
import { api } from '../services/api';
import BuildPhasesPanel from '../components/BuildPhasesPanel';
import type { PhaseExecution } from '../components/BuildPhasesPanel';

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
}

const AGENT_INFO: Record<string, { name: string; role: string; icon: typeof Code; color: string }> = {
  diego: { name: 'Diego', role: 'Apex Developer', icon: Code, color: 'from-orange-500 to-amber-500' },
  zara: { name: 'Zara', role: 'LWC Developer', icon: Wrench, color: 'from-pink-500 to-rose-500' },
  raj: { name: 'Raj', role: 'SF Admin', icon: Database, color: 'from-blue-500 to-indigo-500' },
  aisha: { name: 'Aisha', role: 'Data Migration', icon: Database, color: 'from-emerald-500 to-teal-500' },
  elena: { name: 'Elena', role: 'QA Engineer', icon: TestTube, color: 'from-purple-500 to-violet-500' },
  jordan: { name: 'Jordan', role: 'DevOps', icon: Rocket, color: 'from-red-500 to-orange-500' },
  lucas: { name: 'Lucas', role: 'Trainer', icon: GraduationCap, color: 'from-cyan-500 to-blue-500' },
  marcus: { name: 'Marcus', role: 'Architect', icon: Code, color: 'from-slate-500 to-gray-500' },
};

const STATUS_CONFIG: Record<string, { color: string; bgColor: string; icon: typeof CheckCircle; label: string }> = {
  pending: { color: 'text-slate-400', bgColor: 'bg-slate-600', icon: Clock, label: 'Pending' },
  running: { color: 'text-cyan-400', bgColor: 'bg-cyan-500', icon: Play, label: 'Running' },
  deploying: { color: 'text-yellow-400', bgColor: 'bg-yellow-500', icon: Rocket, label: 'Deploying' },
  testing: { color: 'text-purple-400', bgColor: 'bg-purple-500', icon: TestTube, label: 'Testing' },
  passed: { color: 'text-green-400', bgColor: 'bg-green-500', icon: CheckCircle, label: 'Passed' },
  committing: { color: 'text-blue-400', bgColor: 'bg-blue-500', icon: GitCommit, label: 'Committing' },
  completed: { color: 'text-green-400', bgColor: 'bg-green-600', icon: CheckCircle, label: 'Completed' },
  failed: { color: 'text-red-400', bgColor: 'bg-red-500', icon: AlertCircle, label: 'Failed' },
  skipped: { color: 'text-slate-500', bgColor: 'bg-slate-700', icon: Pause, label: 'Skipped' },
  blocked: { color: 'text-orange-400', bgColor: 'bg-orange-500', icon: Clock, label: 'Blocked' },
};

export default function BuildMonitoringPage() {
  const { executionId } = useParams<{ executionId: string }>();
  const navigate = useNavigate();
  
  const [data, setData] = useState<BuildTasksResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set(['apex', 'lwc', 'admin']));
  const [selectedTask, setSelectedTask] = useState<TaskInfo | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [phases, setPhases] = useState<PhaseExecution[]>([]);
  const [currentPhase, setCurrentPhase] = useState<number | undefined>();
  
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    fetchBuildTasks();
    fetchPhases();
    
    // Poll every 3 seconds
    pollingRef.current = setInterval(fetchBuildTasks, 3000);
    
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [executionId]);

  const fetchBuildTasks = async () => {
    try {
      const response = await api.get(`/api/pm-orchestrator/execute/${executionId}/build-tasks`);
      setData(response);
      setIsLoading(false);
      setIsPaused(response.execution_status === 'paused' || (response.metadata?.build_paused === true));
      
      // Stop polling if build is complete
      if (response.execution_status === 'COMPLETED' || response.execution_status === 'FAILED') {
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      }
    } catch (err: any) {
      if (!data) setError(err.message || 'Failed to load build tasks');
      setIsLoading(false);
    }
  };
  
  // BUILD v2: Fetch phase status
  const fetchPhases = async () => {
    try {
      const response = await api.get(`/api/pm-orchestrator/execute/${executionId}/build-phases`);
      setPhases(response.phases || []);
      setCurrentPhase(response.current_phase);
    } catch (err) {
      console.warn("Failed to fetch phases (BUILD v2 not active):", err);
    }
  };

  const toggleAgent = (agentId: string) => {
    setExpandedAgents(prev => {
      const next = new Set(prev);
      if (next.has(agentId)) next.delete(agentId);
      else next.add(agentId);
      return next;
    });
  };

  const getStatusConfig = (status: string) => {
    return STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0B1120] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-cyan-500 animate-spin mx-auto" />
          <p className="text-slate-400 mt-4">Loading BUILD phase...</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-screen bg-[#0B1120] flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto" />
          <p className="text-red-400 mt-4">{error}</p>
          <button 
            onClick={() => navigate(-1)}
            className="mt-4 px-4 py-2 bg-slate-700 text-white rounded-lg"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  const stats = data?.build_phase;
  const tasksByAgent = data?.tasks_by_agent || {};

  const handlePause = async () => {
    setActionLoading(true);
    try {
      await api.post(`/api/pm-orchestrator/execute/${executionId}/pause-build`);
      setIsPaused(true);
    } catch (err) {
      console.error('Pause failed:', err);
    }
    setActionLoading(false);
  };

  const handleResume = async () => {
    setActionLoading(true);
    try {
      await api.post(`/api/pm-orchestrator/execute/${executionId}/resume-build`);
      setIsPaused(false);
    } catch (err) {
      console.error('Resume failed:', err);
    }
    setActionLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#0B1120]">
      <Navbar />

      {/* Background Effects */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
        <div className="absolute top-[-20%] right-[-10%] w-[600px] h-[600px] bg-orange-900/20 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-20%] left-[-10%] w-[600px] h-[600px] bg-cyan-900/15 rounded-full blur-[150px]" />
      </div>

      <main className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">BUILD Phase Monitor</h1>
              <p className="text-slate-400">
                Execution #{executionId} • {data?.execution_status}
              </p>
            </div>
            <div className="flex gap-3">
              {data?.execution_status === 'running' || data?.execution_status === 'building' ? (
                isPaused ? (
                  <button
                    onClick={handleResume}
                    disabled={actionLoading}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-colors disabled:opacity-50"
                  >
                    <Play className="w-4 h-4" />
                    Resume
                  </button>
                ) : (
                  <button
                    onClick={handlePause}
                    disabled={actionLoading}
                    className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded-lg transition-colors disabled:opacity-50"
                  >
                    <Pause className="w-4 h-4" />
                    Pause
                  </button>
                )
              ) : null}
              <button
                onClick={fetchBuildTasks}
                className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            </div>
          </div>
        </div>

        {/* Progress Overview */}
        {stats && (
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">Overall Progress</h2>
              <span className="text-2xl font-bold text-cyan-400">{stats.progress_percent}%</span>
            </div>
            
            {/* Progress Bar */}
            <div className="h-4 bg-slate-700 rounded-full overflow-hidden mb-4">
              <div 
                className="h-full bg-gradient-to-r from-cyan-500 to-green-500 transition-all duration-500"
                style={{ width: `${stats.progress_percent}%` }}
              />
            </div>
            
            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center p-3 bg-slate-900/50 rounded-lg">
                <div className="text-2xl font-bold text-white">{stats.total_tasks}</div>
                <div className="text-xs text-slate-400">Total Tasks</div>
              </div>
              <div className="text-center p-3 bg-slate-900/50 rounded-lg">
                <div className="text-2xl font-bold text-green-400">{stats.completed}</div>
                <div className="text-xs text-slate-400">Completed</div>
              </div>
              <div className="text-center p-3 bg-slate-900/50 rounded-lg">
                <div className="text-2xl font-bold text-cyan-400">{stats.running}</div>
                <div className="text-xs text-slate-400">Running</div>
              </div>
              <div className="text-center p-3 bg-slate-900/50 rounded-lg">
                <div className="text-2xl font-bold text-red-400">{stats.failed}</div>
                <div className="text-xs text-slate-400">Failed</div>
              </div>
              <div className="text-center p-3 bg-slate-900/50 rounded-lg">
                <div className="text-2xl font-bold text-slate-400">{stats.pending}</div>
                <div className="text-xs text-slate-400">Pending</div>
              </div>
            </div>
          </div>
        )}

        {/* BUILD v2 Phases Panel */}
        {phases.length > 0 && (
          <div className="mb-8">
            <BuildPhasesPanel phases={phases} currentPhase={currentPhase} />
          </div>
        )}

        {/* Tasks by Agent */}
        <div className="space-y-4">
          {Object.entries(tasksByAgent).map(([agentId, tasks]) => {
            const agentInfo = AGENT_INFO[agentId] || { name: agentId, role: 'Agent', icon: Code, color: 'from-slate-500 to-slate-600' };
            const IconComponent = agentInfo.icon;
            const isExpanded = expandedAgents.has(agentId);
            const completedCount = tasks.filter(t => t.status === 'completed' || t.status === 'passed').length;
            const runningCount = tasks.filter(t => t.status === 'running').length;
            
            return (
              <div key={agentId} className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl overflow-hidden">
                {/* Agent Header */}
                <div 
                  className="p-4 flex items-center justify-between cursor-pointer hover:bg-slate-700/30 transition-colors"
                  onClick={() => toggleAgent(agentId)}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${agentInfo.color} flex items-center justify-center`}>
                      <agentInfo.icon className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h3 className="text-white font-semibold">{agentInfo.name}</h3>
                      <p className="text-slate-400 text-sm">{agentInfo.role}</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-4">
                    {/* Mini stats */}
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-green-400">{completedCount}/{tasks.length}</span>
                      {runningCount > 0 && (
                        <span className="flex items-center gap-1 text-cyan-400">
                          <Loader2 className="w-3 h-3 animate-spin" />
                          {runningCount}
                        </span>
                      )}
                    </div>
                    
                    {/* Progress mini bar */}
                    <div className="w-24 h-2 bg-slate-700 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-green-500"
                        style={{ width: `${(completedCount / tasks.length) * 100}%` }}
                      />
                    </div>
                    
                    {isExpanded ? (
                      <ChevronUp className="w-5 h-5 text-slate-400" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-slate-400" />
                    )}
                  </div>
                </div>
                
                {/* Tasks List */}
                {isExpanded && (
                  <div className="border-t border-slate-700">
                    {tasks.map(task => {
                      const statusConfig = getStatusConfig(task.status);
                      const StatusIcon = statusConfig.icon;
                      
                      return (
                        <div 
                          key={task.task_id}
                          className="p-4 border-b border-slate-700/50 last:border-0 hover:bg-slate-700/20 transition-colors cursor-pointer"
                          onClick={() => setSelectedTask(task)}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <StatusIcon className={`w-5 h-5 ${statusConfig.color}`} />
                              <div>
                                <p className="text-white font-medium">{task.task_name}</p>
                                <p className="text-slate-500 text-xs">{task.task_id} • {task.phase_name}</p>
                              </div>
                            </div>
                            
                            <div className="flex items-center gap-3">
                              {task.attempt_count > 1 && (
                                <span className="text-orange-400 text-xs">
                                  Attempt {task.attempt_count}
                                </span>
                              )}
                              {task.git_commit_sha && (
                                <span className="text-slate-500 text-xs font-mono">
                                  {task.git_commit_sha.slice(0, 7)}
                                </span>
                              )}
                              <span className={`px-2 py-1 rounded text-xs ${statusConfig.bgColor} text-white`}>
                                {statusConfig.label}
                              </span>
                            </div>
                          </div>
                          
                          {task.last_error && task.status === 'failed' && (
                            <div className="mt-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-xs">
                              <Terminal className="w-3 h-3 inline mr-1" />
                              {task.last_error.slice(0, 150)}...
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        
        {/* Empty state */}
        {Object.keys(tasksByAgent).length === 0 && (
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-12 text-center">
            <Clock className="w-12 h-12 text-slate-500 mx-auto mb-4" />
            <h3 className="text-white text-lg font-semibold mb-2">No BUILD tasks yet</h3>
            <p className="text-slate-400">
              BUILD phase tasks will appear here once the SDS is approved and build starts.
            </p>
          </div>
        )}

        {/* Task Detail Modal */}
        {selectedTask && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedTask(null)} />
            <div className="relative bg-slate-800 border border-slate-600 rounded-2xl w-full max-w-lg overflow-hidden">
              <div className="p-6 border-b border-slate-700">
                <h3 className="text-xl font-bold text-white">{selectedTask.task_name}</h3>
                <p className="text-slate-400 text-sm">{selectedTask.task_id}</p>
              </div>
              <div className="p-6 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-slate-400 text-sm">Status</p>
                    <p className={`font-medium ${getStatusConfig(selectedTask.status).color}`}>
                      {getStatusConfig(selectedTask.status).label}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Phase</p>
                    <p className="text-white">{selectedTask.phase_name}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Attempts</p>
                    <p className="text-white">{selectedTask.attempt_count}</p>
                  </div>
                  <div>
                    <p className="text-slate-400 text-sm">Agent</p>
                    <p className="text-white">{AGENT_INFO[selectedTask.assigned_agent]?.name || selectedTask.assigned_agent}</p>
                  </div>
                </div>
                
                {selectedTask.last_error && (
                  <div>
                    <p className="text-slate-400 text-sm mb-2">Last Error</p>
                    <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm font-mono">
                      {selectedTask.last_error}
                    </div>
                  </div>
                )}
                
                {selectedTask.git_commit_sha && (
                  <div>
                    <p className="text-slate-400 text-sm mb-1">Git Commit</p>
                    <p className="text-green-400 font-mono">{selectedTask.git_commit_sha}</p>
                  </div>
                )}
              </div>
              <div className="p-6 border-t border-slate-700 flex justify-end">
                <button
                  onClick={() => setSelectedTask(null)}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
