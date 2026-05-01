import { motion } from 'framer-motion';
import { useLang } from '../../contexts/LangContext';
import {
  STUDIO_ENSEMBLE,
  ACT_LABELS,
  groupByAct,
  type AgentAccent,
} from '../../lib/agents';

const ACCENT_BORDER: Record<AgentAccent, string> = {
  indigo: 'border-indigo/50',
  plum: 'border-plum/50',
  terra: 'border-terra/50',
  sage: 'border-sage/50',
  ochre: 'border-ochre/50',
};

const ACCENT_TEXT: Record<AgentAccent, string> = {
  indigo: 'text-indigo',
  plum: 'text-plum',
  terra: 'text-terra',
  sage: 'text-sage',
  ochre: 'text-ochre',
};

/**
 * Lecture seule — le wizard ne permet pas de modifier la distribution.
 * Affiche les 11 agents groupés par acte, photos `/avatars/large/`.
 */
export default function EnsembleDisplay() {
  const { t, lang } = useLang();
  const groups = groupByAct();

  return (
    <div className="space-y-10">
      <p className="font-mono text-[12px] text-bone-3 leading-relaxed max-w-2xl">
        {t(
          'These eleven specialists will compose your Salesforce solution. Each acts in turn ; their work is your project.',
          'Onze spécialistes composeront votre solution Salesforce. Chacun joue son tour ; leur ouvrage est votre projet.',
        )}
      </p>

      {groups.map(({ act, agents }) => (
        <section key={act}>
          <header className="mb-4 flex items-baseline justify-between border-b border-bone/5 pb-2">
            <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
              {t(ACT_LABELS[act].en, ACT_LABELS[act].fr)}
            </p>
            <p className="font-mono text-[10px] text-bone-4">
              {agents.length}{' '}
              {agents.length === 1
                ? t('agent', 'agent')
                : t('agents', 'agents')}
            </p>
          </header>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent, idx) => (
              <motion.article
                key={agent.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.32, delay: idx * 0.04, ease: 'easeOut' }}
                className={`flex items-start gap-3 border ${ACCENT_BORDER[agent.accent]} bg-ink-2 p-3`}
              >
                <img
                  src={`/avatars/small/${agent.slug}.png`}
                  alt={agent.name[lang === 'fr' ? 'fr' : 'en']}
                  className="w-12 h-12 object-cover border border-bone/10 shrink-0"
                  loading="lazy"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                  }}
                />
                <div className="min-w-0">
                  <p
                    className={`font-mono text-[10px] tracking-eyebrow uppercase ${ACCENT_TEXT[agent.accent]}`}
                  >
                    {t(agent.role.en, agent.role.fr)}
                  </p>
                  <h3 className="mt-1 font-serif italic text-lg text-bone leading-tight">
                    {t(agent.name.en, agent.name.fr)}
                  </h3>
                  <p className="mt-1 font-mono text-[11px] text-bone-3 leading-snug">
                    {t(agent.tagline.en, agent.tagline.fr)}
                  </p>
                </div>
              </motion.article>
            ))}
          </div>
        </section>
      ))}

      <p className="text-right">
        <a
          href="/preview"
          className="inline-block font-mono text-[11px] tracking-cta uppercase text-brass hover:text-brass-2"
        >
          {t('Read about the ensemble →', "En savoir plus sur l'ensemble →")}
        </a>
      </p>

      <p className="sr-only">{`Ensemble: ${STUDIO_ENSEMBLE.length} agents.`}</p>
    </div>
  );
}
