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
  const [mode, setMode] = useState<'idle' | 'annotating' | 'submitting'>('idle');
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
    <div className="mb-6 bg-purple-500/10 border border-purple-500/30 rounded-xl p-6">
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center flex-shrink-0">
          <FileText className="w-6 h-6 text-purple-400" />
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-purple-400 mb-2">
            {pending.gate_label || 'Validation Required'}
          </h3>
          <p className="text-slate-300 mb-4">
            The pipeline has paused for your review. Please examine the deliverables
            and either approve to continue or request changes with feedback.
          </p>

          {/* Deliverables summary */}
          {Object.keys(deliverables).length > 0 && (
            <div className="mb-4 bg-slate-800/50 rounded-lg p-4">
              <p className="text-sm text-slate-400 font-medium mb-2">Deliverables Summary</p>
              <div className="space-y-1">
                {deliverables.phase && (
                  <p className="text-sm text-slate-300">
                    <span className="text-slate-500">Phase:</span> {deliverables.phase}
                  </p>
                )}
                {deliverables.completed_experts && deliverables.completed_experts.length > 0 && (
                  <p className="text-sm text-slate-300">
                    <span className="text-slate-500">Completed:</span>{' '}
                    {deliverables.completed_experts.join(', ')}
                  </p>
                )}
                {deliverables.failed_experts && deliverables.failed_experts.length > 0 && (
                  <p className="text-sm text-red-400">
                    <span className="text-slate-500">Failed:</span>{' '}
                    {deliverables.failed_experts.join(', ')}
                  </p>
                )}
                {deliverables.sds_length && (
                  <p className="text-sm text-slate-300">
                    <span className="text-slate-500">SDS Document:</span>{' '}
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
              <label className="block text-sm text-slate-400 mb-2">
                <MessageSquare className="w-4 h-4 inline mr-1" />
                Feedback for the agent
              </label>
              <textarea
                value={annotations}
                onChange={(e) => setAnnotations(e.target.value)}
                placeholder="Describe what needs to be changed. The agent will receive this feedback and re-run the phase..."
                className="w-full h-32 bg-slate-800 border border-slate-600 rounded-lg p-3 text-slate-200 placeholder-slate-500 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 outline-none resize-y"
              />
            </div>
          )}

          {error && (
            <div className="mb-4 text-sm text-red-400">{error}</div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3">
            {mode !== 'annotating' ? (
              <>
                <button
                  onClick={handleApprove}
                  disabled={mode === 'submitting'}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-green-500 to-emerald-600 text-white font-medium rounded-xl hover:from-green-600 hover:to-emerald-700 transition-all shadow-lg shadow-green-500/25 disabled:opacity-50"
                >
                  {mode === 'submitting' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <CheckCircle className="w-4 h-4" />
                  )}
                  {mode === 'submitting' ? 'Processing...' : 'Approve & Continue'}
                </button>
                <button
                  onClick={() => setMode('annotating')}
                  disabled={mode === 'submitting'}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-orange-500 to-red-600 text-white font-medium rounded-xl hover:from-orange-600 hover:to-red-700 transition-all shadow-lg shadow-orange-500/25 disabled:opacity-50"
                >
                  <RotateCcw className="w-4 h-4" />
                  Request Changes
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={handleReject}
                  disabled={mode === 'submitting'}
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-orange-500 to-red-600 text-white font-medium rounded-xl hover:from-orange-600 hover:to-red-700 transition-all shadow-lg shadow-orange-500/25 disabled:opacity-50"
                >
                  {mode === 'submitting' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RotateCcw className="w-4 h-4" />
                  )}
                  {mode === 'submitting' ? 'Submitting...' : 'Submit Feedback & Rerun'}
                </button>
                <button
                  onClick={() => { setMode('idle'); setError(''); }}
                  className="inline-flex items-center gap-2 px-5 py-2.5 border border-slate-600 text-slate-300 font-medium rounded-xl hover:bg-slate-700/50 transition-all"
                >
                  Cancel
                </button>
              </>
            )}
          </div>

          <p className="text-xs text-slate-500 mt-3">
            Paused at {new Date(pending.paused_at).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}
