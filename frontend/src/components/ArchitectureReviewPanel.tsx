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
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { api } from '../services/api';
import MermaidRenderer from './MermaidRenderer';
import GanttChart from './GanttChart';

interface ArchitectureReviewPanelProps {
  executionId: number;
  onApprove: () => void;
  onRevise: () => void;
  isActioning?: boolean;
  coverageScore?: number | null;
  criticalGaps?: Array<{ gap?: string; what_is_missing?: string; id?: string; severity: string; [key: string]: any }>;
  uncoveredUseCases?: Array<string | { id?: string; title?: string; [key: string]: any }>;
  revisionCount?: number;
}

// --- JSON types from Marcus ---
interface SFField {
  api_name: string;
  type: string;
  required?: boolean;
  description?: string;
}
interface SFObject {
  api_name: string;
  label?: string;
  purpose?: string;
  sharing_model?: string;
  fields?: SFField[];
  custom_fields?: SFField[];
}
interface Relationship {
  from: string;
  to: string;
  type: string;
  field: string;
  cardinality?: string;
}
interface FlowElement {
  type: string;
  object?: string;
  filter?: string;
  purpose?: string;
  condition?: string;
  [key: string]: any;
}
interface SFFlow {
  api_name: string;
  label?: string;
  type: string;
  trigger?: { object: string; event: string; condition?: string };
  uc_refs?: string[];
  elements?: FlowElement[];
}
interface DataModel {
  standard_objects?: SFObject[];
  custom_objects?: SFObject[];
  relationships?: Relationship[];
}
interface ArchContent {
  data_model?: DataModel;
  automation_design?: { flows?: SFFlow[] };
  security?: any;
  artifact_id?: string;
  title?: string;
}
interface WBSPhase {
  id: string;
  name: string;
  duration_weeks?: number;
  tasks?: WBSTask[];
}
interface WBSTask {
  id: string;
  name: string;
  effort_days?: number;
  dependencies?: string[];
  assigned_agent?: string;
  priority?: string;
  gap_refs?: string[];
}

// --- Mermaid generators ---

function generateERDMermaid(dm: DataModel): string {
  const lines: string[] = ['erDiagram'];
  const allObjects = [...(dm.custom_objects || []), ...(dm.standard_objects || []).slice(0, 8)];
  const objectNames = new Set(allObjects.map(o => o.api_name));

  for (const obj of allObjects) {
    const safeName = obj.api_name.replace(/__c$/, '').replace(/_/g, '-');
    const fields = obj.fields || obj.custom_fields || [];
    if (fields.length > 0) {
      lines.push(`  ${safeName} {`);
      for (const f of fields.slice(0, 8)) {
        const fType = (f.type || 'Text').split('(')[0].replace(/[^a-zA-Z]/g, '');
        const fName = f.api_name.replace(/__c$/, '').replace(/_/g, '-');
        lines.push(`    ${fType} ${fName}`);
      }
      if (fields.length > 8) lines.push(`    string plus-${fields.length - 8}-more`);
      lines.push('  }');
    }
  }

  for (const rel of (dm.relationships || []).slice(0, 40)) {
    const from = rel.from.replace(/__c$/, '').replace(/_/g, '-');
    const to = rel.to.replace(/__c$/, '').replace(/_/g, '-');
    const card = rel.type === 'MasterDetail' ? '||--o{' : '}o--o|';
    const label = rel.field?.replace(/__c$/, '') || rel.type;
    lines.push(`  ${to} ${card} ${from} : "${label}"`);
  }

  return lines.join('\n');
}

function generateFlowMermaid(flow: SFFlow): string {
  const lines: string[] = ['flowchart TD'];
  const elements = flow.elements || [];
  if (elements.length === 0) return '';

  const safeId = (i: number) => `n${i}`;

  for (let i = 0; i < Math.min(elements.length, 15); i++) {
    const el = elements[i];
    const label = (el.purpose || el.type || 'Step').replace(/"/g, "'").substring(0, 60);
    const shape = el.type === 'Decision'
      ? `${safeId(i)}{{"${label}"}}`
      : el.type?.includes('Get')
        ? `${safeId(i)}[("${label}")]`
        : `${safeId(i)}["${label}"]`;
    lines.push(`  ${shape}`);
    if (i > 0) lines.push(`  ${safeId(i - 1)} --> ${safeId(i)}`);
  }

  // Style
  lines.push('  classDef decision fill:#f59e0b,stroke:#d97706,color:#000');
  for (let i = 0; i < elements.length; i++) {
    if (elements[i].type === 'Decision') lines.push(`  class ${safeId(i)} decision`);
  }

  return lines.join('\n');
}

function wbsToGanttTasks(phases: WBSPhase[]): { id: string; name: string; duration: string; dependencies: string }[] {
  const tasks: { id: string; name: string; duration: string; dependencies: string }[] = [];
  for (const phase of phases) {
    for (const task of phase.tasks || []) {
      tasks.push({
        id: task.id,
        name: task.name?.substring(0, 50) || task.id,
        duration: `${task.effort_days || 3}d`,
        dependencies: (task.dependencies || []).join(', '),
      });
    }
  }
  return tasks;
}

// --- Tab types ---
const TABS = [
  { id: 'data_model', label: 'Data Model', icon: Database },
  { id: 'flows', label: 'Flows', icon: GitBranch },
  { id: 'lwc', label: 'Components', icon: Layout },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'wbs', label: 'WBS', icon: ListTree },
] as const;
type TabId = (typeof TABS)[number]['id'];

