import { useEffect, useState } from 'react';
import { X, ChevronDown, ChevronUp, FileText, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import MermaidRenderer, { extractMermaidBlocks } from './MermaidRenderer';
import StructuredRenderer from './StructuredRenderer';

interface DeliverablePreview {
  id: number;
  agent_id: number;
  agent_name: string;
  deliverable_type: string;
  content_preview: string;
  content_size: number;
  created_at: string;
}

interface DeliverableViewerProps {
  executionId: number;
  phaseNumber: number;
  onClose: () => void;
}

const PHASE_DELIVERABLE_MAP: Record<number, string[]> = {
  1: ['pm_br_extraction', 'br_extraction'],
  2: ['ba_use_cases', 'research_analyst_uc_digest'],
  3: [
    'architect_solution_design',
    'architect_as_is',
    'architect_gap_analysis',
    'research_analyst_coverage_report',
    'architect_wbs',
  ],
  4: ['qa_', 'devops_', 'data_', 'trainer_'],
  5: ['research_analyst_sds_document', 'research_analyst_write_sds'],
};

const PHASE_LABELS: Record<number, string> = {
  1: 'Business Requirements',
  2: 'Use Cases',
  3: 'Architecture',
  4: 'Expert Specs',
  5: 'SDS Final',
};

function formatDeliverableType(type: string): string {
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DeliverableViewer({ executionId, phaseNumber, onClose }: DeliverableViewerProps) {
  const [deliverables, setDeliverables] = useState<DeliverablePreview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [fullContents, setFullContents] = useState<Record<number, string>>({});
  const [loadingFull, setLoadingFull] = useState<number | null>(null);

  useEffect(() => {
    const fetchPreviews = async () => {
      setLoading(true);
      setError('');
      try {
        const data = await api.get(`/api/deliverables/executions/${executionId}/previews`);
        const previews: DeliverablePreview[] = Array.isArray(data) ? data : data?.deliverables || [];

        const phaseTypes = PHASE_DELIVERABLE_MAP[phaseNumber] || [];
        const filtered = previews.filter((d) => {
          // Phase 4 uses prefix matching
          if (phaseNumber === 4) {
            return phaseTypes.some((prefix) => d.deliverable_type.startsWith(prefix));
          }
          return phaseTypes.includes(d.deliverable_type);
        });

        setDeliverables(filtered);
      } catch (err: any) {
        setError(err.message || 'Failed to load deliverables');
      } finally {
        setLoading(false);
      }
    };

    fetchPreviews();
  }, [executionId, phaseNumber]);

  const handleExpand = async (deliverableId: number) => {
    if (expandedId === deliverableId) {
      setExpandedId(null);
      return;
    }

    setExpandedId(deliverableId);

    if (!fullContents[deliverableId]) {
      setLoadingFull(deliverableId);
      try {
        const data = await api.get(`/api/deliverables/${deliverableId}`);
        const content = typeof data === 'string' ? data : data?.content || data?.full_content || JSON.stringify(data, null, 2);
        setFullContents((prev) => ({ ...prev, [deliverableId]: content }));
      } catch (err: any) {
        setFullContents((prev) => ({
          ...prev,
          [deliverableId]: `Error loading content: ${err.message}`,
        }));
      } finally {
        setLoadingFull(null);
      }
    }
  };

  return (
    <div className="bg-ink-2 border border-bone/10 rounded-2xl p-6 mb-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <FileText className="w-5 h-5 text-brass" />
          <h3 className="text-lg font-semibold text-bone">
            Phase {phaseNumber}: {PHASE_LABELS[phaseNumber]} — Deliverables
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-ink-3 transition-colors text-bone-4 hover:text-bone"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 text-brass animate-spin" />
          <span className="text-bone-4 ml-3">Loading deliverables...</span>
        </div>
      )}

      {error && (
        <div className="bg-error/10 border border-error/30 rounded-xl p-4 text-error">
          {error}
        </div>
      )}

      {!loading && !error && deliverables.length === 0 && (
        <p className="text-bone-4 text-center py-6">No deliverables found for this phase.</p>
      )}

      {!loading && !error && deliverables.length > 0 && (
        <div className="space-y-3">
          {deliverables.map((d) => {
            const isExpanded = expandedId === d.id;
            const isLoadingThis = loadingFull === d.id;

            return (
              <div
                key={d.id}
                className="bg-ink border border-bone/15 rounded-xl overflow-hidden"
              >
                {/* Deliverable header */}
                <div className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h4 className="text-bone font-medium">
                        {formatDeliverableType(d.deliverable_type)}
                      </h4>
                      <p className="text-xs text-bone-4 mt-1">
                        {d.agent_name} &middot; {formatSize(d.content_size)} &middot;{' '}
                        {new Date(d.created_at).toLocaleString()}
                      </p>
                    </div>
                    {(d.deliverable_type.includes('sds_document') || d.deliverable_type.includes('write_sds')) ? (
                      <a
                        href={`/api/deliverables/${d.id}/render`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-brass text-ink hover:bg-brass/90 transition-colors"
                      >
                        Open SDS
                        <span aria-hidden="true">↗</span>
                      </a>
                    ) : (
                      <button
                        onClick={() => handleExpand(d.id)}
                        className="ml-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-brass/10 text-brass hover:bg-brass/20 transition-colors"
                      >
                        {isExpanded ? (
                          <>
                            <ChevronUp className="w-3.5 h-3.5" />
                            Collapse
                          </>
                        ) : (
                          <>
                            <ChevronDown className="w-3.5 h-3.5" />
                            View details
                          </>
                        )}
                      </button>
                    )}
                  </div>

                  {/* Preview (always visible) — hidden for SDS docs (Open SDS button replaces it) */}
                  {!isExpanded && d.content_preview && !(d.deliverable_type.includes('sds_document') || d.deliverable_type.includes('write_sds')) && (
                    <p className="mt-3 text-sm text-bone-4 line-clamp-3 whitespace-pre-wrap">
                      {d.content_preview}
                    </p>
                  )}
                </div>

                {/* Full content (expanded) */}
                {isExpanded && (
                  <div className="border-t border-bone/10 p-4">
                    {isLoadingThis ? (
                      <div className="flex items-center gap-2 py-4">
                        <Loader2 className="w-4 h-4 text-brass animate-spin" />
                        <span className="text-bone-4 text-sm">Loading full content...</span>
                      </div>
                    ) : (() => {
                      const text = fullContents[d.id] || d.content_preview;
                      const hasMermaid = extractMermaidBlocks(text).some(b => b.type === 'mermaid');
                      const isSDS = d.deliverable_type.includes('sds') || d.deliverable_type.includes('write_sds');
                      const isJSON = text.trimStart().startsWith('{') || text.trimStart().startsWith('[');

                      // SDS deliverables now have their own "Open SDS" button (opens /render)
                      // so this branch won't fire — we keep the JSON path for everything else.
                      // JSON deliverables → StructuredRenderer (tables, badges, etc.)
                      if (isJSON) {
                        return (
                          <div className="max-h-[600px] overflow-y-auto">
                            <StructuredRenderer deliverableType={d.deliverable_type} content={text} />
                          </div>
                        );
                      }
                      // Mermaid content
                      if (hasMermaid) {
                        return (
                          <div className="max-h-[600px] overflow-y-auto bg-ink rounded-lg p-4">
                            <MermaidRenderer content={text} />
                          </div>
                        );
                      }
                      // Plain text fallback
                      return (
                        <pre className="text-sm text-bone-3 whitespace-pre-wrap break-words max-h-96 overflow-y-auto font-mono bg-ink rounded-lg p-4">
                          {text}
                        </pre>
                      );
                    })()}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
