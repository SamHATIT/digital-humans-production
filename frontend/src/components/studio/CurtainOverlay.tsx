import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLang } from '../../contexts/LangContext';

interface CurtainOverlayProps {
  /** Stable identifier — used to gate the animation in sessionStorage. */
  storageKey: string;
  /** Eyebrow line printed atop the title (e.g. "№ 04 · Curtain Up"). */
  eyebrow?: string;
  /** Main title (will be wrapped in italic serif). */
  title?: { en: string; fr: string };
}

/**
 * Plays once per session per execution: a deep ink curtain rises from the
 * bottom (1s ease-out), then fades. Gated by sessionStorage to prevent
 * replays on poll-driven re-renders or Studio navigation.
 */
export default function CurtainOverlay({
  storageKey,
  eyebrow,
  title,
}: CurtainOverlayProps) {
  const { t } = useLang();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const seen = window.sessionStorage.getItem(`curtain-seen-${storageKey}`);
    if (seen) return;
    setVisible(true);
    const id = window.setTimeout(() => {
      setVisible(false);
      window.sessionStorage.setItem(`curtain-seen-${storageKey}`, 'true');
    }, 1400);
    return () => window.clearTimeout(id);
  }, [storageKey]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          aria-hidden
          initial={{ y: 0 }}
          animate={{ y: 0 }}
          exit={{ y: '-100%' }}
          transition={{ duration: 1.0, ease: [0.22, 0.61, 0.36, 1] }}
          className="fixed inset-0 z-[80] bg-gradient-to-b from-ink to-ink-2 flex items-center justify-center"
        >
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5, delay: 0.2, ease: 'easeOut' }}
            className="text-center px-6"
          >
            <p className="font-mono text-[11px] tracking-eyebrow uppercase text-brass">
              {eyebrow ?? t('No 04 · Curtain Up', 'Nº 04 · Le rideau se lève')}
            </p>
            <h1 className="mt-3 font-serif italic text-bone text-3xl md:text-5xl leading-tight">
              {title
                ? t(title.en, title.fr)
                : t('The ensemble takes the stage', 'L’ensemble entre en scène')}
            </h1>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
