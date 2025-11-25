import React from 'react';
import { X, Brain, FileCode, MessageSquare } from 'lucide-react';
import Avatar from './ui/Avatar';

// Define Agent type inline - TypeScript types get erased at runtime
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
}

const AgentThoughtModal: React.FC<AgentThoughtModalProps> = ({ agent, isOpen, onClose, currentTask }) => {
  if (!isOpen) return null;

  // Generate contextual mock data based on role
  const getMockContext = () => {
    switch (agent.role) {
      case 'Project Manager':
        return {
          task: currentTask || 'Coordinating agent workflows',
          files: ['project_plan.json', 'timeline.xml', 'risks.csv'],
          thoughts: [
            'Analyzing project velocity metrics...',
            'QA phase might need additional buffer.',
            'Diego is ahead of schedule on Apex triggers.',
          ],
        };
      case 'Apex Developer':
        return {
          task: currentTask || 'Writing AccountTriggerHandler',
          files: ['AccountTrigger.trigger', 'AccountService.cls', 'AccountTest.cls'],
          thoughts: [
            'Need to bulkify this SOQL query.',
            'Checking governor limits for batch size.',
            'Adding error handling for null cases.',
          ],
        };
      case 'Business Analyst':
        return {
          task: currentTask || 'Mapping user stories to requirements',
          files: ['Requirements.docx', 'UserStories.csv', 'ProcessFlow.bpmn'],
          thoughts: [
            'Client requirement needs clarification.',
            'Identified 3 edge cases in order flow.',
            'Scheduling stakeholder review meeting.',
          ],
        };
      case 'Solution Architect':
        return {
          task: currentTask || 'Designing data model',
          files: ['ERD.mermaid', 'DataModel.json', 'IntegrationSpec.yaml'],
          thoughts: [
            'Evaluating junction object vs. lookup.',
            'Need to consider sharing rules impact.',
            'API integration requires OAuth 2.0.',
          ],
        };
      default:
        return {
          task: currentTask || 'Processing assigned tasks...',
          files: ['task_log.json'],
          thoughts: ['Analyzing requirements...', 'Generating optimal solution...'],
        };
    }
  };

  const context = getMockContext();

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-slate-800 border border-slate-600 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden animate-fade-in">
        {/* Header */}
        <div className="bg-slate-900/50 p-6 border-b border-slate-700 flex items-center gap-4">
          <Avatar src={agent.avatar} alt={agent.name} size="lg" isActive={true} />
          <div className="flex-1">
            <h3 className="text-xl font-bold text-white">{agent.name}</h3>
            <p className="text-cyan-400 text-sm uppercase tracking-wider">{agent.role}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Current Task */}
          <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-cyan-400 mb-2">
              <Brain className="w-4 h-4" />
              <span className="text-sm font-medium uppercase tracking-wider">Current Task</span>
            </div>
            <p className="text-white">{context.task}</p>
          </div>

          {/* Active Files */}
          <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-purple-400 mb-2">
              <FileCode className="w-4 h-4" />
              <span className="text-sm font-medium uppercase tracking-wider">Active Files</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {context.files.map((file, i) => (
                <span
                  key={i}
                  className="px-3 py-1 bg-slate-800 border border-slate-600 rounded-full text-sm text-slate-300"
                >
                  {file}
                </span>
              ))}
            </div>
          </div>

          {/* Thought Chain */}
          <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 text-green-400 mb-2">
              <MessageSquare className="w-4 h-4" />
              <span className="text-sm font-medium uppercase tracking-wider">Thought Chain</span>
            </div>
            <ul className="space-y-2">
              {context.thoughts.map((thought, i) => (
                <li key={i} className="flex items-start gap-2 text-slate-300 text-sm">
                  <span className="text-cyan-500 mt-1">→</span>
                  <span>{thought}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentThoughtModal;
