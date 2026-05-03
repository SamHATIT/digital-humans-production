/**
 * Pricing — A5.4
 * Refonte commerciale + visuelle Studio :
 *   Free / Pro (49€/mo) / Team (1490€/mo) / Enterprise (devis)
 * Page publique (pas de ProtectedRoute), accessible avec un AppShell variant="public".
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, X } from 'lucide-react';
import { useLang } from '../contexts/LangContext';

type Tier = 'free' | 'pro' | 'team' | 'enterprise';

interface Feature {
  group: { en: string; fr: string };
  label: { en: string; fr: string };
  values: Record<Tier, boolean | string>;
}

const FEATURES: Feature[] = [
  // SDS Phase
  { group: { en: 'SDS Phase', fr: 'Phase SDS' }, label: { en: 'Business Requirements extraction', fr: 'Extraction des Business Requirements' }, values: { free: true, pro: true, team: true, enterprise: true } },
  { group: { en: 'SDS Phase', fr: 'Phase SDS' }, label: { en: 'Use Cases generation', fr: 'Génération des Use Cases' }, values: { free: true, pro: true, team: true, enterprise: true } },
  { group: { en: 'SDS Phase', fr: 'Phase SDS' }, label: { en: 'Solution Design', fr: 'Solution Design' }, values: { free: true, pro: true, team: true, enterprise: true } },
  { group: { en: 'SDS Phase', fr: 'Phase SDS' }, label: { en: 'SDS Document (Word / PDF)', fr: 'Document SDS (Word / PDF)' }, values: { free: true, pro: true, team: true, enterprise: true } },
  { group: { en: 'SDS Phase', fr: 'Phase SDS' }, label: { en: 'Max BRs per project', fr: 'BRs max par projet' }, values: { free: '30', pro: '100', team: 'Unlimited', enterprise: 'Unlimited' } },
  { group: { en: 'SDS Phase', fr: 'Phase SDS' }, label: { en: 'Max projects', fr: 'Projets max' }, values: { free: '1', pro: '5', team: 'Unlimited', enterprise: 'Unlimited' } },
  // BUILD Phase
  { group: { en: 'BUILD Phase', fr: 'Phase BUILD' }, label: { en: 'BUILD Phase (code generation)', fr: 'Phase BUILD (génération de code)' }, values: { free: false, pro: true, team: true, enterprise: true } },
  { group: { en: 'BUILD Phase', fr: 'Phase BUILD' }, label: { en: 'SFDX Deployment', fr: 'Déploiement SFDX' }, values: { free: false, pro: true, team: true, enterprise: true } },
  { group: { en: 'BUILD Phase', fr: 'Phase BUILD' }, label: { en: 'Git integration', fr: 'Intégration Git' }, values: { free: false, pro: true, team: true, enterprise: true } },
  { group: { en: 'BUILD Phase', fr: 'Phase BUILD' }, label: { en: 'Multi-environments', fr: 'Multi-environnements' }, values: { free: false, pro: false, team: true, enterprise: true } },
  // Advanced
  { group: { en: 'Advanced', fr: 'Avancé' }, label: { en: 'Custom templates', fr: 'Templates personnalisés' }, values: { free: false, pro: false, team: true, enterprise: true } },
  { group: { en: 'Advanced', fr: 'Avancé' }, label: { en: 'Priority support', fr: 'Support prioritaire' }, values: { free: false, pro: true, team: true, enterprise: true } },
  { group: { en: 'Advanced', fr: 'Avancé' }, label: { en: 'Zero data retention', fr: 'Zero data retention' }, values: { free: true, pro: false, team: false, enterprise: true } },
  { group: { en: 'Advanced', fr: 'Avancé' }, label: { en: 'On-premise deployment', fr: 'Déploiement on-premise' }, values: { free: false, pro: false, team: false, enterprise: true } },
  { group: { en: 'Advanced', fr: 'Avancé' }, label: { en: 'SLA + dedicated support', fr: 'SLA + support dédié', }, values: { free: false, pro: false, team: false, enterprise: true } },
];

interface TierCardData {
  id: Tier;
  name: string;
  tagline: { en: string; fr: string };
  price: { en: string; fr: string };
  unit: { en: string; fr: string } | null;
  credits: { en: string; fr: string };
  projects: { en: string; fr: string };
  scope: { en: string; fr: string };
  cta: { en: string; fr: string };
  highlight?: boolean;
}

const TIERS: TierCardData[] = [
  {
    id: 'free',
    name: 'Free',
    tagline: { en: 'Try the Studio', fr: 'Découvrir le Studio' },
    price: { en: '0€', fr: '0€' },
    unit: null,
    credits: { en: '500 credits / mo', fr: '500 crédits / mois' },
    projects: { en: '1 project · SDS only', fr: '1 projet · SDS uniquement' },
    scope: { en: 'Zero data retention', fr: 'Zero data retention' },
    cta: { en: 'Sign up free', fr: 'Créer un compte' },
  },
  {
    id: 'pro',
    name: 'Pro',
    tagline: { en: 'For consultants & freelance admins', fr: 'Pour consultants & admins freelance' },
    price: { en: '49€', fr: '49€' },
    unit: { en: '/ month', fr: '/ mois' },
    credits: { en: '5 000 credits / mo', fr: '5 000 crédits / mois' },
    projects: { en: '5 projects · SDS + BUILD', fr: '5 projets · SDS + BUILD' },
    scope: { en: 'Git, SFDX, priority support', fr: 'Git, SFDX, support prioritaire' },
    cta: { en: 'Subscribe', fr: "S'abonner" },
    highlight: true,
  },
  {
    id: 'team',
    name: 'Team',
    tagline: { en: 'For agencies & in-house teams', fr: 'Pour agences & équipes internes' },
    price: { en: '1 490€', fr: '1 490€' },
    unit: { en: '/ month', fr: '/ mois' },
    credits: { en: '50 000 credits / mo', fr: '50 000 crédits / mois' },
    projects: { en: 'Unlimited · multi-env', fr: 'Illimités · multi-env' },
    scope: { en: 'Custom templates, shared workspaces', fr: 'Templates personnalisés, workspaces partagés' },
    cta: { en: 'Talk to us', fr: 'Nous contacter' },
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    tagline: { en: 'For large organisations', fr: 'Pour grandes organisations' },
    price: { en: 'On request', fr: 'Sur devis' },
    unit: null,
    credits: { en: 'Unlimited', fr: 'Illimité' },
    projects: { en: 'Unlimited · on-premise', fr: 'Illimités · on-premise' },
    scope: { en: 'SLA, dedicated support, ZDR', fr: 'SLA, support dédié, ZDR' },
    cta: { en: 'Talk to us', fr: 'Nous contacter' },
  },
];

const FAQ = [
  {
    q: { en: 'How are credits counted?', fr: 'Comment les crédits sont-ils comptés ?' },
    a: {
      en: 'Each agent invocation consumes credits proportional to the LLM tokens used. A typical SDS run costs ~ 800 credits, a typical BUILD ~ 3 500 credits.',
      fr: 'Chaque invocation d\'agent consomme des crédits proportionnels aux tokens LLM utilisés. Un SDS coûte généralement ~ 800 crédits, un BUILD ~ 3 500 crédits.',
    },
  },
  {
    q: { en: 'Can I change plan at any time?', fr: 'Puis-je changer de plan à tout moment ?' },
    a: {
      en: 'Yes. Upgrades take effect immediately, downgrades at the end of the current billing period.',
      fr: 'Oui. Les passages au tier supérieur sont immédiats ; les rétrogradations prennent effet à la fin de la période en cours.',
    },
  },
  {
    q: { en: 'Where does my data go?', fr: 'Où vont mes données ?' },
    a: {
      en: 'Free and Enterprise tiers operate in zero-data-retention mode by default. Pro and Team store your projects and deliverables on EU-hosted infrastructure.',
      fr: 'Les plans Free et Enterprise opèrent par défaut en zero data retention. Pro et Team stockent vos projets et livrables sur infrastructure UE.',
    },
  },
];

const ENTERPRISE_EMAIL = '[email protected]';

function FeatureValue({ value }: { value: boolean | string }) {
  if (typeof value === 'string') {
    return (
      <span className="font-mono text-[12px] text-bone-2 tabular-nums">{value}</span>
    );
  }
  return value ? (
    <Check className="w-4 h-4 text-brass mx-auto" aria-label="included" />
  ) : (
    <X className="w-4 h-4 text-bone-4 mx-auto" aria-label="not included" />
  );
}

/**
 * Mod 24 — Helper pret a brancher pour declencher un checkout Stripe.
 *
 * Etat actuel : NON BRANCHE. Le bouton Pro ouvre toujours un modal "Bientot",
 * Team / Enterprise ouvrent un mailto. Quand l\'ouverture publique de Pro/Team
 * est decidee, il suffira de remplacer dans handleCta :
 *   - `setShowProModal(true)` par `startStripeCheckout(\'pro\')`
 *   - le mailto Team par `startStripeCheckout(\'team\')`
 *
 * Le backend `POST /api/billing/checkout` :
 *   - exige un Bearer token (utilisateur doit etre logge)
 *   - retourne `{url}` = URL Stripe Checkout hosted
 *   - redirige vers `/billing/success` ou `/billing/cancel` apres paiement
 *
 * Si pas de token : redirige vers /signup (l\'utilisateur sera reoriente
 * vers le checkout apres signup, a implementer dans SignupPage si besoin).
 */
