import { motion } from 'framer-motion';
import { Check, AlertCircle, Pause } from 'lucide-react';
import { useLang } from '../../contexts/LangContext';
import {
  ACCENT_TEXT,
  type AccentToken,
  type TheatreStep,
  getAgentById,
} from '../../lib/agents';

export type StepStatus =
  | 'pending'
  | 'current'
  | 'completed'
  | 'waiting_hitl'
  | 'failed';

export interface StudioTimelineEntry extends TheatreStep {
  status: StepStatus;
  /** Whether this step has produced reviewable deliverables. */
  hasDeliverables?: boolean;
}

interface StudioTimelineProps {
  steps: StudioTimelineEntry[];
  onSelect?: (step: StudioTimelineEntry) => void;
  selectedId?: string | null;
  /** Optional eyebrow above the timeline. */
  title?: string;
}

const STATUS_DOT: Record<StepStatus, string> = {
  pending: 'bg-ink-3 border-bone/15',
  current: 'bg-brass border-brass',
  completed: 'bg-brass/20 border-brass',
  waiting_hitl: 'bg-warning/20 border-warning',
  failed: 'bg-error/20 border-error',
};

export default function StudioTimeline({
  steps,
  onSelect,
  selectedId,
  title,
}: StudioTimelineProps) {
  const { t } = useLang();

  return (
    <nav aria-label={title ?? 'Theatre timeline'} className="bg-ink-2 border border-bone/10">
      <div className="px-5 py-4 border-b border-bone/10">
        <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
          {title ?? t('The score', 'La partition')}
        </p>
        <p className="mt-1 font-serif italic text-bone text-lg">
          {t('Acts of the performance', 'Actes de la représentation')}
        </p>
      </div>

      <ol className="relative px-5 py-5 space-y-4">
        {/* Vertical hairline behind dots */}
        <span
          aria-hidden
          className="absolute left-[27px] top-7 bottom-7 w-px bg-bone/10"
        />
        {steps.map((step, idx) => {
          const agent = getAgentById(step.agentId);
          const tone: AccentToken = agent?.accent ?? 'brass';
          const isClickable =
            !!onSelect &&
            (step.status === 'completed' ||
              step.status === 'waiting_hitl' ||
              step.hasDeliverables === true);
          const isSelected = selectedId === step.id;

          return (
            <li key={step.id} className="relative pl-10">
              <button
                type="button"
                disabled={!isClickable}
                onClick={() => isClickable && onSelect?.(step)}
                className={[
                  'group w-full text-left',
                  isClickable ? 'cursor-pointer' : 'cursor-default',
                ].join(' ')}
              >
                {/* Dot */}
                <span
                  aria-hidden
                  className={[
                    'absolute left-1.5 top-1 w-5 h-5 border flex items-center justify-center',
                    STATUS_DOT[step.status],
                  ].join(' ')}
                >
                  {step.status === 'completed' && (
                    <Check className="w-3 h-3 text-brass" />
                  )}
                  {step.status === 'failed' && (
                    <AlertCircle className="w-3 h-3 text-error" />
                  )}
                  {step.status === 'waiting_hitl' && (
                    <Pause className="w-3 h-3 text-warning" />
                  )}
                  {step.status === 'current' && (
                    <motion.span
                      className="w-1.5 h-1.5 rounded-full bg-ink"
                      animate={{ opacity: [0.4, 1, 0.4] }}
                      transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
                    />
                  )}
                  {step.status === 'pending' && (
                    <span className="font-mono text-[9px] text-bone-4">{idx + 1}</span>
                  )}
                </span>

                <p
                  className={[
                    'font-mono text-[10px] tracking-eyebrow uppercase',
                    step.status === 'current'
                      ? ACCENT_TEXT[tone]
                      : step.status === 'waiting_hitl'
                        ? 'text-warning'
                        : step.status === 'failed'
                          ? 'text-error'
                          : step.status === 'completed'
                            ? 'text-bone-3'
                            : 'text-bone-4',
                  ].join(' ')}
                >
                  {t(step.label.en, step.label.fr)}
                </p>
                <p
                  className={[
                    'mt-1 font-serif italic text-[15px] leading-snug',
                    step.status === 'pending' ? 'text-bone-4' : 'text-bone-2',
                    isSelected ? 'underline decoration-brass/60 underline-offset-4' : '',
                  ].join(' ')}
                >
                  {agent
                    ? `${agent.name.en} — `
                    : ''}
                  {t(step.cue.en, step.cue.fr)}
                </p>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
