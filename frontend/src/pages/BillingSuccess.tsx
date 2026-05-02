/**
 * BillingSuccess — Mod 24
 * Page d\'atterrissage post-paiement Stripe Checkout.
 * Stripe ajoute ?session_id={CHECKOUT_SESSION_ID} a l\'URL.
 *
 * Le webhook backend a deja mis a jour user.subscription_tier a ce stade
 * (event customer.subscription.created), donc on se contente d\'afficher
 * un message de bienvenue et de proposer d\'entrer dans le studio.
 */
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useLang } from '../contexts/LangContext';

export default function BillingSuccess() {
  const { t } = useLang();
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('session_id');
  const [tier, setTier] = useState<string>('');

  useEffect(() => {
    // Optionnel : confirmer le tier en cours via /api/billing/balance.
    // Le webhook a normalement deja fait son boulot, mais on rafraichit l\'UI.
    const token = localStorage.getItem('token');
    if (!token) return;
    fetch('/api/billing/balance', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.tier) setTier(data.tier);
      })
      .catch(() => {
        /* silent */
      });
  }, []);

  return (
    <div className="bg-ink text-bone min-h-[70vh] flex items-center">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-4">
          № 09.2 · {t('Subscription confirmed', 'Abonnement confirme')}
        </p>
        <h1 className="font-serif italic text-5xl md:text-6xl text-bone mb-6 leading-[1.05]">
          {t('Welcome to the studio.', 'Bienvenue dans le studio.')}
        </h1>
        <p className="max-w-xl mx-auto font-mono text-[13px] leading-relaxed text-bone-3 mb-8">
          {tier
            ? t(
                `Your ${tier} plan is live. The full cast is at your disposal.`,
                `Votre plan ${tier} est actif. Toute la distribution est a votre disposition.`,
              )
            : t(
                'Your subscription is being activated. The full cast will be at your disposal in a moment.',
                'Votre abonnement est en cours d\'activation. Toute la distribution sera a votre disposition dans un instant.',
              )}
        </p>
        <Link
          to="/"
          className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-brass text-ink font-mono text-[11px] tracking-cta uppercase hover:bg-brass-2 transition-colors"
        >
          {t('Enter the studio', 'Entrer dans le studio')}
          <span aria-hidden="true">&rarr;</span>
        </Link>
        {sessionId && (
          <p className="font-mono text-[10px] text-bone-4 mt-8">
            {t('Reference', 'Reference')} : {sessionId.slice(0, 24)}…
          </p>
        )}
      </div>
    </div>
  );
}
