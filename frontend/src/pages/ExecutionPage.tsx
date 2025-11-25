import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Play, Loader2, Users, FileText, ArrowRight, CheckCircle } from 'lucide-react';
import { projects, executions } from '../services/api';
import Navbar from '../components/Navbar';
import Avatar from '../components/ui/Avatar';
import { AGENTS, MANDATORY_AGENTS } from '../constants';

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

export default function ExecutionPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchProject = async () => {
      try {
        const data = await projects.get(Number(projectId));
        setProject(data);
        // Use agents from project or default to all agents
        if (data.selected_agents && data.selected_agents.length > 0) {
          setSelectedAgents(data.selected_agents);
        } else {
          // Default: all agents
          setSelectedAgents(AGENTS.map(a => a.id));
        }
      } catch (err) {
        console.error('Failed to fetch project:', err);
        setError('Failed to load project');
      } finally {
        setIsLoading(false);
      }
    };

    if (projectId) {
      fetchProject();
    }
  }, [projectId]);

  const handleStartExecution = async () => {
    if (!project) return;

    setIsStarting(true);
    setError('');

    try {
      const result = await executions.start(project.id, selectedAgents);
      navigate(`/execution/${result.execution_id}/monitor`);
    } catch (err: any) {
      console.error('Failed to start execution:', err);
      if (err.detail) {
        setError(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
      } else {
        setError(err.message || 'Failed to start execution');
      }
    } finally {
      setIsStarting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0B1120] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-cyan-500 animate-spin mx-auto" />
          <p className="text-slate-400 mt-4">Loading project...</p>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="min-h-screen bg-[#0B1120] flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400">Project not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0B1120]">
      <Navbar />

      {/* Background Effects */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none">
        <div className="absolute top-[-20%] right-[-10%] w-[600px] h-[600px] bg-purple-900/20 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-20%] left-[-10%] w-[600px] h-[600px] bg-cyan-900/15 rounded-full blur-[150px]" />
      </div>

      <main className="relative max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Header */}
        <div className="mb-10 text-center">
          <h1 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-500">
            Ready to Launch
          </h1>
          <p className="mt-2 text-slate-400">Review your project and start the AI execution</p>
        </div>

        {error && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400">
            {error}
          </div>
        )}

        {/* Project Summary */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center">
              <FileText className="w-5 h-5 text-cyan-400" />
            </div>
            <h2 className="text-xl font-bold text-white">Project Summary</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-sm text-slate-400">Project Name</p>
              <p className="text-white font-medium">{project.name}</p>
            </div>
            <div>
              <p className="text-sm text-slate-400">Salesforce Product</p>
              <p className="text-white font-medium">{project.salesforce_product || 'Not specified'}</p>
            </div>
            <div>
              <p className="text-sm text-slate-400">Organization Type</p>
              <p className="text-white font-medium">{project.organization_type || 'Not specified'}</p>
            </div>
            <div>
              <p className="text-sm text-slate-400">Status</p>
              <p className="text-cyan-400 font-medium capitalize">{project.status}</p>
            </div>
          </div>

          {project.business_requirements && (
            <div className="mt-4 pt-4 border-t border-slate-700">
              <p className="text-sm text-slate-400 mb-2">Business Requirements</p>
              <p className="text-slate-300 text-sm max-h-32 overflow-y-auto">
                {project.business_requirements}
              </p>
            </div>
          )}
        </div>

        {/* Selected Agents */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 mb-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
              <Users className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">AI Team ({selectedAgents.length} agents)</h2>
              <p className="text-sm text-slate-400">These agents will work on your project</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            {selectedAgents.map((agentId) => {
              const agent = AGENTS.find(a => a.id === agentId);
              if (!agent) return null;
              const isMandatory = MANDATORY_AGENTS.includes(agentId);

              return (
                <div
                  key={agentId}
                  className="flex items-center gap-2 px-3 py-2 bg-slate-700/50 rounded-xl border border-slate-600"
                >
                  <Avatar src={agent.avatar} alt={agent.name} size="sm" />
                  <div>
                    <p className="text-sm text-white font-medium">{agent.name}</p>
                    <p className="text-xs text-slate-400">{agent.role}</p>
                  </div>
                  {isMandatory && (
                    <CheckCircle className="w-4 h-4 text-green-400" />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Launch Button */}
        <div className="flex justify-center">
          <button
            onClick={handleStartExecution}
            disabled={isStarting || selectedAgents.length === 0}
            className="inline-flex items-center gap-3 px-12 py-5 bg-gradient-to-r from-cyan-500 to-purple-600 text-white text-xl font-semibold rounded-2xl hover:from-cyan-600 hover:to-purple-700 transition-all shadow-xl shadow-cyan-500/30 hover:shadow-cyan-500/50 disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-105"
          >
            {isStarting ? (
              <>
                <Loader2 className="w-7 h-7 animate-spin" />
                Launching AI Agents...
              </>
            ) : (
              <>
                <Play className="w-7 h-7" />
                Launch Execution
                <ArrowRight className="w-6 h-6" />
              </>
            )}
          </button>
        </div>
      </main>
    </div>
  );
}