async function startStripeCheckout(tier: 'pro' | 'team'): Promise<void> {
  const token = localStorage.getItem('token');
  if (!token) {
    // Pas logge → on envoie vers signup, le checkout reprendra apres login
    sessionStorage.setItem('post_signup_checkout_tier', tier);
    window.location.href = '/signup';
    return;
  }

  try {
    const res = await fetch('/api/billing/checkout', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ tier }),
    });

    if (!res.ok) {
      const detail = await res.text().catch(() => '');
      console.error('[Stripe checkout] HTTP', res.status, detail);
      alert('Le checkout Stripe est indisponible. Reessayez dans un instant ou contactez-nous.');
      return;
    }

    const { url } = await res.json();
    if (!url) {
      console.error('[Stripe checkout] reponse sans url');
      return;
    }
    window.location.href = url;
  } catch (err) {
    console.error('[Stripe checkout] erreur reseau', err);
    alert('Le checkout Stripe est indisponible. Reessayez dans un instant ou contactez-nous.');
  }
}

export default function Pricing() {
  const { t, lang } = useLang();
  const [showProModal, setShowProModal] = useState(false);

  const handleCta = (tier: Tier) => {
    if (tier === 'free') {
      // ONBOARDING-001: Free tier is self-serve — go straight to /signup
      // and pre-select Free in the SignupPage hero so the user knows what
      // they're getting (and so /register sets subscription_tier='free').
      window.location.href = '/signup?tier=free';
    } else if (tier === 'pro') {
      // Mod 24 : pour activer le checkout Stripe, remplacer la ligne suivante par :
      //   startStripeCheckout('pro');
      setShowProModal(true);
    } else {
      // Mod 24 : pour activer le checkout Stripe sur Team, remplacer ce bloc par :
      //   if (tier === 'team') { startStripeCheckout('team'); return; }
      // Pour Enterprise on garde toujours le mailto (on-premise, pas de Stripe).
      const subject = encodeURIComponent(
        tier === 'team' ? 'Team plan inquiry' : 'Enterprise plan inquiry',
      );
      window.location.href = `mailto:${ENTERPRISE_EMAIL}?subject=${subject}`;
    }
  };

  // Group features by group label
  const groups = FEATURES.reduce<Record<string, Feature[]>>((acc, f) => {
    const key = lang === 'fr' ? f.group.fr : f.group.en;
    (acc[key] ||= []).push(f);
    return acc;
  }, {});

  return (
    <div className="bg-ink text-bone">
      {/* Hero */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-4">
          № 09 · {t('Pricing', 'Tarifs')}
        </p>
        <h1 className="font-serif italic text-5xl md:text-6xl text-bone mb-6 leading-[1.05]">
          {t('A studio for every scale.', 'Un studio à toute échelle.')}
        </h1>
        <p className="max-w-2xl font-mono text-[13px] leading-relaxed text-bone-3">
          {t(
            'From a single Salesforce admin to a full team — pick the cast that fits your studio.',
            'De l’admin Salesforce indépendant à l’équipe complète — choisissez la distribution adaptée à votre studio.',
          )}
        </p>
      </section>

      {/* Tier cards */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-20">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {TIERS.map((tier) => {
            const highlighted = !!tier.highlight;
            return (
              <div
                key={tier.id}
                className={`relative flex flex-col bg-ink-2 border ${
                  highlighted ? 'border-brass' : 'border-bone/10'
                } p-7`}
              >
                {highlighted && (
                  <span className="absolute -top-2.5 left-7 bg-brass text-ink font-mono text-[10px] tracking-eyebrow uppercase px-2 py-0.5">
                    {t('Popular', 'Populaire')}
                  </span>
                )}

                <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                  {tier.name}
                </p>
                <p className="font-mono text-[11px] text-bone-3 mt-1 mb-6 min-h-[36px]">
                  {t(tier.tagline.en, tier.tagline.fr)}
                </p>

                <div className="mb-6">
                  <span className="font-serif italic text-4xl text-bone">
                    {t(tier.price.en, tier.price.fr)}
                  </span>
                  {tier.unit && (
                    <span className="font-mono text-[11px] text-bone-4 ml-1">
                      {t(tier.unit.en, tier.unit.fr)}
                    </span>
                  )}
                </div>

                <ul className="space-y-2.5 mb-8 flex-1">
                  <li className="font-mono text-[11px] text-bone-2">
                    {t(tier.credits.en, tier.credits.fr)}
                  </li>
                  <li className="font-mono text-[11px] text-bone-3">
                    {t(tier.projects.en, tier.projects.fr)}
                  </li>
                  <li className="font-mono text-[11px] text-bone-3">
                    {t(tier.scope.en, tier.scope.fr)}
                  </li>
                </ul>

                <button
                  type="button"
                  onClick={() => handleCta(tier.id)}
                  className={`w-full inline-flex items-center justify-center gap-2 px-4 py-3 font-mono text-[11px] tracking-cta uppercase transition-colors ${
                    highlighted
                      ? 'bg-brass text-ink hover:bg-brass-2'
                      : 'bg-ink-3 text-bone border border-bone/10 hover:border-brass/40'
                  }`}
                >
                  {t(tier.cta.en, tier.cta.fr)}
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            );
          })}
        </div>
      </section>

      {/* Comparison table */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 border-t border-bone/10">
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-3">
          № 09.1 · {t('Compare', 'Comparer')}
        </p>
        <h2 className="font-serif italic text-3xl text-bone mb-10">
          {t('What each tier carries', 'Ce que porte chaque tier')}
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-bone/10">
                <th className="text-left py-3 pr-4 font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 font-normal">
                  {t('Feature', 'Fonctionnalité')}
                </th>
                {TIERS.map((tier) => (
                  <th
                    key={tier.id}
                    className="text-center py-3 px-3 font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 font-normal min-w-[110px]"
                  >
                    {tier.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(groups).map(([group, items]) => (
                <>
                  <tr key={`group-${group}`} className="border-b border-bone/5">
                    <td colSpan={5} className="pt-6 pb-2">
                      <p className="font-mono text-[10px] tracking-eyebrow uppercase text-brass">
                        {group}
                      </p>
                    </td>
                  </tr>
                  {items.map((feature, i) => (
                    <tr
                      key={`${group}-${i}`}
                      className="border-b border-bone/5 hover:bg-ink-2/40 transition-colors"
                    >
                      <td className="py-3 pr-4 font-mono text-[12px] text-bone-2">
                        {t(feature.label.en, feature.label.fr)}
                      </td>
                      {TIERS.map((tier) => (
                        <td key={tier.id} className="py-3 px-3 text-center">
                          <FeatureValue value={feature.values[tier.id]} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* FAQ */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16 border-t border-bone/10">
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-3">
          № 09.2 · {t('Questions', 'Questions')}
        </p>
        <h2 className="font-serif italic text-3xl text-bone mb-10">
          {t('Things people ask first', 'Ce que l’on nous demande en premier')}
        </h2>

        <div className="space-y-1">
          {FAQ.map((item, i) => (
            <details
              key={i}
              className="group border-b border-bone/10 py-5"
            >
              <summary className="cursor-pointer list-none flex items-center justify-between gap-6 font-mono text-[12px] tracking-eyebrow uppercase text-bone-2 hover:text-bone">
                <span>{t(item.q.en, item.q.fr)}</span>
                <span className="text-brass transition-transform group-open:rotate-45" aria-hidden="true">+</span>
              </summary>
              <p className="mt-4 font-mono text-[12px] leading-relaxed text-bone-3">
                {t(item.a.en, item.a.fr)}
              </p>
            </details>
          ))}
        </div>
      </section>

      {/* Final note */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center border-t border-bone/10">
        <p className="font-serif italic text-2xl text-bone-2 mb-2">
          {t('"The eleven agents perform — you direct."', '« Les onze agents jouent — vous mettez en scène. »')}
        </p>
        <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
          Samhatit Consulting · MMXXVI
        </p>
      </section>

      {/* Pro tier "Coming soon" modal */}
      {showProModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 backdrop-blur-sm p-4"
          onClick={() => setShowProModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-ink-2 border border-brass/30 max-w-md w-full p-8 relative"
          >
            <button
              type="button"
              onClick={() => setShowProModal(false)}
              className="absolute top-4 right-4 text-bone-4 hover:text-bone"
              aria-label={t('Close', 'Fermer')}
            >
              <X className="w-4 h-4" />
            </button>
            <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4 mb-3">
              Pro tier
            </p>
            <h3 className="font-serif italic text-2xl text-bone mb-4">
              {t('Curtain rises soon.', 'Le rideau se lève bientôt.')}
            </h3>
            <p className="font-mono text-[12px] leading-relaxed text-bone-3 mb-6">
              {t(
                'Self-serve subscription is in final preparation. Want to be notified when it opens?',
                'L\'abonnement en self-service est en préparation. Souhaitez-vous être prévenu de son ouverture ?',
              )}
            </p>
            <div className="flex gap-3">
              <a
                href={`mailto:${ENTERPRISE_EMAIL}?subject=${encodeURIComponent('Notify me about Pro tier')}`}
                className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-3 bg-brass text-ink font-mono text-[11px] tracking-cta uppercase hover:bg-brass-2 transition-colors"
              >
                {t('Notify me', 'Me prévenir')}
                <span aria-hidden="true">→</span>
              </a>
              <button
                type="button"
                onClick={() => setShowProModal(false)}
                className="px-4 py-3 font-mono text-[11px] tracking-cta uppercase text-bone-3 hover:text-bone"
              >
                {t('Close', 'Fermer')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bottom link */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-center">
        <Link
          to="/login"
          className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3 hover:text-brass transition-colors"
        >
          {t('Already a member? Sign in →', 'Déjà membre ? Se connecter →')}
        </Link>
      </div>
    </div>
  );
}
