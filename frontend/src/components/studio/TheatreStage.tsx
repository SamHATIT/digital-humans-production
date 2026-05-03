/**
 * TheatreStage — STUDIO-S4.1
 *
 * Sidebar gauche du monitor d'execution. Implémente la cinématique
 * "Théâtre" choisie par Sam (mockup /mockups-o3/02-theatre.html) :
 * agents organisés par acte sur des planches de scène, avec rideau en
 * haut, footlight en bas, et spotlight (halo brass + scale-up + photo
 * couleur) sur l'agent actif. Les agents en attente sont muets
 * (grayscale + opacité réduite), les agents qui ont fini retombent dans
 * un état "down lit" (gris-doré, opacité moyenne).
 *
 * Remplace visuellement StudioTimeline pour le côté narratif. La timeline
 * "score / partition" reste disponible si on veut la rapatrier ailleurs.
 *
 * Couvre aussi BUILD-AGENT-AVATARS : les avatars affichés sont les
 * portraits Studio canoniques (`/avatars/large/{slug}.png`), pas une
 * autre source qui défile.
 */
import { motion } from 'framer-motion';
import { useLang } from '../../contexts/LangContext';
import {
  groupByAct,
  type AccentToken,
  type StudioAgent,
} from '../../lib/agents';
import type { StepStatus } from './StudioTimeline';

interface TheatreStageProps {
  /** Map agent.id → status. The page derives this from the orchestrator's
   *  agent_progress array. Agents not in the map default to 'pending'. */
  statusByAgent: Record<string, StepStatus>;
  /** ID of the currently-active agent (gets the spotlight). */
  activeAgentId: string | null;
  /** Optional onClick (e.g. to scroll the right pane to that agent). */
  onSelect?: (agent: StudioAgent) => void;
}

const ACT_LABELS: Record<string, { en: string; fr: string }> = {
  I: { en: 'The Brief', fr: 'Le Brief' },
  II: { en: 'Use Cases · Coverage · Architecture', fr: 'Cas d\u2019usage · Couverture · Architecture' },
  III: { en: 'Validation', fr: 'Validation' },
  IV: { en: 'Expert Specs', fr: 'Cahiers des experts' },
  V: { en: 'Build · Stand-by', fr: 'Build · En attente' },
};

const ACCENT_RING: Record<AccentToken, string> = {
  indigo: 'shadow-[0_0_0_2px_var(--ink),0_0_24px_rgba(110,125,184,0.55),0_-8px_20px_rgba(245,242,236,0.18)]',
  plum: 'shadow-[0_0_0_2px_var(--ink),0_0_24px_rgba(155,110,148,0.55),0_-8px_20px_rgba(245,242,236,0.18)]',
  terra: 'shadow-[0_0_0_2px_var(--ink),0_0_24px_rgba(197,127,92,0.55),0_-8px_20px_rgba(245,242,236,0.18)]',
  sage: 'shadow-[0_0_0_2px_var(--ink),0_0_24px_rgba(122,148,116,0.55),0_-8px_20px_rgba(245,242,236,0.18)]',
  ochre: 'shadow-[0_0_0_2px_var(--ink),0_0_24px_rgba(184,139,63,0.55),0_-8px_20px_rgba(245,242,236,0.18)]',
  brass: 'shadow-[0_0_0_2px_var(--ink),0_0_24px_rgba(200,169,126,0.55),0_-8px_20px_rgba(245,242,236,0.18)]',
};

const ACCENT_BORDER: Record<AccentToken, string> = {
  indigo: 'border-indigo',
  plum: 'border-plum',
  terra: 'border-terra',
  sage: 'border-sage',
  ochre: 'border-ochre',
  brass: 'border-brass',
};

/**
 * One agent on the stage. Three visual variants based on status:
 * - active: spotlight halo, full color, lifted, scaled up, italic name
 * - completed: dim color, no halo, name in muted bone
 * - pending/waiting/failed: grayscale + low opacity ('off-stage')
 */
