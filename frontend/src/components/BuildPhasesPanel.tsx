/**
 * BuildPhasesPanel - BUILD v2 Phase Monitoring Component
 * Displays the 6 phases of BUILD v2 with their status and progress
 */
import { 
  CheckCircle, AlertCircle, Clock, Play, Loader2,
  Database, Code, Wrench, Settings, Shield, FileSpreadsheet,
  ChevronDown, ChevronUp, GitMerge
} from 'lucide-react';
import { useState } from 'react';

// Phase configuration
const PHASE_CONFIG = [
  { phase: 1, name: 'Data Model', agent: 'raj', icon: Database, description: 'Objects, Fields, Record Types' },
  { phase: 2, name: 'Business Logic', agent: 'diego', icon: Code, description: 'Apex Classes, Triggers, Tests' },
  { phase: 3, name: 'UI Components', agent: 'zara', icon: Wrench, description: 'LWC, FlexiPages, Tabs' },
  { phase: 4, name: 'Automation', agent: 'raj', icon: Settings, description: 'Flows, Validation Rules' },
  { phase: 5, name: 'Security', agent: 'raj', icon: Shield, description: 'Permission Sets, Profiles' },
  { phase: 6, name: 'Data Migration', agent: 'aisha', icon: FileSpreadsheet, description: 'Import Scripts, Mappings' },
];

// Status configuration
const STATUS_CONFIG: Record<string, { color: string; bgColor: string; icon: typeof CheckCircle }> = {
  pending: { color: 'text-bone-4', bgColor: 'bg-ink-3', icon: Clock },
  generating: { color: 'text-indigo', bgColor: 'bg-indigo', icon: Loader2 },
  aggregating: { color: 'text-brass', bgColor: 'bg-brass', icon: Loader2 },
  reviewing: { color: 'text-plum', bgColor: 'bg-plum', icon: Loader2 },
  pr_created: { color: 'text-ochre', bgColor: 'bg-warning', icon: GitMerge },
  deploying: { color: 'text-ochre', bgColor: 'bg-ochre', icon: Play },
  retrieving: { color: 'text-sage', bgColor: 'bg-sage', icon: Loader2 },
  completed: { color: 'text-sage', bgColor: 'bg-sage', icon: CheckCircle },
  failed: { color: 'text-error', bgColor: 'bg-error', icon: AlertCircle },
  retry: { color: 'text-warning', bgColor: 'bg-warning', icon: AlertCircle },
};

export interface PhaseExecution {
  phase_number: number;
  phase_name: string;
  status: string;
  agent_id: string;
  total_batches: number;
  completed_batches: number;
  elena_verdict?: string;
  elena_feedback?: string;
  elena_review_count: number;
  deploy_method?: string;
  branch_name?: string;
  pr_url?: string;
  pr_number?: number;
  merge_sha?: string;
  started_at?: string;
  completed_at?: string;
  last_error?: string;
  attempt_count: number;
}

interface BuildPhasesPanelProps {
  phases: PhaseExecution[];
  currentPhase?: number;
}

