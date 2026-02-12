import { useState, useEffect } from 'react';
import {
  Database,
  GitBranch,
  Layout,
  Shield,
  ListTree,
  Loader2,
  CheckCircle,
  RotateCcw,
  MessageSquare,
} from 'lucide-react';
import { api } from '../services/api';
import { executions } from '../services/api';
import MermaidRenderer from './MermaidRenderer';
import GanttChart from './GanttChart';

interface ArchitectureReviewPanelProps {
  executionId: number;
  onApprove: () => void;
  onRevise: () => void;
  isActioning?: boolean;
  coverageScore?: number | null;
  criticalGaps?: Array<{ gap: string; severity: string }>;
  uncoveredUseCases?: string[];
  revisionCount?: number;
}

interface ArchitectureData {
  dataModel?: string;
  flows?: string;
  lwcComponents?: string;
  security?: string;
  wbs?: any;
}

const TABS = [
  { id: 'data_model', label: 'Data Model', icon: Database },
  { id: 'flows', label: 'Flows', icon: GitBranch },
  { id: 'lwc', label: 'LWC Components', icon: Layout },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'wbs', label: 'WBS', icon: ListTree },
] as const;

type TabId = (typeof TABS)[number]['id'];

function extractSection(content: string, sectionName: string): string {
  // Try to find section by heading
  const patterns = [
    new RegExp(`## ${sectionName}[\\s\\S]*?(?=\\n## |$)`, 'i'),
    new RegExp(`### ${sectionName}[\\s\\S]*?(?=\\n### |\\n## |$)`, 'i'),
    new RegExp(`# ${sectionName}[\\s\\S]*?(?=\\n# |$)`, 'i'),
  ];

  for (const pattern of patterns) {
    const match = content.match(pattern);
    if (match) return match[0].trim();
  }

  return '';
}

function parseWBSTasks(wbsContent: string): any[] {
  // Try parsing as JSON first
  try {
    const parsed = JSON.parse(wbsContent);
    if (Array.isArray(parsed)) return parsed;
    if (parsed.tasks && Array.isArray(parsed.tasks)) return parsed.tasks;
    if (parsed.phases) {
      const tasks: any[] = [];
      for (const phase of parsed.phases) {
        if (phase.tasks) {
          tasks.push(...phase.tasks);
        } else {
          tasks.push(phase);
        }
      }
      return tasks;
    }
  } catch {
    // Not JSON, try line-based parsing
  }

  // Parse markdown table or list format
  const tasks: any[] = [];
  const lines = wbsContent.split('\n');
  let taskId = 0;

  for (const line of lines) {
    // Match list items: "- Task name (5d)" or "1. Task name"
    const listMatch = line.match(/^\s*[-*\d.]+\s+(.+?)(?:\s*\((\d+[dhw]?)\))?$/);
    if (listMatch) {
      taskId++;
      tasks.push({
        id: `T${taskId}`,
        name: listMatch[1].trim(),
        duration: listMatch[2] || '3d',
      });
    }

    // Match table rows: "| T1 | Task name | 5d | T0 |"
    const tableMatch = line.match(
      /\|\s*(\S+)\s*\|\s*(.+?)\s*\|\s*(\d+[dhw]?)\s*\|\s*(.*?)\s*\|/
    );
    if (tableMatch && !tableMatch[1].includes('-')) {
      tasks.push({
        id: tableMatch[1].trim(),
        name: tableMatch[2].trim(),
        duration: tableMatch[3].trim(),
        dependencies: tableMatch[4].trim() || undefined,
      });
    }
  }

  return tasks;
}

