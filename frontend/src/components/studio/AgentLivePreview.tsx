import { motion, AnimatePresence } from 'framer-motion';
import { useLang } from '../../contexts/LangContext';
import {
  ACCENT_BORDER,
  ACCENT_TEXT,
  type AccentToken,
  type StudioAgent,
} from '../../lib/agents';

interface AgentLivePreviewProps {
  agent: StudioAgent | null;
  /** Free-text excerpt from the orchestrator (output_summary). */
  excerpt?: string | null;
  /** What the agent is doing right now. */
  currentTask?: string | null;
  /** 0–100. */
  progress?: number;
  /** Lifecycle hint from the page. */
  state: 'idle' | 'active' | 'completed' | 'failed' | 'waiting';
}

const ACCENT_PROGRESS_BG: Record<AccentToken, string> = {
  indigo: 'bg-indigo',
  plum: 'bg-plum',
  terra: 'bg-terra',
  sage: 'bg-sage',
  ochre: 'bg-ochre',
  brass: 'bg-brass',
};

export default function AgentLivePreview({
  agent,
  excerpt,
  currentTask,
  progress = 0,
  state,
}: AgentLivePreviewProps) {
  const { t } = useLang();
  const tone: AccentToken = agent?.accent ?? 'brass';
  const isActive = state === 'active';

  return (
    <section className={`bg-ink-2 border ${ACCENT_BORDER[tone]}`}>
      <header className="flex items-center justify-between border-b border-bone/10 px-5 py-3">
        <p className={`font-mono text-[10px] tracking-eyebrow uppercase ${ACCENT_TEXT[tone]}`}>
          {t('Live preview', 'Aperçu en direct')}
        </p>
        <p className="font-mono text-[10px] text-bone-4">
          {state === 'active'
            ? t('rendering…', 'rendu en cours…')
            : state === 'completed'
              ? t('final pass', 'pass final')
              : state === 'waiting'
                ? t('on hold', 'en attente')
                : state === 'failed'
                  ? t('interrupted', 'interrompu')
                  : t('curtain', 'rideau')}
        </p>
      </header>

      <div className="px-5 py-5 min-h-[180px]">
        <AnimatePresence mode="wait">
          <motion.div
            key={(agent?.id || 'none') + state}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.32, ease: 'easeOut' }}
          >
            {currentTask && (
              <p className="font-mono text-[11px] text-bone-3 mb-3 leading-relaxed">
                <span className={`${ACCENT_TEXT[tone]} mr-2`}>›</span>
                {currentTask}
              </p>
            )}

            {excerpt ? (
              <p className="font-serif text-bone-2 text-[15px] leading-relaxed whitespace-pre-wrap">
                {excerpt.length > 1400 ? excerpt.slice(0, 1400) + '…' : excerpt}
              </p>
            ) : (
              <p className="font-serif italic text-bone-4 text-[14px]">
                {isActive
                  ? t(
                      'The output is forming, line by line.',
                      'L’écriture se forme, ligne après ligne.',
                    )
                  : t(
                      'No deliverable yet — the act has not opened.',
                      'Aucun livrable encore — l’acte n’a pas commencé.',
                    )}
              </p>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="border-t border-bone/10 px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 w-16">
            {Math.round(progress)}%
          </span>
          <div className="flex-1 h-[2px] bg-bone/10 overflow-hidden">
            <motion.div
              className={`h-full ${ACCENT_PROGRESS_BG[tone]}`}
              initial={{ width: 0 }}
              animate={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
