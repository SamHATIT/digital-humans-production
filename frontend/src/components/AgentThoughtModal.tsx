import React from 'react';
import { X, Brain, FileCode, MessageSquare, Loader2 } from 'lucide-react';
import Avatar from './ui/Avatar';

interface Agent {
  id: string;
  name: string;
  role: string;
  description: string;
  avatar: string;
  isMandatory?: boolean;
}

interface AgentThoughtModalProps {
  agent: Agent;
  isOpen: boolean;
  onClose: () => void;
  currentTask?: string;
  outputSummary?: string;
  status?: string;
}

const AgentThoughtModal: React.FC<AgentThoughtModalProps> = ({ 
  agent, 
  isOpen, 
  onClose, 
  currentTask,
  outputSummary,
  status 
}) => {
  if (!isOpen) return null;

  // Get status-specific info
  const isRunning = status === 'running' || status === 'in_progress';
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';

  // Get agent-specific metadata
  const getAgentMetadata = () => {
    const metadata: Record<string, { expertise: string[], tools: string[] }> = {
      pm: {
        expertise: ['Project coordination', 'Timeline management', 'Risk assessment'],
        tools: ['Gantt charts', 'Resource allocation', 'Progress tracking'],
      },
      ba: {
        expertise: ['Business requirements', 'Use cases', 'Process analysis'],
        tools: ['User stories', 'Acceptance criteria', 'Process flows'],
      },
      architect: {
        expertise: ['Solution design', 'Data modeling', 'Integration patterns'],
        tools: ['ERD diagrams', 'Sequence diagrams', 'API specs'],
      },
      apex: {
        expertise: ['Apex development', 'Triggers', 'Batch processing'],
        tools: ['Apex classes', 'Test classes', 'Governor limits'],
      },
      lwc: {
        expertise: ['Lightning Web Components', 'UI/UX', 'Frontend'],
        tools: ['HTML templates', 'JavaScript', 'CSS'],
      },
      admin: {
        expertise: ['Salesforce configuration', 'Flows', 'Permission sets'],
        tools: ['Declarative tools', 'Validation rules', 'Page layouts'],
      },
      qa: {
        expertise: ['Test strategy', 'Quality assurance', 'Test execution'],
        tools: ['Test cases', 'Apex tests', 'UAT plans'],
      },
      devops: {
        expertise: ['CI/CD', 'Deployment', 'Release management'],
        tools: ['SFDX', 'Git', 'Package management'],
      },
      data: {
        expertise: ['Data migration', 'ETL', 'Data quality'],
        tools: ['Data mapping', 'Migration scripts', 'Validation reports'],
      },
      trainer: {
        expertise: ['User training', 'Documentation', 'Change management'],
        tools: ['Training materials', 'User guides', 'Videos'],
      },
    };
    return metadata[agent.id] || { expertise: ['AI-powered analysis'], tools: ['Intelligent processing'] };
  };

  const metadata = getAgentMetadata();

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-slate-800 border border-slate-600 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-fade-in">
        {/* Header */}
        <div className="bg-slate-900/50 p-6 border-b border-slate-700 flex items-center gap-4">
          <Avatar src={agent.avatar} alt={agent.name} size="lg" isActive={isRunning} />
          <div className="flex-1">
            <h3 className="text-xl font-bold text-white">{agent.name}</h3>
            <p className="text-cyan-400 text-sm uppercase tracking-wider">{agent.role}</p>
            {/* Status badge */}
            <div className="mt-1">
              {isRunning && (
                <span className="inline-flex items-center gap-1 text-cyan-400 text-xs">
                  <Loader2 className="w-3 h-3 animate-spin" /> Working...
                </span>
              )}
              {isCompleted && (
                <span className="text-green-400 text-xs">✓ Completed</span>
              )}
              {isFailed && (
                <span className="text-red-400 text-xs">✗ Failed</span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 max-h-[60vh] overflow-y-auto">
          {/* Current Task - Real data */}
          <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-cyan-400 mb-2">
              <Brain className="w-4 h-4" />
              <span className="text-sm font-medium uppercase tracking-wider">Current Activity</span>
            </div>
            <p className="text-white">
              {currentTask || outputSummary || 'Waiting for task assignment...'}
            </p>
          </div>

          {/* Output Summary - if different from currentTask */}
          {outputSummary && outputSummary !== currentTask && (
            <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700">
              <div className="flex items-center gap-2 text-green-400 mb-2">
                <MessageSquare className="w-4 h-4" />
                <span className="text-sm font-medium uppercase tracking-wider">Output Summary</span>
              </div>
              <p className="text-slate-300 text-sm whitespace-pre-wrap">
                {outputSummary.length > 500 ? outputSummary.substring(0, 500) + '...' : outputSummary}
              </p>
            </div>
          )}

          {/* Agent Expertise */}
          <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-purple-400 mb-2">
              <FileCode className="w-4 h-4" />
              <span className="text-sm font-medium uppercase tracking-wider">Expertise</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {metadata.expertise.map((item, i) => (
                <span
                  key={i}
                  className="px-3 py-1 bg-slate-800 border border-slate-600 rounded-full text-sm text-slate-300"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          {/* Agent Tools */}
          <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-amber-400 mb-2">
              <FileCode className="w-4 h-4" />
              <span className="text-sm font-medium uppercase tracking-wider">Tools & Outputs</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {metadata.tools.map((tool, i) => (
                <span
                  key={i}
                  className="px-3 py-1 bg-slate-800 border border-amber-600/30 rounded-full text-sm text-amber-300"
                >
                  {tool}
                </span>
              ))}
            </div>
          </div>

          {/* Agent Description */}
          <div className="text-slate-400 text-sm border-t border-slate-700 pt-4">
            {agent.description}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentThoughtModal;