export default function ArchitectureReviewPanel({
  executionId,
  onApprove,
  onRevise,
  isActioning = false,
  coverageScore,
  criticalGaps = [],
  uncoveredUseCases = [],
  revisionCount = 0,
}: ArchitectureReviewPanelProps) {
  const [activeTab, setActiveTab] = useState<TabId>('data_model');
  const [archData, setArchData] = useState<ArchitectureData>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState('');

  useEffect(() => {
    const fetchArchitectureDeliverables = async () => {
      setLoading(true);
      try {
        const data = await api.get(
          `/api/deliverables/executions/${executionId}/previews`
        );
        const deliverables = Array.isArray(data) ? data : data?.deliverables || [];

        const archDeliverables = deliverables.filter(
          (d: any) =>
            d.deliverable_type.startsWith('architect_') ||
            d.deliverable_type.includes('solution_design')
        );

        // Load full content for each
        const contents: Record<string, string> = {};
        for (const d of archDeliverables) {
          try {
            const full = await api.get(`/api/deliverables/${d.id}`);
            const content =
              typeof full === 'string'
                ? full
                : full?.content || full?.full_content || JSON.stringify(full, null, 2);
            contents[d.deliverable_type] = content;
          } catch {
            contents[d.deliverable_type] = d.content_preview || '';
          }
        }

        // Extract sections from the solution design
        const solutionDesign = contents['architect_solution_design'] || '';
        const allContent = Object.values(contents).join('\n\n');

        setArchData({
          dataModel:
            extractSection(allContent, 'Data Model') ||
            extractSection(allContent, 'Entity Relationship') ||
            extractSection(allContent, 'Objects') ||
            extractSection(solutionDesign, 'Data Model'),
          flows:
            extractSection(allContent, 'Flows') ||
            extractSection(allContent, 'Process Flow') ||
            extractSection(allContent, 'Business Flow') ||
            extractSection(solutionDesign, 'Flows'),
          lwcComponents:
            extractSection(allContent, 'LWC') ||
            extractSection(allContent, 'Lightning Web Component') ||
            extractSection(allContent, 'UI Component') ||
            extractSection(solutionDesign, 'Component'),
          security:
            extractSection(allContent, 'Security') ||
            extractSection(allContent, 'Permission') ||
            extractSection(allContent, 'Access Control') ||
            extractSection(solutionDesign, 'Security'),
          wbs:
            contents['architect_wbs'] ||
            extractSection(allContent, 'WBS') ||
            extractSection(allContent, 'Work Breakdown') ||
            extractSection(solutionDesign, 'WBS'),
        });
      } catch (err: any) {
        setError(err.message || 'Failed to load architecture data');
      } finally {
        setLoading(false);
      }
    };

    fetchArchitectureDeliverables();
  }, [executionId]);

  const getTabContent = () => {
    switch (activeTab) {
      case 'data_model':
        return archData.dataModel ? (
          <MermaidRenderer content={archData.dataModel} />
        ) : (
          <EmptyTab label="Data Model" />
        );
      case 'flows':
        return archData.flows ? (
          <MermaidRenderer content={archData.flows} />
        ) : (
          <EmptyTab label="Flows" />
        );
      case 'lwc':
        return archData.lwcComponents ? (
          <div className="text-sm text-slate-300 whitespace-pre-wrap">
            <MermaidRenderer content={archData.lwcComponents} />
          </div>
        ) : (
          <EmptyTab label="LWC Components" />
        );
      case 'security':
        return archData.security ? (
          <div className="text-sm text-slate-300 whitespace-pre-wrap">
            <MermaidRenderer content={archData.security} />
          </div>
        ) : (
          <EmptyTab label="Security" />
        );
      case 'wbs': {
        if (!archData.wbs) return <EmptyTab label="WBS" />;
        const tasks = parseWBSTasks(
          typeof archData.wbs === 'string' ? archData.wbs : JSON.stringify(archData.wbs)
        );
        return tasks.length > 0 ? (
          <GanttChart tasks={tasks} title="Work Breakdown Structure" />
        ) : (
          <div className="text-sm text-slate-300 whitespace-pre-wrap">
            <MermaidRenderer content={typeof archData.wbs === 'string' ? archData.wbs : JSON.stringify(archData.wbs, null, 2)} />
          </div>
        );
      }
      default:
        return null;
    }
  };

  return (
    <div className="mb-6 bg-blue-500/10 border border-blue-500/30 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-blue-500/20">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center flex-shrink-0">
            <Shield className="w-6 h-6 text-blue-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-blue-400 mb-1">
              Architecture Review
            </h3>
            <p className="text-slate-300 text-sm">
              Review Marcus&apos;s solution design across all dimensions before proceeding.
            </p>

            {/* Coverage score */}
            {coverageScore != null && (
              <div className="mt-3 flex items-center gap-3">
                <span className="text-slate-400 text-sm">
                  {revisionCount > 0
                    ? `Score after ${revisionCount} revision${revisionCount > 1 ? 's' : ''}:`
                    : 'Coverage Score:'}
                </span>
                <span
                  className={`text-2xl font-bold ${
                    coverageScore >= 85
                      ? 'text-green-400'
                      : coverageScore >= 70
                        ? 'text-orange-400'
                        : 'text-red-400'
                  }`}
                >
                  {Math.round(coverageScore)}%
                </span>
              </div>
            )}

            {/* Critical gaps */}
            {criticalGaps.length > 0 && (
              <div className="mt-3">
                <p className="text-sm text-slate-400 font-medium mb-1">
                  Critical Gaps ({criticalGaps.length}):
                </p>
                <ul className="space-y-1">
                  {criticalGaps.map((gap, i) => (
                    <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                      <span
                        className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${
                          gap.severity === 'high'
                            ? 'bg-red-400'
                            : gap.severity === 'medium'
                              ? 'bg-orange-400'
                              : 'bg-yellow-400'
                        }`}
                      />
                      <span>
                        <span
                          className={`font-medium ${
                            gap.severity === 'high'
                              ? 'text-red-400'
                              : gap.severity === 'medium'
                                ? 'text-orange-400'
                                : 'text-yellow-400'
                          }`}
                        >
                          [{gap.severity}]
                        </span>{' '}
                        {gap.gap}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Uncovered UCs */}
            {uncoveredUseCases.length > 0 && (
              <div className="mt-3">
                <p className="text-sm text-slate-400 font-medium mb-1">
                  Uncovered Use Cases ({uncoveredUseCases.length}):
                </p>
                <ul className="space-y-0.5">
                  {uncoveredUseCases.map((uc, i) => (
                    <li key={i} className="text-sm text-slate-300">
                      &bull; {uc}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-700/50 bg-slate-800/30 overflow-x-auto">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors border-b-2 ${
                isActive
                  ? 'text-blue-400 border-blue-400 bg-blue-500/5'
                  : 'text-slate-400 border-transparent hover:text-white hover:bg-slate-700/30'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div className="p-5 min-h-[200px] max-h-[500px] overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
            <span className="text-slate-400 ml-3">Loading architecture data...</span>
          </div>
        ) : error ? (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
            {error}
          </div>
        ) : (
          getTabContent()
        )}
      </div>

      {/* Feedback area */}
      {showFeedback && (
        <div className="px-5 pb-3">
          <label className="block text-sm text-slate-400 mb-2">
            <MessageSquare className="w-4 h-4 inline mr-1" />
            Revision feedback (optional)
          </label>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Describe what needs to be revised in the architecture..."
            className="w-full h-24 bg-slate-800 border border-slate-600 rounded-lg p-3 text-slate-200 placeholder-slate-500 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none resize-y text-sm"
          />
        </div>
      )}

      {/* Action buttons */}
      <div className="px-5 py-4 border-t border-slate-700/50 flex items-center gap-3">
        <button
          onClick={onApprove}
          disabled={isActioning}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-green-500 to-emerald-600 text-white font-medium rounded-xl hover:from-green-600 hover:to-emerald-700 transition-all shadow-lg shadow-green-500/25 disabled:opacity-50"
        >
          {isActioning ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <CheckCircle className="w-4 h-4" />
          )}
          {isActioning ? 'Processing...' : 'Approve Architecture'}
        </button>
        <button
          onClick={() => {
            if (showFeedback) {
              onRevise();
            } else {
              setShowFeedback(true);
            }
          }}
          disabled={isActioning}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-indigo-700 transition-all shadow-lg shadow-blue-500/25 disabled:opacity-50"
        >
          <RotateCcw className="w-4 h-4" />
          {isActioning ? 'Processing...' : showFeedback ? 'Submit & Revise' : 'Revise Architecture'}
        </button>
        {showFeedback && (
          <button
            onClick={() => {
              setShowFeedback(false);
              setFeedback('');
            }}
            className="text-sm text-slate-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

function EmptyTab({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center py-12 text-slate-500 text-sm">
      No {label} data found in the architecture deliverables.
    </div>
  );
}
