/**
 * Pricing — A5.4
 * Refonte commerciale + visuelle Studio : Free / Pro / Team / Enterprise.
 * Page publique (pas de ProtectedRoute), accessible avec un AppShell variant="public".
 *
 * Vague B, lot B7 (D9, 03/09) : plus aucun prix ni nombre de crédits en dur
 * ici. La table `tier_config` est la seule source ; cette page appelle
 * `publicTiers.list()` (`GET /api/subscription/tiers`, public, sans jeton)
 * et affiche un état de chargement / d'erreur explicite — jamais un chiffre
 * de repli silencieux si l'appel échoue (règle 6).
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, X } from 'lucide-react';
import { useLang } from '../contexts/LangContext';
import { publicTiers, type PublicTier } from '../services/api';

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

interface TierCopy {
  id: Tier;
  name: string;
  tagline: { en: string; fr: string };
  projects: { en: string; fr: string };
  scope: { en: string; fr: string };
  cta: { en: string; fr: string };
  highlight?: boolean;
}

// Copie marketing statique — aucun prix, aucun nombre de crédits ici (D9).
// Ces chiffres viennent exclusivement de `publicTiers.list()` (état `apiTiers`
// dans le composant), lu depuis `tier_config`.
const TIER_COPY: TierCopy[] = [
  {
    id: 'free',
    name: 'Free',
    tagline: { en: 'Try the Studio', fr: 'Découvrir le Studio' },
    projects: { en: '1 project · SDS only', fr: '1 projet · SDS uniquement' },
    scope: { en: 'Zero data retention', fr: 'Zero data retention' },
    cta: { en: 'Sign up free', fr: 'Créer un compte' },
  },
  {
    id: 'pro',
    name: 'Pro',
    tagline: { en: 'For consultants & freelance admins', fr: 'Pour consultants & admins freelance' },
    projects: { en: '5 projects · SDS + BUILD', fr: '5 projets · SDS + BUILD' },
    scope: { en: 'Git, SFDX, priority support', fr: 'Git, SFDX, support prioritaire' },
    cta: { en: 'Subscribe', fr: "S'abonner" },
    highlight: true,
  },
  {
    id: 'team',
    name: 'Team',
    tagline: { en: 'For agencies & in-house teams', fr: 'Pour agences & équipes internes' },
    projects: { en: 'Unlimited · multi-env', fr: 'Illimités · multi-env' },
    scope: { en: 'Custom templates, shared workspaces', fr: 'Templates personnalisés, workspaces partagés' },
    cta: { en: 'Talk to us', fr: 'Nous contacter' },
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    tagline: { en: 'For large organisations', fr: 'Pour grandes organisations' },
    projects: { en: 'Unlimited · on-premise', fr: 'Illimités · on-premise' },
    scope: { en: 'SLA, dedicated support, ZDR', fr: 'SLA, support dédié, ZDR' },
    cta: { en: 'Talk to us', fr: 'Nous contacter' },
  },
];

const TIER_ORDER: Tier[] = ['free', 'pro', 'team', 'enterprise'];

// Formatage des chiffres reçus de l'API — jamais une valeur de repli, un
// tier absent de la réponse (Enterprise n'a pas de ligne `tier_config`)
// rend "Sur devis" / "On request", jamais un nombre inventé.
function formatPrice(apiTier: PublicTier | undefined, lang: 'en' | 'fr'): string {
  if (!apiTier || apiTier.price_eur_monthly === null) {
    return lang === 'fr' ? 'Sur devis' : 'On request';
  }
  const grouped = new Intl.NumberFormat(lang === 'fr' ? 'fr-FR' : 'en-US').format(
    apiTier.price_eur_monthly,
  );
  return `${grouped}€`;
}

function formatCredits(apiTier: PublicTier | undefined, lang: 'en' | 'fr'): string {
  if (!apiTier || apiTier.credits === null || apiTier.credits_period === null) {
    return lang === 'fr' ? 'Illimité' : 'Unlimited';
  }
  const grouped = new Intl.NumberFormat(lang === 'fr' ? 'fr-FR' : 'en-US').format(
    apiTier.credits,
  );
  const noun = lang === 'fr' ? 'crédits' : 'credits';
  const period =
    apiTier.credits_period === 'day'
      ? lang === 'fr'
        ? 'jour'
        : 'day'
      : lang === 'fr'
        ? 'mois'
        : 'month';
  return `${grouped} ${noun} / ${period}`;
}

const FAQ = [
  {
    q: { en: 'How are credits counted?', fr: 'Comment les crédits sont-ils comptés ?' },
    a: {
      en: 'Each agent invocation consumes credits proportional to the LLM tokens used, so cost scales with project complexity rather than a fixed count. The exact allowance for each plan is shown above, read live from our pricing table.',
      fr: 'Chaque invocation d\'agent consomme des crédits proportionnels aux tokens LLM utilisés : le coût suit la complexité du projet plutôt qu\'un forfait fixe. L\'allocation exacte de chaque plan est affichée ci-dessus, lue en direct depuis notre table de tarifs.',
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
export async function _startStripeCheckout(tier: 'pro' | 'team'): Promise<void> {
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

  // Vague B / B7 (D9) : les prix et crédits ne sont plus en dur — ils
  // viennent de `tier_config` via cet appel. Trois états explicites,
  // jamais de nombre de repli silencieux si l'appel échoue (règle 6).
  const [apiTiers, setApiTiers] = useState<PublicTier[] | null>(null);
  const [tiersError, setTiersError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    publicTiers
      .list()
      .then((res) => {
        if (!cancelled) setApiTiers(res.tiers);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setTiersError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const apiTiersById = (apiTiers ?? []).reduce<Record<string, PublicTier>>((acc, at) => {
    acc[at.tier] = at;
    return acc;
  }, {});

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
        {tiersError && (
          <p className="mb-6 font-mono text-[12px] text-red-400 border border-red-400/30 bg-red-400/5 px-4 py-3">
            {t(
              `Pricing is temporarily unavailable (${tiersError}). Please retry in a moment.`,
              `Les tarifs sont temporairement indisponibles (${tiersError}). Réessayez dans un instant.`,
            )}
          </p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {TIER_ORDER.map((id) => {
            const copy = TIER_COPY.find((c) => c.id === id)!;
            const apiTier = apiTiersById[id];
            const highlighted = !!copy.highlight;
            const loading = !apiTiers && !tiersError;
            return (
              <div
                key={copy.id}
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
                  {copy.name}
                </p>
                <p className="font-mono text-[11px] text-bone-3 mt-1 mb-6 min-h-[36px]">
                  {t(copy.tagline.en, copy.tagline.fr)}
                </p>

                <div className="mb-6">
                  {loading ? (
                    <span className="font-mono text-[13px] text-bone-4 animate-pulse">
                      {t('Loading…', 'Chargement…')}
                    </span>
                  ) : (
                    <>
                      <span className="font-serif italic text-4xl text-bone">
                        {formatPrice(apiTier, lang)}
                      </span>
                      {apiTier && apiTier.price_eur_monthly !== null && apiTier.price_eur_monthly > 0 && (
                        <span className="font-mono text-[11px] text-bone-4 ml-1">
                          {t('/ month', '/ mois')}
                        </span>
                      )}
                    </>
                  )}
                </div>

                <ul className="space-y-2.5 mb-8 flex-1">
                  <li className="font-mono text-[11px] text-bone-2">
                    {loading ? t('Loading…', 'Chargement…') : formatCredits(apiTier, lang)}
                  </li>
                  <li className="font-mono text-[11px] text-bone-3">
                    {t(copy.projects.en, copy.projects.fr)}
                  </li>
                  <li className="font-mono text-[11px] text-bone-3">
                    {t(copy.scope.en, copy.scope.fr)}
                  </li>
                </ul>

                <button
                  type="button"
                  onClick={() => handleCta(copy.id)}
                  className={`w-full inline-flex items-center justify-center gap-2 px-4 py-3 font-mono text-[11px] tracking-cta uppercase transition-colors ${
                    highlighted
                      ? 'bg-brass text-ink hover:bg-brass-2'
                      : 'bg-ink-3 text-bone border border-bone/10 hover:border-brass/40'
                  }`}
                >
                  {t(copy.cta.en, copy.cta.fr)}
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
                {TIER_COPY.map((copy) => (
                  <th
                    key={copy.id}
                    className="text-center py-3 px-3 font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 font-normal min-w-[110px]"
                  >
                    {copy.name}
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
                      {TIER_COPY.map((copy) => (
                        <td key={copy.id} className="py-3 px-3 text-center">
                          <FeatureValue value={feature.values[copy.id]} />
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