function Actor({
  agent,
  status,
  isActive,
  lang,
  onSelect,
}: {
  agent: StudioAgent;
  status: StepStatus;
  isActive: boolean;
  lang: 'en' | 'fr';
  onSelect?: (agent: StudioAgent) => void;
}) {
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';
  const isHitl = status === 'waiting_hitl';

  const photoClass = isActive
    ? `${ACCENT_BORDER[agent.accent]} ${ACCENT_RING[agent.accent]} -translate-y-1 scale-105 brightness-110`
    : isCompleted
    ? 'border-bone/15 grayscale-[0.4] opacity-70'
    : isFailed
    ? 'border-error/40 grayscale opacity-60'
    : 'border-bone/10 grayscale-[0.7] brightness-75 opacity-70';

  const nameClass = isActive
    ? 'text-bone italic'
    : isCompleted
    ? 'text-bone-3'
    : 'text-bone-4';

  return (
    <button
      type="button"
      onClick={() => onSelect?.(agent)}
      className="flex flex-col items-center gap-1 group min-w-0 transition-transform"
      title={agent.role[lang]}
    >
      <div
        className={[
          'relative w-12 h-12 rounded-full overflow-hidden border-[1.5px] transition-all duration-300',
          photoClass,
        ].join(' ')}
      >
        <img
          src={`/avatars/large/${agent.slug}.png`}
          alt={agent.name[lang]}
          className="w-full h-full object-cover"
        />
        {isActive && (
          /* Pulsing aura on top of the photo */
          <motion.span
            aria-hidden
            className="pointer-events-none absolute inset-0 rounded-full"
            style={{
              boxShadow: '0 0 18px 2px rgba(245,242,236,0.18) inset',
            }}
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}
        {isHitl && (
          <span className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-warning border-2 border-ink" />
        )}
        {isCompleted && (
          <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-sage border-2 border-ink flex items-center justify-center text-[8px] text-ink font-bold">
            ✓
          </span>
        )}
      </div>
      <span
        className={[
          'font-serif text-[0.78rem] leading-tight transition-colors',
          nameClass,
        ].join(' ')}
      >
        {agent.name[lang]}
      </span>
    </button>
  );
}

export default function TheatreStage({
  statusByAgent,
  activeAgentId,
  onSelect,
}: TheatreStageProps) {
  const { t, lang } = useLang();
  const acts = groupByAct().filter((g) => g.agents.length > 0);

  return (
    <nav
      aria-label={t('Theatre stage', 'Scène du théâtre')}
      className="bg-ink-2 border border-bone/10 overflow-hidden"
    >
      {/* Curtain — top frieze */}
      <div className="relative h-9 border-b border-rim-brass">
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(180deg, rgba(184,139,63,0.35) 0%, rgba(184,139,63,0.08) 70%, transparent 100%)',
          }}
        />
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            backgroundImage:
              'repeating-linear-gradient(90deg, transparent 0 18px, rgba(10,10,11,0.4) 18px 19px)',
          }}
        />
        <p className="relative z-10 text-center pt-1.5 font-serif italic text-[0.85rem] text-brass">
          {t('The studio', 'Le studio')}
        </p>
      </div>

      <div className="px-3 py-4 space-y-5">
        {acts.map((group) => (
          <div key={group.act} className="relative">
            <div className="flex items-baseline gap-2 px-1">
              <span className="font-serif italic text-[1.2rem] text-brass leading-none">
                {group.act}
              </span>
              <span className="font-mono text-[0.55rem] tracking-eyebrow uppercase text-bone-3">
                — {t(ACT_LABELS[group.act].en, ACT_LABELS[group.act].fr)}
              </span>
            </div>

            {/* Stage row — agents standing on the boards */}
            <div
              className="mt-2 flex flex-wrap gap-2 items-end justify-around px-1.5 py-2.5 relative"
              style={{
                background:
                  'linear-gradient(180deg, rgba(245,242,236,0.02) 0%, transparent 70%)',
                borderBottom: '1px solid rgba(200,169,126,0.18)',
              }}
            >
              {group.agents.map((agent) => {
                const status = statusByAgent[agent.id] ?? 'pending';
                const isActive = activeAgentId === agent.id;
                return (
                  <Actor
                    key={agent.id}
                    agent={agent}
                    status={status}
                    isActive={isActive}
                    lang={lang}
                    onSelect={onSelect}
                  />
                );
              })}
              {/* Stage floor shadow */}
              <span
                aria-hidden
                className="absolute left-[10%] right-[10%] -bottom-[2px] h-[3px]"
                style={{
                  background:
                    'radial-gradient(ellipse at center, rgba(0,0,0,0.7) 0%, transparent 80%)',
                  filter: 'blur(2px)',
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Footlights */}
      <div
        aria-hidden
        className="h-[3px] mt-1"
        style={{
          background:
            'linear-gradient(90deg, transparent, rgba(200,169,126,0.55) 50%, transparent)',
        }}
      />
    </nav>
  );
}
