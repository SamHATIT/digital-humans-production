import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Play, Loader2, CheckCircle, Users, FileText, ArrowRight } from 'lucide-react';
import { projects, executions } from '../services/api';
import Navbar from '../components/Navbar';
import Avatar from '../components/ui/Avatar';
import { AGENTS, MANDATORY_AGENTS } from '../constants';

interface Project {
  id: number;
  name: string;
  description?: string;
  status: string;
  selected_agents?: string[];
}

export default function ExecutionPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [selectedAgents, setSelectedAgents] = useState<string[]>(MANDATORY_AGENTS);
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchProject = async () => {
      try {
        const data = await projects.get(Number(projectId));
        setProject(data);
        if (data.selected_agents && data.selected_agents.length > 0) {
          setSelectedAgents(data.selected_agents);
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

  const toggleAgent = (agentId: string) => {
    if (MANDATORY_AGENTS.includes(agentId)) return;

    setSelectedAgents((prev) =>
      prev.includes(agentId) ? prev.filter((a) => a !== agentId) : [...prev, agentId]
    );
  };

  const handleStartExecution = async () => {
    if (!project) return;

    setIsStarting(true);
    setError('');

    try {
      const result = await executions.start(project.id, selectedAgents);
      navigate(`/execution/${result.execution_id}/monitor`);
    } catch (err: any) {
      console.error('Failed to start execution:', err);
      setError(err.message || 'Failed to start execution');
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

      <main className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-3xl font-extrabold text-white">{project.name}</h1>
          {project.description && (
            <p className="mt-2 text-slate-400">{project.description}</p>
          )}
        </div>

        {error && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400">
            {error}
          </div>
        )}

        {/* Agent Selection */}
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-2xl p-6 mb-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
              <Users className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Select Your AI Team</h2>
              <p className="text-sm text-slate-400">Sophie & Olivia are always included</p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {AGENTS.map((agent) => {
              const isSelected = selectedAgents.includes(agent.id);
              const isMandatory = MANDATORY_AGENTS.includes(agent.id);

              return (
                <button
                  key={agent.id}
                  onClick={() => toggleAgent(agent.id)}
                  disabled={isMandatory}
                  className={`p-4 rounded-xl border transition-all text-center ${
                    isSelected
                      ? 'bg-cyan-500/20 border-cyan-500/50 shadow-lg shadow-cyan-500/10'
                      : 'bg-slate-800/50 border-slate-600 hover:border-slate-500'
                  } ${isMandatory ? 'cursor-not-allowed opacity-90' : 'cursor-pointer'}`}
                >
                  <div className="flex justify-center mb-3">
                    <Avatar
                      src={agent.avatar}
                      alt={agent.name}
                      size="lg"
                      isActive={isSelected}
                    />
                  </div>
                  <p className="font-medium text-white text-sm">{agent.name}</p>
                  <p className="text-xs text-slate-400 mt-1">{agent.role}</p>
                  {isMandatory && (
                    <span className="inline-block mt-2 px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded-full">
                      Required
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Launch Button */}
        <div className="flex justify-center">
          <button
            onClick={handleStartExecution}
            disabled={isStarting || selectedAgents.length === 0}
            className="inline-flex items-center gap-3 px-10 py-4 bg-gradient-to-r from-cyan-500 to-purple-600 text-white text-lg font-medium rounded-xl hover:from-cyan-600 hover:to-purple-700 transition-all shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isStarting ? (
              <>
                <Loader2 className="w-6 h-6 animate-spin" />
                Launching Agents...
              </>
            ) : (
              <>
                <Play className="w-6 h-6" />
                Launch Execution
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>
        </div>
      </main>
    </div>
  );
}
