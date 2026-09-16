import { Sparkles } from 'lucide-react';
import { useLang } from '../contexts/LangContext';
import { aiChatDisclosure } from '../lib/aiDisclosure';

/**
 * Bandeau « vous échangez avec une IA » — AI Act art. 50 (GL-19).
 *
 * Affiché en tête de chaque fenêtre de dialogue du Studio, donc visible au
 * premier contact et pendant toute la conversation. Un bandeau qui
 * disparaîtrait après le premier message laisserait une conversation longue
 * sans mention : l'obligation porte sur l'information de l'utilisateur, pas
 * sur un seul instant.
 *
 * `data-testid` est là pour que le contrôle Chromium puisse l'asserter sans
 * dépendre du texte traduit.
 */
export default function AiDisclosureBanner({ className = '' }: { className?: string }) {
  const { lang } = useLang();

  return (
    <p
      data-testid="ai-disclosure"
      role="note"
      className={[
        'flex items-start gap-2 border-b border-brass/20 bg-brass/5 px-4 py-2',
        'font-mono text-[10px] leading-relaxed tracking-[0.04em] text-bone-3',
        className,
      ].join(' ')}
    >
      <Sparkles className="mt-[1px] h-3 w-3 shrink-0 text-brass" aria-hidden="true" />
      <span>{aiChatDisclosure(lang)}</span>
    </p>
  );
}
