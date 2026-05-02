/**
 * BillingCancel - Mod 24
 * Page d\'atterrissage si l\'utilisateur annule le checkout Stripe.
 * Stripe redirige ici sans session_id si l\'utilisateur ferme l\'onglet ou
 * clique le bouton "Back" du formulaire de paiement.
 *
 * Aucun changement DB n\'est attendu : Stripe ne cree la subscription que
 * quand le paiement est confirme. Donc on se contente d\'un message "no
 * harm done" et d\'un retour vers /pricing.
 */
import { Link } from 'react-router-dom';
import { useLang } from '../contexts/LangContext';

export default function BillingCancel() {
  const { t } = useLang();

  return (
    <div className="bg-ink text-bone min-h-[70vh] flex items-center">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-4">
          № 09.3 · {t('No worries', 'Aucun souci')}
        </p>
        <h1 className="font-serif italic text-5xl md:text-6xl text-bone mb-6 leading-[1.05]">
          {t('The curtain stays drawn.', 'Le rideau reste baisse.')}
        </h1>
        <p className="max-w-xl mx-auto font-mono text-[13px] leading-relaxed text-bone-3 mb-8">
          {t(
            'You haven\'t been charged. Take your time — the studio is here when you\'re ready.',
            'Aucun debit n\'a ete effectue. Prenez votre temps — le studio sera la quand vous serez pret.',
          )}
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link
            to="/pricing"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-brass text-ink font-mono text-[11px] tracking-cta uppercase hover:bg-brass-2 transition-colors"
          >
            {t('Back to pricing', 'Retour aux tarifs')}
            <span aria-hidden="true">&larr;</span>
          </Link>
          <Link
            to="/"
            className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3 hover:text-brass transition-colors"
          >
            {t('Or enter the studio', 'Ou entrer dans le studio')}
          </Link>
        </div>
      </div>
    </div>
  );
}
