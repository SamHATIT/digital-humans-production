import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Play, Check, ArrowLeft } from 'lucide-react';
import { AGENTS, calculateTotalTime, getAgentAvatar } from '../lib/constants';
import { projects, executions } from '../services/api';

interface Project {
  id: number;
  name: string;
  salesforce_product: string;
  organization_type: string;
  business_requirements: string;
  status: string;
}

export default function ExecutionPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  
  const [project, setProject] = useState<Project | null>(null);
  const [selectedAgents, setSelectedAgents] = useState<string[]>(
    AGENTS.filter(a => a.required).map(a => a.id)
  );
  const [isExecuting, setIsExecuting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (projectId) {
      loadProject();
    }
  }, [projectId]);

  const loadProject = async () => {
    try {
      const data = await projects.get(Number(projectId));
      setProject(data);
    } catch (error) {
      console.error('Error loading project:', error);
      alert('Failed to load project');
      navigate('/projects');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleAgent = (agentId: string) => {
    const agent = AGENTS.find(a => a.id === agentId);
    if (agent?.required) return;

    if (selectedAgents.includes(agentId)) {
      setSelectedAgents(selectedAgents.filter(id => id !== agentId));
    } else {
      setSelectedAgents([...selectedAgents, agentId]);
    }
  };

  const handleStartExecution = async () => {
    if (!projectId) return;

    try {
      setIsExecuting(true);
      
      // Démarrer l'exécution - le backend gérera le statut
      const result = await executions.start(Number(projectId), selectedAgents);
      
      // Rediriger vers la page de monitoring
      navigate(`/execution/${result.execution_id}/monitor`);
      
    } catch (error: any) {
      console.error('Error starting execution:', error);
      alert(`Failed to start execution: ${error.message}`);
      setIsExecuting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin h-12 w-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">Loading project...</p>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="max-w-6xl mx-auto flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-red-600 mb-4">Project not found</p>
          <button onClick={() => navigate('/projects')} className="text-blue-600 hover:underline">
            Back to Projects
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <button
        onClick={() => navigate('/projects')}
        className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft size={20} />
        Back to Projects
      </button>

      <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-6 rounded-lg mb-8">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold mb-2">{project.name}</h1>
            <p className="text-blue-100">
              {project.salesforce_product} • {project.organization_type}
            </p>
          </div>
          <div className="px-4 py-2 rounded-lg bg-blue-700">
            <span className="text-sm font-medium uppercase">{project.status}</span>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
        <h2 className="text-xl font-semibold mb-2">Select Agents to Execute</h2>
        <p className="text-gray-600 mb-6">Choose which AI agents will work on your project</p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {AGENTS.map(agent => (
            <AgentCard
              key={agent.id}
              agent={agent}
              selected={selectedAgents.includes(agent.id)}
              onToggle={() => toggleAgent(agent.id)}
              disabled={isExecuting}
            />
          ))}
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-gray-200">
          <div className="flex gap-2">
            <button
              onClick={() => setSelectedAgents(AGENTS.map(a => a.id))}
              disabled={isExecuting}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Select All
            </button>
            <button
              onClick={() => setSelectedAgents(AGENTS.filter(a => a.required).map(a => a.id))}
              disabled={isExecuting}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Clear Selection
            </button>
          </div>
          <span className="text-sm text-gray-600">
            {selectedAgents.length} agent(s) selected
          </span>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-lg mb-1">Ready to Execute</h3>
            <p className="text-sm text-gray-600">
              {selectedAgents.length} agent(s) selected •
              Estimated time: {calculateTotalTime(selectedAgents)} minutes
            </p>
          </div>

          <button
            onClick={handleStartExecution}
            disabled={selectedAgents.length === 0 || isExecuting}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
          >
            {isExecuting ? (
              <>
                <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full" />
                Executing...
              </>
            ) : (
              <>
                <Play size={20} />
                Start Execution
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

interface AgentCardProps {
  agent: typeof AGENTS[0];
  selected: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

function AgentCard({ agent, selected, onToggle, disabled = false }: AgentCardProps) {
  const [imageError, setImageError] = useState(false);
  
  return (
    <div
      onClick={agent.required || disabled ? undefined : onToggle}
      className={`
        border-3 rounded-xl p-4 transition-all duration-300
        ${selected
          ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-blue-100 shadow-lg transform scale-105'
          : 'border-gray-200 hover:border-blue-300 hover:shadow-md'
        }
        ${agent.required || disabled ? 'opacity-75 cursor-not-allowed' : 'cursor-pointer hover:-translate-y-1'}
      `}
    >
      <div className="flex items-center gap-3 mb-3">
        <div className="relative w-16 h-16 flex-shrink-0">
          {!imageError ? (
            <img 
              src={getAgentAvatar(agent.id, 'small')}
              alt={agent.name}
              className="w-full h-full rounded-full object-cover border-2 border-gray-200"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="w-full h-full rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-bold text-xl">
              {agent.name[0]}
            </div>
          )}
        </div>
        <div>
          <h3 className="font-semibold text-gray-900 text-sm">{agent.name}</h3>
        </div>
      </div>

      <p className="text-xs text-gray-700 mb-3 line-clamp-2">{agent.description}</p>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${
            selected ? 'bg-blue-600 border-blue-600 scale-110' : 'border-gray-300'
          }`}>
            {selected && <Check className="text-white" size={14} />}
          </div>
          <span className="text-xs font-medium text-gray-700">
            {agent.required ? 'Required' : selected ? 'Selected' : 'Select'}
          </span>
        </div>
        <span className="text-xs text-gray-500">~{agent.estimatedTime}min</span>
      </div>
    </div>
  );
}
