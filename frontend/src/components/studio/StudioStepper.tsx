import { Check } from 'lucide-react';
import { motion } from 'framer-motion';

export interface StudioStep {
  id: string;
  label: string;
  /** Sous-titre court : ex. "The Opening". */
  subtitle?: string;
}

interface StudioStepperProps {
  steps: StudioStep[];
  currentIndex: number;
  /** Indices des étapes complétées (≠ currentIndex). */
  completed: Set<number> | number[];
  onJump?: (index: number) => void;
}

export default function StudioStepper({
  steps,
  currentIndex,
  completed,
  onJump,
}: StudioStepperProps) {
  const completedSet = completed instanceof Set ? completed : new Set(completed);

  return (
    <ol className="flex flex-col gap-4">
      {steps.map((step, index) => {
        const isCurrent = index === currentIndex;
        const isCompleted = completedSet.has(index);
        const isClickable = onJump && (isCompleted || index <= currentIndex);

        return (
          <li key={step.id} className="relative">
            <button
              type="button"
              disabled={!isClickable}
              onClick={isClickable ? () => onJump?.(index) : undefined}
              className={[
                'group w-full flex items-start gap-3 text-left transition-colors',
                isClickable ? 'cursor-pointer' : 'cursor-default',
              ].join(' ')}
            >
              <span
                aria-hidden
                className={[
                  'mt-[2px] inline-flex w-5 h-5 shrink-0 items-center justify-center border',
                  isCurrent
                    ? 'border-brass bg-brass/10 text-brass'
                    : isCompleted
                      ? 'border-brass bg-brass text-ink'
                      : 'border-bone/20 text-bone-4',
                ].join(' ')}
              >
                {isCompleted ? (
                  <motion.span
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 24 }}
                    className="inline-flex"
                  >
                    <Check className="w-3 h-3" />
                  </motion.span>
                ) : isCurrent ? (
                  <motion.span
                    aria-hidden
                    className="inline-block w-1.5 h-1.5 rounded-full bg-brass"
                    animate={{ opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
                  />
                ) : (
                  <span className="font-mono text-[10px] text-bone-4">
                    {index + 1}
                  </span>
                )}
              </span>
              <span className="flex flex-col leading-tight">
                <span
                  className={[
                    'font-mono text-[10px] tracking-eyebrow uppercase',
                    isCurrent ? 'text-brass' : isCompleted ? 'text-bone-3' : 'text-bone-4',
                  ].join(' ')}
                >
                  {step.label}
                </span>
                {step.subtitle && (
                  <span
                    className={[
                      'mt-1 font-serif italic text-[15px] leading-snug',
                      isCurrent ? 'text-bone' : 'text-bone-3',
                    ].join(' ')}
                  >
                    {step.subtitle}
                  </span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