export default function BuildPhasesPanel({ phases, currentPhase }: BuildPhasesPanelProps) {
  const [expandedPhase, setExpandedPhase] = useState<number | null>(currentPhase || null);

  const getPhaseData = (phaseNum: number): PhaseExecution | undefined => {
    return phases.find(p => p.phase_number === phaseNum);
  };

  const formatDuration = (start?: string, end?: string): string => {
    if (!start) return '-';
    const startDate = new Date(start);
    const endDate = end ? new Date(end) : new Date();
    const seconds = Math.floor((endDate.getTime() - startDate.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  return (
    <div className="bg-ink-2 rounded-xl p-6 shadow-lg border border-bone/10">
      <h3 className="text-lg font-semibold text-bone mb-4 flex items-center gap-2">
        <Play className="w-5 h-5 text-brass" />
        BUILD Phases (v2)
      </h3>

      <div className="space-y-3">
        {PHASE_CONFIG.map((config) => {
          const phaseData = getPhaseData(config.phase);
          const status = phaseData?.status || 'pending';
          const statusConfig = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
          const StatusIcon = statusConfig.icon;
          const PhaseIcon = config.icon;
          const isExpanded = expandedPhase === config.phase;
          const isCurrent = currentPhase === config.phase;

          return (
            <div 
              key={config.phase}
              className={`
                rounded-lg border transition-all
                ${isCurrent ? 'border-brass bg-ink-3/60' : 'border-bone/15 bg-ink-3'}
                ${status === 'completed' ? 'opacity-80' : ''}
              `}
            >
              {/* Header */}
              <div 
                className="p-4 flex items-center justify-between cursor-pointer"
                onClick={() => setExpandedPhase(isExpanded ? null : config.phase)}
              >
                <div className="flex items-center gap-3">
                  {/* Status Icon */}
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${statusConfig.bgColor}`}>
                    <StatusIcon className={`w-4 h-4 text-bone ${status.includes('ing') ? 'animate-spin' : ''}`} />
                  </div>
                  
                  {/* Phase Info */}
                  <div>
                    <div className="flex items-center gap-2">
                      <PhaseIcon className="w-4 h-4 text-bone-4" />
                      <span className="font-medium text-bone">
                        Phase {config.phase}: {config.name}
                      </span>
                      {isCurrent && (
                        <span className="text-xs px-2 py-0.5 bg-brass/20 text-brass-2 rounded-full">
                          Current
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-bone-4 mt-0.5">
                      {config.description} • Agent: {config.agent}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {/* Progress */}
                  {phaseData && phaseData.total_batches > 0 && (
                    <div className="text-xs text-bone-4">
                      {phaseData.completed_batches}/{phaseData.total_batches} batches
                    </div>
                  )}
                  
                  {/* Duration */}
                  {phaseData?.started_at && (
                    <div className="text-xs text-bone-4">
                      {formatDuration(phaseData.started_at, phaseData.completed_at)}
                    </div>
                  )}
                  
                  {/* Status Badge */}
                  <span className={`text-xs px-2 py-1 rounded-full ${statusConfig.bgColor} text-bone`}>
                    {status.replace('_', ' ')}
                  </span>
                  
                  {/* Expand Arrow */}
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-bone-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-bone-4" />
                  )}
                </div>
              </div>

              {/* Expanded Details */}
              {isExpanded && phaseData && (
                <div className="px-4 pb-4 pt-2 border-t border-bone/15 text-sm">
                  <div className="grid grid-cols-2 gap-4">
                    {/* Elena Review */}
                    {phaseData.elena_verdict && (
                      <div>
                        <div className="text-bone-4 text-xs mb-1">Elena Review</div>
                        <div className={`
                          ${phaseData.elena_verdict === 'PASS' ? 'text-sage' : 'text-error'}
                        `}>
                          {phaseData.elena_verdict} 
                          {phaseData.elena_review_count > 1 && ` (${phaseData.elena_review_count} reviews)`}
                        </div>
                        {phaseData.elena_feedback && (
                          <div className="text-xs text-bone-4 mt-1 line-clamp-2">
                            {phaseData.elena_feedback}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Deploy Info */}
                    {phaseData.deploy_method && (
                      <div>
                        <div className="text-bone-4 text-xs mb-1">Deploy Method</div>
                        <div className="text-bone">{phaseData.deploy_method}</div>
                      </div>
                    )}

                    {/* Git Info */}
                    {phaseData.pr_url && (
                      <div>
                        <div className="text-bone-4 text-xs mb-1">Pull Request</div>
                        <a 
                          href={phaseData.pr_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-brass hover:underline"
                        >
                          PR #{phaseData.pr_number}
                        </a>
                      </div>
                    )}

                    {phaseData.merge_sha && (
                      <div>
                        <div className="text-bone-4 text-xs mb-1">Merge SHA</div>
                        <code className="text-xs text-bone-3 bg-ink-3 px-2 py-0.5 rounded">
                          {phaseData.merge_sha.substring(0, 8)}
                        </code>
                      </div>
                    )}

                    {/* Error */}
                    {phaseData.last_error && (
                      <div className="col-span-2">
                        <div className="text-error text-xs mb-1">Last Error</div>
                        <div className="text-xs text-error bg-error/15 p-2 rounded">
                          {phaseData.last_error}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary */}
      <div className="mt-4 pt-4 border-t border-bone/10 flex justify-between text-sm">
        <div className="text-bone-4">
          Completed: {phases.filter(p => p.status === 'completed').length}/6 phases
        </div>
        <div className="text-bone-4">
          Current: Phase {currentPhase || '-'}
        </div>
      </div>
    </div>
  );
}
