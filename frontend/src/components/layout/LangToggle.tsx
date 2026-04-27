import { useLang } from '../../contexts/LangContext';

interface LangToggleProps {
  className?: string;
}

export default function LangToggle({ className = '' }: LangToggleProps) {
  const { lang, setLang } = useLang();

  const baseBtn =
    'px-2 py-1 font-mono text-[11px] tracking-eyebrow uppercase transition-colors';

  return (
    <div
      role="group"
      aria-label="Language toggle"
      className={`inline-flex items-center gap-1 border border-bone/10 ${className}`}
    >
      <button
        type="button"
        aria-pressed={lang === 'en'}
        onClick={() => setLang('en')}
        className={`${baseBtn} ${
          lang === 'en' ? 'bg-brass text-ink' : 'text-bone-3 hover:text-bone'
        }`}
      >
        EN
      </button>
      <button
        type="button"
        aria-pressed={lang === 'fr'}
        onClick={() => setLang('fr')}
        className={`${baseBtn} ${
          lang === 'fr' ? 'bg-brass text-ink' : 'text-bone-3 hover:text-bone'
        }`}
      >
        FR
      </button>
    </div>
  );
}
