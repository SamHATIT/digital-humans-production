import React, { useState, useEffect } from 'react';
import { AGENTS, MANDATORY_AGENTS } from '../constants';
import Avatar from './ui/Avatar';
import { GripVertical, Lock, X } from 'lucide-react';

// Define types inline - TypeScript types get erased at runtime
type Phase = 'Discovery' | 'Design' | 'Build' | 'QA' | 'Release';

interface WorkflowEditorProps {
  onSelectionChange: (selectedAgents: string[]) => void;
}

const PHASES: Phase[] = ['Discovery', 'Design', 'Build', 'QA', 'Release'];

const PHASE_COLORS: Record<Phase, string> = {
  Discovery: 'from-blue-500/20 to-cyan-500/20 border-cyan-500/30',
  Design: 'from-purple-500/20 to-pink-500/20 border-purple-500/30',
  Build: 'from-orange-500/20 to-yellow-500/20 border-orange-500/30',
  QA: 'from-green-500/20 to-emerald-500/20 border-green-500/30',
  Release: 'from-red-500/20 to-rose-500/20 border-red-500/30',
};

const WorkflowEditor: React.FC<WorkflowEditorProps> = ({ onSelectionChange }) => {
  // Use backend agent IDs: pm, ba, architect, apex, lwc, admin, qa, devops, data, trainer
  const [assignments, setAssignments] = useState<Record<Phase, string[]>>({
    Discovery: ['pm', 'ba'],
    Design: ['architect'],
    Build: ['apex', 'lwc', 'admin', 'data'],
    QA: ['qa'],
    Release: ['devops', 'trainer'],
  });

  const [draggedAgent, setDraggedAgent] = useState<string | null>(null);

  // Notify parent of selection changes
  useEffect(() => {
    const allAgents = Object.values(assignments).flat();
    const uniqueAgents = Array.from(new Set(allAgents));
    onSelectionChange(uniqueAgents);
  }, [assignments, onSelectionChange]);

  const handleDragStart = (e: React.DragEvent, agentId: string) => {
    if (MANDATORY_AGENTS.includes(agentId)) return;
    setDraggedAgent(agentId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: React.DragEvent, targetPhase: Phase) => {
    e.preventDefault();
    if (!draggedAgent) return;

    setAssignments((prev) => {
      // Remove from all phases first
      const newAssignments = { ...prev };
      Object.keys(newAssignments).forEach((phase) => {
        newAssignments[phase as Phase] = newAssignments[phase as Phase].filter((a) => a !== draggedAgent);
      });

      // Add to target phase
      if (!newAssignments[targetPhase].includes(draggedAgent)) {
        newAssignments[targetPhase] = [...newAssignments[targetPhase], draggedAgent];
      }

      return newAssignments;
    });
    setDraggedAgent(null);
  };

  const removeFromPhase = (phase: Phase, agentId: string) => {
    if (MANDATORY_AGENTS.includes(agentId)) return;
    setAssignments((prev) => ({
      ...prev,
      [phase]: prev[phase].filter((a) => a !== agentId),
    }));
  };

  const getUnassignedAgents = () => {
    const assigned = new Set(Object.values(assignments).flat());
    return AGENTS.filter((a) => !assigned.has(a.id));
  };

  return (
    <div className="space-y-6">
      {/* Phases */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {PHASES.map((phase) => (
          <div
            key={phase}
            className={`bg-gradient-to-br ${PHASE_COLORS[phase]} border rounded-xl p-4 min-h-[200px] transition-all ${
              draggedAgent ? 'ring-2 ring-cyan-500/50' : ''
            }`}
            onDragOver={handleDragOver}
            onDrop={(e) => handleDrop(e, phase)}
          >
            <h3 className="text-sm font-bold text-white mb-3 uppercase tracking-wider">{phase}</h3>
            <div className="space-y-2">
              {assignments[phase].map((agentId) => {
                const agent = AGENTS.find((a) => a.id === agentId);
                if (!agent) return null;
                const isMandatory = MANDATORY_AGENTS.includes(agentId);

                return (
                  <div
                    key={agentId}
                    draggable={!isMandatory}
                    onDragStart={(e) => handleDragStart(e, agentId)}
                    className={`flex items-center gap-2 p-2 bg-slate-800/80 rounded-lg border border-slate-600 ${
                      isMandatory ? 'opacity-90 cursor-not-allowed' : 'cursor-grab active:cursor-grabbing hover:border-cyan-500/50'
                    }`}
                  >
                    {!isMandatory && <GripVertical className="w-3 h-3 text-slate-500" />}
                    {isMandatory && <Lock className="w-3 h-3 text-yellow-500" />}
                    <Avatar src={agent.avatar} alt={agent.name} size="sm" />
                    <span className="text-xs text-white flex-1 truncate">{agent.name}</span>
                    {!isMandatory && (
                      <button
                        onClick={() => removeFromPhase(phase, agentId)}
                        className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-red-400"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Unassigned Agents Pool */}
      {getUnassignedAgents().length > 0 && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <h3 className="text-sm font-medium text-slate-400 mb-3">Available Agents (drag to assign)</h3>
          <div className="flex flex-wrap gap-3">
            {getUnassignedAgents().map((agent) => (
              <div
                key={agent.id}
                draggable
                onDragStart={(e) => handleDragStart(e, agent.id)}
                className="flex items-center gap-2 px-3 py-2 bg-slate-700/50 rounded-lg border border-slate-600 cursor-grab active:cursor-grabbing hover:border-cyan-500/50 transition-all"
              >
                <GripVertical className="w-3 h-3 text-slate-500" />
                <Avatar src={agent.avatar} alt={agent.name} size="sm" />
                <div>
                  <span className="text-sm text-white">{agent.name}</span>
                  <span className="text-xs text-slate-400 block">{agent.role}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkflowEditor;
