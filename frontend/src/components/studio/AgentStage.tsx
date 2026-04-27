import { motion, AnimatePresence } from 'framer-motion';
import {
  ACCENT_BORDER,
  ACCENT_BORDER_STRONG,
  ACCENT_TEXT,
  type AccentToken,
  type StudioAgent,
} from '../../lib/agents';
import { useLang } from '../../contexts/LangContext';

interface AgentStageProps {
  agent: StudioAgent | null;
  /** What the agent is currently doing (free text from the orchestrator). */
  currentTask?: string;
  /** Lifecycle hint : 'active' pulses, 'completed' rests, 'idle' is muted. */
  state: 'idle' | 'active' | 'completed' | 'failed' | 'waiting';
  /** Optional timestamp (act start). */
  startedAt?: string;
  /** Optional act eyebrow override (defaults to ACT_LABELS[agent.act]). */
  eyebrow?: string;
  /** Override accent (used when agent is null but we still want an accent). */
  accent?: AccentToken;
}

const ACT_NUMERAL: Record<string, string> = {
  I: 'I',
  II: 'II',
  III: 'III',
  IV: 'IV',
  V: 'V',
};

const ACCENT_DOT: Record<AccentToken, string> = {
  indigo: 'bg-indigo',
  plum: 'bg-plum',
  terra: 'bg-terra',
  sage: 'bg-sage',
  ochre: 'bg-ochre',
  brass: 'bg-brass',
};

export default function AgentStage({
  agent,
  currentTask,
  state,
  eyebrow,
  accent,
}: AgentStageProps) {
  const { t, lang } = useLang();
  const tone: AccentToken = accent ?? agent?.accent ?? 'brass';

  const isActive = state === 'active';
  const isWaiting = state === 'waiting';
  const isCompleted = state === 'completed';
  const isFailed = state === 'failed';

  const bracket = isActive
    ? ACCENT_BORDER_STRONG[tone]
    : ACCENT_BORDER[tone];

  return (
    <section className="relative bg-ink-2 border border-bone/10 px-6 py-8 md:px-10 md:py-12 overflow-hidden">
      {/* Brass corners — subtle frame */}
      <div className={`pointer-events-none absolute inset-3 border ${bracket} opacity-70`} />
      {isActive && (
        <motion.div
          aria-hidden
          className={`pointer-events-none absolute inset-3 border ${ACCENT_BORDER_STRONG[tone]}`}
          animate={{ opacity: [0.35, 1, 0.35] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}

      <div className="relative flex items-center gap-6 md:gap-10">
        {/* Avatar */}
        <div className="relative shrink-0">
          <AnimatePresence mode="wait">
            <motion.img
              key={agent?.slug || 'placeholder'}
              src={agent ? `/avatars/large/${agent.slug}.png` : '/avatars/large/sophie-pm.png'}
              alt={agent ? agent.name[lang] : 'Stage'}
              initial={{ opacity: 0, scale: 0.94 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
              className={`w-28 h-28 md:w-32 md:h-32 object-cover border ${bracket} grayscale-[15%]`}
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = 'none';
              }}
            />
          </AnimatePresence>
          {isActive && (
            <motion.span
              aria-hidden
              className={`absolute -inset-2 border ${ACCENT_BORDER_STRONG[tone]}`}
              animate={{ opacity: [0.6, 1, 0.6], scale: [1, 1.03, 1] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            />
          )}
        </div>

        {/* Copy */}
        <div className="min-w-0 flex-1">
          <p className={`font-mono text-[10px] md:text-[11px] tracking-eyebrow uppercase ${ACCENT_TEXT[tone]}`}>
            {eyebrow ??
              (agent
                ? t(`Act ${ACT_NUMERAL[agent.act]} · ${agent.role.en}`, `Acte ${ACT_NUMERAL[agent.act]} · ${agent.role.fr}`)
                : t('The Theatre', 'Le Théâtre'))}
          </p>

          <AnimatePresence mode="wait">
            <motion.h2
              key={(agent?.id || 'stage') + state}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
              className="mt-2 font-serif italic text-3xl md:text-4xl text-bone leading-tight"
            >
              {agent
                ? t(agent.name.en, agent.name.fr)
                : t('Curtain rising', 'Le rideau se lève')}
            </motion.h2>
          </AnimatePresence>

          <p className="mt-2 font-mono text-[12px] text-bone-3 leading-relaxed max-w-xl">
            {agent
              ? t(agent.tagline.en, agent.tagline.fr)
              : t(
                  'The ensemble is taking the stage.',
                  'L’ensemble entre en scène.',
                )}
          </p>

          {currentTask && (
            <AnimatePresence mode="wait">
              <motion.p
                key={currentTask}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4 }}
                className="mt-4 font-serif italic text-[16px] text-bone-2 max-w-2xl border-l-2 border-bone/15 pl-4"
              >
                « {currentTask} »
              </motion.p>
            </AnimatePresence>
          )}

          <div className="mt-5 flex items-center gap-3 font-mono text-[10px] tracking-eyebrow uppercase">
            {isActive && (
              <span className={`inline-flex items-center gap-2 ${ACCENT_TEXT[tone]}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${ACCENT_DOT[tone]}`} />
                {t('In performance', 'En représentation')}
              </span>
            )}
            {isWaiting && (
              <span className="inline-flex items-center gap-2 text-warning">
                <span className="w-1.5 h-1.5 rounded-full bg-warning" />
                {t('Waiting on you', 'En attente de vous')}
              </span>
            )}
            {isCompleted && (
              <span className="inline-flex items-center gap-2 text-sage">
                <span className="w-1.5 h-1.5 rounded-full bg-sage" />
                {t('Curtain call', 'Saluts')}
              </span>
            )}
            {isFailed && (
              <span className="inline-flex items-center gap-2 text-error">
                <span className="w-1.5 h-1.5 rounded-full bg-error" />
                {t('Performance interrupted', 'Représentation interrompue')}
              </span>
            )}
            {!isActive && !isWaiting && !isCompleted && !isFailed && (
              <span className="inline-flex items-center gap-2 text-bone-4">
                <span className="w-1.5 h-1.5 rounded-full bg-bone-4" />
                {t('Backstage', 'En coulisses')}
              </span>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
