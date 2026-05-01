/**
 * StructuredRenderer — renders JSON deliverables as readable UI
 * Used by DeliverableViewer for non-Markdown content (architect, expert specs, BRs, etc.)
 */
import { useState } from 'react';
import { ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';

interface StructuredRendererProps {
  deliverableType: string;
  content: string;
}

function tryParseJSON(text: string): any | null {
  try {
    const parsed = JSON.parse(text);
    // Unwrap nested content key
    return parsed?.content || parsed;
  } catch {
    return null;
  }
}

// --- BR Extraction ---
function BRTable({ data }: { data: any }) {
  const brs = data?.business_requirements || data?.requirements || (Array.isArray(data) ? data : []);
  if (!brs.length) return <FallbackJSON data={data} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-ink-2 text-bone-4">
            <th className="text-left px-3 py-2 font-medium">ID</th>
            <th className="text-left px-3 py-2 font-medium">Title</th>
            <th className="text-left px-3 py-2 font-medium">Priority</th>
            <th className="text-left px-3 py-2 font-medium">Category</th>
          </tr>
        </thead>
        <tbody>
          {brs.map((br: any, i: number) => (
            <tr key={i} className="border-t border-bone/10 hover:bg-ink-2/60">
              <td className="px-3 py-2 text-brass font-mono text-xs">{br.id || br.br_id || `BR-${i + 1}`}</td>
              <td className="px-3 py-2 text-bone-2">{br.title || br.description || '-'}</td>
              <td className="px-3 py-2">
                <PriorityBadge priority={br.priority} />
              </td>
              <td className="px-3 py-2 text-bone-4 text-xs">{br.category || br.type || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Coverage Report ---
function CoverageReport({ data }: { data: any }) {
  const score = data?.overall_coverage_score;
  const gaps = data?.critical_gaps || [];
  const byCategory = data?.by_category || {};

  return (
    <div className="space-y-4">
      {score != null && (
        <div className="flex items-center gap-3">
          <span className="text-bone-4 text-sm">Coverage:</span>
          <span className={`text-2xl font-bold ${score >= 85 ? 'text-sage' : score >= 70 ? 'text-ochre' : 'text-error'}`}>
            {Math.round(score)}%
          </span>
          <span className="text-bone-4 text-sm">{data?.verdict || ''}</span>
        </div>
      )}
      {Object.keys(byCategory).length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {Object.entries(byCategory).map(([cat, val]: [string, any]) => (
            <div key={cat} className="bg-ink border border-bone/10 rounded-lg px-3 py-2">
              <span className="text-xs text-bone-4 block">{cat.replace(/_/g, ' ')}</span>
              <span className={`text-lg font-semibold ${(val?.score ?? val) >= 85 ? 'text-sage' : 'text-ochre'}`}>
                {Math.round(val?.score ?? val)}%
              </span>
            </div>
          ))}
        </div>
      )}
      {gaps.length > 0 && (
        <CollapsibleList title={`Critical Gaps (${gaps.length})`} defaultOpen={gaps.length <= 10}>
          <div className="space-y-1">
            {gaps.map((g: any, i: number) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <AlertTriangle className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${
                  g.severity === 'high' ? 'text-error' : g.severity === 'medium' ? 'text-ochre' : 'text-ochre'
                }`} />
                <span className="text-bone-3">{g.what_is_missing || g.gap || g.id}</span>
              </div>
            ))}
          </div>
        </CollapsibleList>
      )}
    </div>
  );
}

// --- Gap Analysis ---
function GapAnalysis({ data }: { data: any }) {
  const gaps = data?.gaps || (Array.isArray(data) ? data : []);
  const categories = new Map<string, any[]>();
  for (const g of gaps) {
    const cat = g.category || 'OTHER';
    if (!categories.has(cat)) categories.set(cat, []);
    categories.get(cat)!.push(g);
  }

  return (
    <div className="space-y-3">
      <span className="text-sm text-bone-4">{gaps.length} gaps identified across {categories.size} categories</span>
      {Array.from(categories.entries()).map(([cat, catGaps]) => (
        <CollapsibleList key={cat} title={`${cat.replace(/_/g, ' ')} (${catGaps.length})`}>
          <div className="space-y-1">
            {catGaps.map((g: any, i: number) => (
              <div key={i} className="text-sm text-bone-3 flex items-start gap-2">
                <span className="text-xs text-bone-4 font-mono flex-shrink-0 w-20">{g.id}</span>
                <span>{g.what_exists || g.current_state || '-'} → {g.what_is_needed || g.target_state || '-'}</span>
              </div>
            ))}
          </div>
        </CollapsibleList>
      ))}
    </div>
  );
}

// --- Expert Specs (QA, DevOps, Training, Data Migration) ---
function ExpertSpecs({ data, type }: { data: any; type: string }) {
  if (type.includes('qa')) return <QASpecs data={data} />;
  if (type.includes('devops')) return <DevOpsSpecs data={data} />;
  if (type.includes('trainer')) return <TrainingSpecs data={data} />;
  if (type.includes('data')) return <DataMigrationSpecs data={data} />;
  return <FallbackJSON data={data} />;
}

function QASpecs({ data }: { data: any }) {
  const scenarios = data?.test_scenarios || data?.test_cases || data?.scenarios || [];
  if (!scenarios.length) return <FallbackJSON data={data} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-ink-2 text-bone-4">
            <th className="text-left px-3 py-2 font-medium">ID</th>
            <th className="text-left px-3 py-2 font-medium">Scenario</th>
            <th className="text-left px-3 py-2 font-medium">Type</th>
            <th className="text-left px-3 py-2 font-medium">Priority</th>
          </tr>
        </thead>
        <tbody>
          {scenarios.slice(0, 30).map((s: any, i: number) => (
            <tr key={i} className="border-t border-bone/10 hover:bg-ink-2/60">
              <td className="px-3 py-2 text-brass font-mono text-xs">{s.id || `TC-${i + 1}`}</td>
              <td className="px-3 py-2 text-bone-2">{s.name || s.title || s.description || '-'}</td>
              <td className="px-3 py-2 text-xs text-bone-4">{s.type || s.test_type || '-'}</td>
              <td className="px-3 py-2"><PriorityBadge priority={s.priority} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {scenarios.length > 30 && <p className="text-xs text-bone-4 mt-2">+ {scenarios.length - 30} more scenarios</p>}
    </div>
  );
}

function DevOpsSpecs({ data }: { data: any }) {
  const steps = data?.pipeline_steps || data?.pipeline || data?.deployment_steps || [];
  const environments = data?.environments || [];
  return (
    <div className="space-y-3">
      {environments.length > 0 && (
        <div className="flex gap-2">
          {environments.map((env: any, i: number) => (
            <span key={i} className="text-xs px-2 py-1 bg-indigo/10 border border-indigo/30 rounded text-indigo">
              {typeof env === 'string' ? env : env.name || env.type}
            </span>
          ))}
        </div>
      )}
      {steps.length > 0 ? (
        <div className="space-y-2">
          {steps.map((s: any, i: number) => (
            <div key={i} className="bg-ink border border-bone/10 rounded-lg px-3 py-2 flex items-center gap-3">
              <span className="text-xs text-bone-4 font-mono w-6">{i + 1}</span>
              <span className="text-sm text-bone-2">{s.name || s.step || s.description || JSON.stringify(s)}</span>
            </div>
          ))}
        </div>
      ) : (
        <FallbackJSON data={data} />
      )}
    </div>
  );
}

function TrainingSpecs({ data }: { data: any }) {
  const modules = data?.modules || data?.training_modules || data?.sessions || [];
  if (!modules.length) return <FallbackJSON data={data} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-ink-2 text-bone-4">
            <th className="text-left px-3 py-2 font-medium">Module</th>
            <th className="text-left px-3 py-2 font-medium">Audience</th>
            <th className="text-left px-3 py-2 font-medium">Duration</th>
          </tr>
        </thead>
        <tbody>
          {modules.map((m: any, i: number) => (
            <tr key={i} className="border-t border-bone/10 hover:bg-ink-2/60">
              <td className="px-3 py-2 text-bone-2">{m.name || m.title || m.module_name || '-'}</td>
              <td className="px-3 py-2 text-xs text-bone-4">{m.audience || m.target_audience || m.role || '-'}</td>
              <td className="px-3 py-2 text-xs text-bone-4">{m.duration || m.estimated_duration || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DataMigrationSpecs({ data }: { data: any }) {
  const mappings = data?.mappings || data?.migration_objects || data?.objects || [];
  if (!mappings.length) return <FallbackJSON data={data} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-ink-2 text-bone-4">
            <th className="text-left px-3 py-2 font-medium">Source</th>
            <th className="text-left px-3 py-2 font-medium">Target</th>
            <th className="text-left px-3 py-2 font-medium">Records</th>
            <th className="text-left px-3 py-2 font-medium">Strategy</th>
          </tr>
        </thead>
        <tbody>
          {mappings.map((m: any, i: number) => (
            <tr key={i} className="border-t border-bone/10 hover:bg-ink-2/60">
              <td className="px-3 py-2 text-brass font-mono text-xs">{m.source || m.source_object || '-'}</td>
              <td className="px-3 py-2 text-sage font-mono text-xs">{m.target || m.target_object || m.api_name || '-'}</td>
              <td className="px-3 py-2 text-bone-4 text-xs">{m.record_count || m.estimated_records || '-'}</td>
              <td className="px-3 py-2 text-bone-4 text-xs">{m.strategy || m.migration_type || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- Helpers ---
function PriorityBadge({ priority }: { priority?: string }) {
  if (!priority) return <span className="text-bone-4 text-xs">-</span>;
  const p = priority.toLowerCase();
  const color = p.includes('high') || p === 'p1' ? 'text-error bg-error/10 border-error/30'
    : p.includes('medium') || p === 'p2' ? 'text-ochre bg-ochre/10 border-ochre/30'
    : 'text-sage bg-sage/10 border-sage/30';
  return <span className={`text-xs px-1.5 py-0.5 rounded border ${color}`}>{priority}</span>;
}

function CollapsibleList({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-ink border border-bone/10 rounded-lg overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-ink-2/60 transition-colors">
        <span className="text-sm font-medium text-bone-3">{title}</span>
        {open ? <ChevronUp className="w-4 h-4 text-bone-4" /> : <ChevronDown className="w-4 h-4 text-bone-4" />}
      </button>
      {open && <div className="px-4 pb-3 border-t border-bone/10">{children}</div>}
    </div>
  );
}

function FallbackJSON({ data }: { data: any }) {
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  return (
    <pre className="text-xs text-bone-4 whitespace-pre-wrap break-words max-h-96 overflow-y-auto font-mono bg-ink rounded-lg p-4">
      {text.substring(0, 5000)}
      {text.length > 5000 && '\n... (truncated)'}
    </pre>
  );
}

// --- Main router ---
export default function StructuredRenderer({ deliverableType, content }: StructuredRendererProps) {
  const data = tryParseJSON(content);
  if (!data) {
    return (
      <pre className="text-sm text-bone-3 whitespace-pre-wrap break-words max-h-96 overflow-y-auto font-mono bg-ink rounded-lg p-4">
        {content}
      </pre>
    );
  }

  const t = deliverableType.toLowerCase();

  if (t.includes('br_extraction') || t.includes('business_requirement')) return <BRTable data={data} />;
  if (t.includes('coverage_report') || t.includes('coverage')) return <CoverageReport data={data} />;
  if (t.includes('gap_analysis') || t.includes('gap')) return <GapAnalysis data={data} />;
  if (t.includes('qa_') || t.includes('devops_') || t.includes('trainer_') || t.includes('data_migration') || t.includes('data_')) {
    return <ExpertSpecs data={data} type={t} />;
  }

  // For architecture JSON — show summary, not raw JSON
  if (t.includes('solution_design') || t.includes('architect_')) {
    const dm = data?.data_model;
    const flows = data?.automation_design?.flows;
    if (dm || flows) {
      return (
        <div className="space-y-3">
          {dm && (
            <div className="flex gap-3 text-sm">
              <span className="px-2 py-1 bg-indigo/10 border border-indigo/30 rounded text-indigo">
                {(dm.custom_objects || []).length} custom objects
              </span>
              <span className="px-2 py-1 bg-bone/5 border border-bone/20 rounded text-bone-4">
                {(dm.standard_objects || []).length} standard objects
              </span>
              <span className="px-2 py-1 bg-plum/10 border border-plum/30 rounded text-plum">
                {(dm.relationships || []).length} relationships
              </span>
            </div>
          )}
          {flows && (
            <span className="text-sm px-2 py-1 bg-sage/10 border border-sage/30 rounded text-sage inline-block">
              {flows.length} automation flows
            </span>
          )}
          <p className="text-xs text-bone-4">Full architecture view available in the Architecture Review panel above.</p>
        </div>
      );
    }
  }

  // Fallback
  return <FallbackJSON data={data} />;
}