// --- Main component ---
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
  const [archContent, setArchContent] = useState<ArchContent | null>(null);
  const [wbsPhases, setWbsPhases] = useState<WBSPhase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [expandedFlows, setExpandedFlows] = useState<Set<number>>(new Set([0]));

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const data = await api.get(`/api/deliverables/executions/${executionId}/previews`);
        const deliverables = Array.isArray(data) ? data : data?.deliverables || [];

        // Fetch full content for architecture deliverables
        for (const d of deliverables) {
          try {
            const full = await api.get(`/api/deliverables/${d.id}/full`);
            const raw = full?.content || full;
            const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
            const inner = parsed?.content || parsed;

            if (d.deliverable_type === 'architect_solution_design') {
              setArchContent(typeof inner === 'object' ? inner : null);
            }
            if (d.deliverable_type === 'architect_wbs') {
              const wbs = typeof inner === 'object' ? inner : {};
              setWbsPhases(wbs.phases || []);
            }
          } catch {
            // skip unparseable deliverables
          }
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load architecture data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [executionId]);

  const toggleFlow = (i: number) => {
    setExpandedFlows(prev => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  };

  const getTabContent = () => {
    if (!archContent && activeTab !== 'wbs') {
      return <EmptyTab label="Architecture" hint="No solution design data found." />;
    }

    switch (activeTab) {
      case 'data_model': {
        const dm = archContent?.data_model;
        if (!dm) return <EmptyTab label="Data Model" />;
        const customObjs = dm.custom_objects || [];
        const stdObjs = dm.standard_objects || [];
        const rels = dm.relationships || [];
        const erd = generateERDMermaid(dm);

        return (
          <div className="space-y-4">
            {/* Stats */}
            <div className="flex gap-4 text-sm">
              <span className="px-3 py-1 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-400">
                {customObjs.length} custom objects
              </span>
              <span className="px-3 py-1 bg-slate-500/10 border border-slate-500/30 rounded-lg text-slate-400">
                {stdObjs.length} standard objects
              </span>
              <span className="px-3 py-1 bg-purple-500/10 border border-purple-500/30 rounded-lg text-purple-400">
                {rels.length} relationships
              </span>
            </div>

            {/* ERD Diagram */}
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
              <h4 className="text-sm font-medium text-slate-300 mb-3">Entity Relationship Diagram</h4>
              <MermaidRenderer content={'```mermaid\n' + erd + '\n```'} />
            </div>

            {/* Objects table */}
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-800/50 text-slate-400">
                    <th className="text-left px-4 py-2 font-medium">Object</th>
                    <th className="text-left px-4 py-2 font-medium">Type</th>
                    <th className="text-left px-4 py-2 font-medium">Fields</th>
                    <th className="text-left px-4 py-2 font-medium">Purpose</th>
                  </tr>
                </thead>
                <tbody>
                  {customObjs.map((obj, i) => (
                    <tr key={i} className="border-t border-slate-700/50 hover:bg-slate-800/30">
                      <td className="px-4 py-2 text-cyan-400 font-mono text-xs">{obj.api_name}</td>
                      <td className="px-4 py-2 text-orange-400 text-xs">Custom</td>
                      <td className="px-4 py-2 text-slate-300">{(obj.fields || []).length}</td>
                      <td className="px-4 py-2 text-slate-400 text-xs max-w-xs truncate">{obj.purpose || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      }

      case 'flows': {
        const flows = archContent?.automation_design?.flows || [];
        if (flows.length === 0) return <EmptyTab label="Flows" />;

        return (
          <div className="space-y-3">
            <span className="text-sm px-3 py-1 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400">
              {flows.length} flows
            </span>
            {flows.map((flow, i) => {
              const isExpanded = expandedFlows.has(i);
              const mermaid = isExpanded ? generateFlowMermaid(flow) : '';
              return (
                <div key={i} className="bg-slate-900/50 border border-slate-700 rounded-lg overflow-hidden">
                  <button
                    onClick={() => toggleFlow(i)}
                    className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-800/30 transition-colors"
                  >
                    <div className="flex items-center gap-3 text-left">
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">{flow.type}</span>
                      <span className="text-sm text-slate-200 font-medium">{flow.label || flow.api_name}</span>
                      {flow.uc_refs && flow.uc_refs.length > 0 && (
                        <span className="text-xs text-slate-500">{flow.uc_refs.length} UCs</span>
                      )}
                    </div>
                    {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                  </button>
                  {isExpanded && (
                    <div className="px-4 pb-4 border-t border-slate-700/50">
                      {flow.trigger && (
                        <div className="text-xs text-slate-400 mt-2 mb-3">
                          Trigger: <span className="text-slate-300">{flow.trigger.object}</span> on <span className="text-slate-300">{flow.trigger.event}</span>
                          {flow.trigger.condition && <span className="text-slate-500"> when {flow.trigger.condition}</span>}
                        </div>
                      )}
                      {mermaid && <MermaidRenderer content={'```mermaid\n' + mermaid + '\n```'} />}
                      {flow.uc_refs && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {flow.uc_refs.map((uc, j) => (
                            <span key={j} className="text-xs px-1.5 py-0.5 bg-blue-500/10 text-blue-400 rounded">{uc}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );
      }

      case 'lwc': {
        // LWC data may be within flows or a separate section depending on Marcus output
        const flows = archContent?.automation_design?.flows || [];
        const lwcFlows = flows.filter(f => f.type?.toLowerCase().includes('lwc') || f.type?.toLowerCase().includes('screen'));
        const customObjs = archContent?.data_model?.custom_objects || [];

        return (
          <div className="space-y-4">
            <p className="text-sm text-slate-400">
              UI components are specified within the architecture's flow definitions and object page layouts.
            </p>
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
              <h4 className="text-sm font-medium text-slate-300 mb-2">Objects with UI Implications</h4>
              <div className="space-y-1">
                {customObjs.filter(o => o.fields && o.fields.length > 5).slice(0, 10).map((obj, i) => (
                  <div key={i} className="text-xs text-slate-400 flex items-center gap-2">
                    <Layout className="w-3 h-3 text-blue-400" />
                    <span className="text-cyan-400 font-mono">{obj.api_name}</span>
                    <span>— {(obj.fields || []).length} fields, {obj.sharing_model || 'Private'}</span>
                  </div>
                ))}
              </div>
            </div>
            {lwcFlows.length > 0 && (
              <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                <h4 className="text-sm font-medium text-slate-300 mb-2">Screen Flows</h4>
                {lwcFlows.map((f, i) => (
                  <div key={i} className="text-sm text-slate-300">{f.label || f.api_name}</div>
                ))}
              </div>
            )}
          </div>
        );
      }

      case 'security': {
        const dm = archContent?.data_model;
        if (!dm) return <EmptyTab label="Security" />;
        const customObjs = dm.custom_objects || [];
        const sharingModels = new Map<string, string[]>();
        for (const obj of customObjs) {
          const sm = obj.sharing_model || 'Private';
          if (!sharingModels.has(sm)) sharingModels.set(sm, []);
          sharingModels.get(sm)!.push(obj.api_name);
        }

        const rels = dm.relationships || [];
        const masterDetail = rels.filter(r => r.type === 'MasterDetail');
        const lookups = rels.filter(r => r.type === 'Lookup');

        return (
          <div className="space-y-4">
            {/* Sharing Model Summary */}
            <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
              <h4 className="text-sm font-medium text-slate-300 mb-3">OWD / Sharing Model</h4>
              <div className="space-y-2">
                {Array.from(sharingModels.entries()).map(([model, objects]) => (
                  <div key={model} className="flex items-start gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      model === 'Private' ? 'bg-red-500/10 text-red-400 border border-red-500/30' :
                      model === 'ControlledByParent' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30' :
                      'bg-green-500/10 text-green-400 border border-green-500/30'
                    }`}>{model}</span>
                    <div className="flex flex-wrap gap-1">
                      {objects.map((o, i) => (
                        <span key={i} className="text-xs text-slate-400 font-mono">{o}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Relationships summary */}
            <div className="flex gap-4 text-sm">
              <span className="px-3 py-1 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
                {masterDetail.length} Master-Detail
              </span>
              <span className="px-3 py-1 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-400">
                {lookups.length} Lookups
              </span>
            </div>
          </div>
        );
      }

      case 'wbs': {
        if (wbsPhases.length === 0) return <EmptyTab label="WBS" hint="WBS data not available or had parse errors." />;
        const ganttTasks = wbsToGanttTasks(wbsPhases);
        const totalTasks = wbsPhases.reduce((sum, p) => sum + (p.tasks?.length || 0), 0);

        return (
          <div className="space-y-4">
            <div className="flex gap-4 text-sm">
              <span className="px-3 py-1 bg-purple-500/10 border border-purple-500/30 rounded-lg text-purple-400">
                {wbsPhases.length} phases
              </span>
              <span className="px-3 py-1 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400">
                {totalTasks} tasks
              </span>
            </div>
            {ganttTasks.length > 0 && (
              <GanttChart tasks={ganttTasks} title="Work Breakdown Structure" />
            )}
            {/* Phase summary */}
            <div className="space-y-2">
              {wbsPhases.map((phase, i) => (
                <div key={i} className="bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-200">{phase.name}</span>
                    <span className="text-xs text-slate-500">{(phase.tasks || []).length} tasks · {phase.duration_weeks || '?'}w</span>
                  </div>
                </div>
              ))}
            </div>
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
            <h3 className="text-lg font-semibold text-blue-400 mb-1">Architecture Review</h3>
            <p className="text-slate-300 text-sm">
              Review Marcus's solution design across all dimensions before proceeding.
            </p>

            {coverageScore != null && (
              <div className="mt-3 flex items-center gap-3">
                <span className="text-slate-400 text-sm">
                  {revisionCount > 0 ? `Score after ${revisionCount} revision${revisionCount > 1 ? 's' : ''}:` : 'Coverage Score:'}
                </span>
                <span className={`text-2xl font-bold ${coverageScore >= 85 ? 'text-green-400' : coverageScore >= 70 ? 'text-orange-400' : 'text-red-400'}`}>
                  {Math.round(coverageScore)}%
                </span>
              </div>
            )}

            {criticalGaps.length > 0 && (
              <div className="mt-3">
                <p className="text-sm text-slate-400 font-medium mb-1">Critical Gaps ({criticalGaps.length}):</p>
                <ul className="space-y-1 max-h-32 overflow-y-auto">
                  {criticalGaps.map((gap, i) => (
                    <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                      <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${
                        gap.severity === 'high' ? 'bg-red-400' : gap.severity === 'medium' ? 'bg-orange-400' : 'bg-yellow-400'
                      }`} />
                      <span>
                        <span className={`font-medium ${
                          gap.severity === 'high' ? 'text-red-400' : gap.severity === 'medium' ? 'text-orange-400' : 'text-yellow-400'
                        }`}>[{gap.severity}]</span>{' '}
                        {gap.what_is_missing || gap.gap || gap.id || 'Unknown gap'}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {uncoveredUseCases.length > 0 && (
              <div className="mt-3">
                <p className="text-sm text-slate-400 font-medium mb-1">Uncovered Use Cases ({uncoveredUseCases.length}):</p>
                <ul className="space-y-0.5 max-h-24 overflow-y-auto">
                  {uncoveredUseCases.map((uc, i) => (
                    <li key={i} className="text-sm text-slate-300">
                      &bull; {typeof uc === 'string' ? uc : `${uc.id || ''}: ${uc.title || uc}`}
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
      <div className="p-5 min-h-[200px] max-h-[600px] overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
            <span className="text-slate-400 ml-3">Loading architecture data...</span>
          </div>
        ) : error ? (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">{error}</div>
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
          {isActioning ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
          {isActioning ? 'Processing...' : 'Approve Architecture'}
        </button>
        <button
          onClick={() => {
            if (showFeedback) { onRevise(); } else { setShowFeedback(true); }
          }}
          disabled={isActioning}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-indigo-700 transition-all shadow-lg shadow-blue-500/25 disabled:opacity-50"
        >
          <RotateCcw className="w-4 h-4" />
          {isActioning ? 'Processing...' : showFeedback ? 'Submit & Revise' : 'Revise Architecture'}
        </button>
        {showFeedback && (
          <button
            onClick={() => { setShowFeedback(false); setFeedback(''); }}
            className="text-sm text-slate-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

function EmptyTab({ label, hint }: { label: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-slate-500 text-sm">
      <p>No {label} data found in the architecture deliverables.</p>
      {hint && <p className="text-slate-600 text-xs mt-1">{hint}</p>}
    </div>
  );
}
