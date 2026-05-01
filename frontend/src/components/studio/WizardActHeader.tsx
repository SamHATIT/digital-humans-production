import type { ReactNode } from 'react';
import { motion } from 'framer-motion';

interface WizardActHeaderProps {
  /** Romain affichée en eyebrow. */
  eyebrow: string;
  title: ReactNode;
  lede?: ReactNode;
}

export default function WizardActHeader({ eyebrow, title, lede }: WizardActHeaderProps) {
  return (
    <motion.header
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: 'easeOut' }}
      className="mb-10 max-w-2xl"
    >
      <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
        {eyebrow}
      </p>
      <h1 className="mt-3 font-serif italic text-[42px] md:text-[48px] leading-tight text-bone">
        {title}
      </h1>
      {lede && (
        <p className="mt-4 font-mono text-[12px] tracking-[0.04em] text-bone-3 leading-relaxed">
          {lede}
        </p>
      )}
    </motion.header>
  );
}
