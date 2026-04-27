/**
 * StudioHeaderPublic — variante du StudioHeader sans CreditCounter,
 * sans avatar/logout, avec CTAs Sign in / Pricing à droite.
 * Pour les pages publiques (Pricing notamment).
 */
import { Link } from 'react-router-dom';
import { useLang } from '../../contexts/LangContext';
import LangToggle from './LangToggle';

export default function StudioHeaderPublic() {
  const { t } = useLang();

  return (
    <header className="sticky top-0 z-40 bg-ink-2/95 backdrop-blur-md border-b border-brass/20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-6">
          {/* Logo */}
          <Link to="/" className="flex flex-col leading-tight group">
            <span className="font-serif italic text-xl text-bone group-hover:text-brass transition-colors">
              Digital · Humans
            </span>
            <span className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
              Autonomous Studio · Est MMXXV
            </span>
          </Link>

          {/* Right side */}
          <div className="flex items-center gap-4">
            <LangToggle />
            <Link
              to="/pricing"
              className="hidden md:inline font-mono text-[11px] tracking-eyebrow uppercase text-bone-3 hover:text-bone transition-colors"
            >
              {t('Pricing', 'Tarifs')}
            </Link>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 px-4 py-2 bg-brass text-ink font-mono text-[11px] tracking-cta uppercase hover:bg-brass-2 transition-colors"
            >
              {t('Sign in', 'Se connecter')}
              <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
}
