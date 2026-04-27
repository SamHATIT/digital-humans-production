import { useLang } from '../../contexts/LangContext';
import { auth } from '../../services/api';

export default function StudioFooter() {
  const { t } = useLang();

  return (
    <footer className="mt-24 border-t border-bone/5 bg-ink">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
          <div className="space-y-2">
            <p className="text-bone-3">© MMXXVI Samhatit Consulting</p>
            <p>Autonomous Studio · Est MMXXV</p>
          </div>

          <div className="space-y-2">
            <p>{t('Crafted in Paris · Hosted in Europe', 'Conçu à Paris · Hébergé en Europe')}</p>
            <p>{t('All works performed by digital agents', 'Toutes les œuvres réalisées par des agents numériques')}</p>
          </div>

          <div className="space-y-2 md:text-right">
            <a
              href="/preview"
              className="block text-bone-3 hover:text-brass transition-colors"
            >
              {t('Marketing preview', 'Aperçu marketing')}
            </a>
            <a
              href="/pricing"
              className="block text-bone-3 hover:text-brass transition-colors"
            >
              {t('Pricing', 'Tarifs')}
            </a>
            <button
              type="button"
              onClick={() => auth.logout()}
              className="block ml-auto text-bone-3 hover:text-brass transition-colors"
            >
              {t('Sign out', 'Déconnexion')}
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
}
