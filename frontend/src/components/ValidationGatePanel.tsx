/**
 * P2-Full: Generic validation gate panel.
 *
 * Displayed when an execution is paused at a configurable validation gate
 * (after_expert_specs, after_sds_generation, after_build_code).
 *
 * Shows:
 * - Gate name and deliverables summary
 * - "Approve & Continue" button
 * - "Request Changes" button with annotation textarea
 */
import { useState } from 'react';
import { CheckCircle, RotateCcw, MessageSquare, Loader2, FileText } from 'lucide-react';
import { executions } from '../services/api';

interface ValidationGatePanelProps {
  executionId: number;
  pending: {
    gate: string;
    gate_label: string;
    deliverables: Record<string, any>;
    paused_at: string;
  };
  onResume: () => void;
}

export default function ValidationGatePanel({
  executionId,
  pending,
  onResume,
}: ValidationGatePanelProps) {
  const [mode, setMode] = useState<string>('idle');
  const [annotations, setAnnotations] = useState('');
  const [error, setError] = useState('');

  const handleApprove = async () => {
    setMode('submitting');
    setError('');
    try {
      await executions.submitValidationGate(executionId, true);
      onResume();
    } catch (err: any) {
      setError(err.message || 'Failed to approve');
      setMode('idle');
    }
  };

  const handleReject = async () => {
    if (!annotations.trim()) {
      setError('Please provide feedback for the agent before requesting changes.');
      return;
    }
    setMode('submitting');
    setError('');
    try {
      await executions.submitValidationGate(executionId, false, annotations);
      onResume();
    } catch (err: any) {
      setError(err.message || 'Failed to submit feedback');
      setMode('annotating');
    }
  };

  const deliverables = pending.deliverables || {};

  return (
    <div className="mb-6 bg-plum/10 border border-plum/30 rounded-xl p-6">
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-xl bg-plum/20 flex items-center justify-center flex-shrink-0">
          <FileText className="w-6 h-6 text-plum" />
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-plum mb-2">
            {pending.gate_label || 'Validation Required'}
          </h3>
          <p className="text-bone-3 mb-4">
            The pipeline has paused for your review. Please examine the deliverables
            and either approve to continue or request changes with feedback.
          </p>

          {/* Deliverables summary */}
          {Object.keys(deliverables).length > 0 && (
            <div className="mb-4 bg-ink-2 rounded-lg p-4">
              <p className="text-sm text-bone-4 font-medium mb-2">Deliverables Summary</p>
              <div className="space-y-1">
                {deliverables.phase && (
                  <p className="text-sm text-bone-3">
                    <span className="text-bone-4">Phase:</span> {deliverables.phase}
                  </p>
                )}
                {deliverables.completed_experts && deliverables.completed_experts.length > 0 && (
                  <p className="text-sm text-bone-3">
                    <span className="text-bone-4">Completed:</span>{' '}
                    {deliverables.completed_experts.join(', ')}
                  </p>
                )}
                {deliverables.failed_experts && deliverables.failed_experts.length > 0 && (
                  <p className="text-sm text-error">
                    <span className="text-bone-4">Failed:</span>{' '}
                    {deliverables.failed_experts.join(', ')}
                  </p>
                )}
                {deliverables.sds_length && (
                  <p className="text-sm text-bone-3">
                    <span className="text-bone-4">SDS Document:</span>{' '}
                    {Math.round(deliverables.sds_length / 1000)}K characters
                    {deliverables.has_annexe && ' (with Annexe A)'}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Annotation area (shown when requesting changes) */}
          {mode === 'annotating' && (
            <div className="mb-4">
              <label className="block text-sm text-bone-4 mb-2">
                <MessageSquare className="w-4 h-4 inline mr-1" />
                Feedback for the agent
              </label>
              <textarea
                value={annotations}
                onChange={(e) => setAnnotations(e.target.value)}
                placeholder="Describe what needs to be changed. The agent will receive this feedback and re-run the phase..."
                className="w-full h-32 bg-ink-2 border border-bone/15 rounded-lg p-3 text-bone-2 placeholder-bone-4 focus:border-plum focus:ring-1 focus:ring-plum outline-none resize-y"
              />
            </div>
          )}

          {error && (
            <div className="mb-4 text-sm text-error">{error}</div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3">
            {mode !== 'annotating' ? (
              <>
                <button
                  onClick={handleApprove}
                  disabled={(mode as string) === 'submitting'}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-sage text-bone font-medium rounded-xl hover:bg-sage/80 transition-all shadow-lg shadow-sage/25 disabled:opacity-50"
                >
                  {(mode as string) === 'submitting' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <CheckCircle className="w-4 h-4" />
                  )}
                  {(mode as string) === 'submitting' ? 'Processing...' : 'Approve & Continue'}
                </button>
                <button
                  onClick={() => setMode('annotating')}
                  disabled={(mode as string) === 'submitting'}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-error text-bone font-medium rounded-xl hover:bg-error/80 transition-all shadow-lg shadow-error/25 disabled:opacity-50"
                >
                  <RotateCcw className="w-4 h-4" />
                  Request Changes
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={handleReject}
                  disabled={(mode as string) === 'submitting'}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-error text-bone font-medium rounded-xl hover:bg-error/80 transition-all shadow-lg shadow-error/25 disabled:opacity-50"
                >
                  {(mode as string) === 'submitting' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RotateCcw className="w-4 h-4" />
                  )}
                  {(mode as string) === 'submitting' ? 'Submitting...' : 'Submit Feedback & Rerun'}
                </button>
                <button
                  onClick={() => { setMode('idle'); setError(''); }}
                  className="inline-flex items-center gap-2 px-5 py-2.5 border border-bone/15 text-bone-3 font-medium rounded-xl hover:bg-ink-3/60 transition-all"
                >
                  Cancel
                </button>
              </>
            )}
          </div>

          <p className="text-xs text-bone-4 mt-3">
            Paused at {new Date(pending.paused_at).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}
