import { Fragment, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, X } from 'lucide-react';
import { useLang } from '../contexts/LangContext';
import { publicTiers, type PublicTier } from '../services/api';
import {
  FEATURE_GROUPS,
  featureValue,
  formatCredits,
  formatLimit,
  formatPrice,
} from '../lib/tierFeatures';

type Tier = 'free' | 'pro' | 'team' | 'enterprise';

interface TierCopy {
  id: Tier;
  name: string;
  tagline: { en: string; fr: string };
  cta: { en: string; fr: string };
  highlight?: boolean;
}

// BILL-07 — copie marketing : aucun prix, aucun nombre de credits, et
// desormais aucune promesse de fonctionnalite. Ce que porte chaque palier
// vient exclusivement de `/api/subscription/tiers` (matrice `TIER_FEATURES`
// du serveur). La page annoncait le SDS et un projet au Free, BUILD/Git/SFDX
// au Pro et des projets illimites au Team : trois promesses que le serveur
// refuse.
const TIER_COPY: TierCopy[] = [
  {
    id: 'free',
    name: 'Free',
    tagline: { en: 'Try the Studio', fr: 'Découvrir le Studio' },
    cta: { en: 'Sign up free', fr: 'Créer un compte' },
  },
  {
    id: 'pro',
    name: 'Pro',
    tagline: { en: 'For consultants & freelance admins', fr: 'Pour consultants & admins freelance' },
    cta: { en: 'Subscribe', fr: "S'abonner" },
    highlight: true,
  },
  {
    id: 'team',
    name: 'Team',
    tagline: { en: 'For agencies & in-house teams', fr: 'Pour agences & équipes internes' },
    cta: { en: 'Talk to us', fr: 'Nous contacter' },
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    tagline: { en: 'For large organisations', fr: 'Pour grandes organisations' },
    cta: { en: 'Talk to us', fr: 'Nous contacter' },
  },
];

const TIER_ORDER: Tier[] = ['free', 'pro', 'team', 'enterprise'];

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
      en: 'Your projects, conversations and deliverables are stored on EU-hosted infrastructure and deleted after the retention period set out in our privacy policy. You can request deletion at any time.',
      fr: 'Vos projets, conversations et livrables sont hébergés sur une infrastructure UE et supprimés au terme de la durée indiquée dans notre politique de confidentialité. Vous pouvez en demander la suppression à tout moment.',
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
 * Checkout Stripe — BILL-07.
 *
 * Etat avant : le bouton Pro ouvrait un modal « le rideau se lève bientôt »
 * et ce helper s'appelait `_startStripeCheckout`, documente comme « NON
 * BRANCHE ». L'abonnement Pro etait donc invendable alors que l'ouverture
 * Free + Pro est decidee pour le 1er octobre.
 *
 * `POST /api/billing/checkout` exige un jeton : un visiteur non connecte est
 * envoye vers /signup, et l'intention est memorisee pour reprendre le
 * checkout apres la creation du compte.
 *
 * Aucun repli silencieux (regle 6) : si le backend repond 503 « Billing is
 * not configured », l'appelant recoit le motif et l'affiche.
 */
export async function startStripeCheckout(tier: 'pro' | 'team'): Promise<void> {
  const token = localStorage.getItem('token');
  if (!token) {
    sessionStorage.setItem('post_signup_checkout_tier', tier);
    window.location.href = `/signup?tier=${tier}`;
    return;
  }

  const res = await fetch('/api/billing/checkout', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ tier }),
  });

  if (!res.ok) {
    const corps = await res.json().catch(() => null);
    const motif =
      (corps && typeof corps.detail === 'string' && corps.detail) ||
      `HTTP ${res.status}`;
    throw new Error(motif);
  }

  const { url } = await res.json();
  if (!url) throw new Error('checkout sans url');
  window.location.href = url;
}

export default function Pricing() {
  const { t, lang } = useLang();
  // BILL-07 : le refus de checkout est montre, jamais avale (regle 6).
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [checkoutPending, setCheckoutPending] = useState<Tier | null>(null);

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

  const handleCta = async (tier: Tier) => {
    setCheckoutError(null);
    if (tier === 'free') {
      // ONBOARDING-001: Free tier is self-serve — go straight to /signup.
      window.location.href = '/signup?tier=free';
      return;
    }
    if (tier === 'pro') {
      // BILL-07 : ce bouton ouvrait un modal « bientôt ». Il ouvre le
      // Checkout Stripe.
      setCheckoutPending('pro');
      try {
        await startStripeCheckout('pro');
      } catch (err) {
        setCheckoutError(err instanceof Error ? err.message : String(err));
      } finally {
        setCheckoutPending(null);
      }
      return;
    }
    // Team et Enterprise restent sur un contact : Team n'est pas ouvert le
    // 1er octobre (perimetre Free + Pro decide le 15/09), Enterprise est
    // on-premise et negocie.
    const subject = encodeURIComponent(
      tier === 'team' ? 'Team plan inquiry' : 'Enterprise plan inquiry',
    );
    window.location.href = `mailto:${ENTERPRISE_EMAIL}?subject=${subject}`;
  };

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
                  {/* BILL-07 : ces deux lignes etaient des promesses ecrites a la
                      main (« 1 projet · SDS uniquement », « Git, SFDX, support
                      prioritaire ») que la matrice serveur contredit. Elles sont
                      desormais lues dans la reponse API. */}
                  <li className="font-mono text-[11px] text-bone-3">
                    {loading
                      ? t('Loading…', 'Chargement…')
                      : `${formatLimit(apiTier, 'max_projects', lang)} ${t('projects', 'projets')}`}
                  </li>
                  <li className="font-mono text-[11px] text-bone-3">
                    {loading
                      ? t('Loading…', 'Chargement…')
                      : featureValue(apiTier, 'sds_document')
                        ? t('SDS deliverable included', 'Livrable SDS inclus')
                        : t('Conversation with Sophie & Olivia', 'Dialogue avec Sophie & Olivia')}
                  </li>
                </ul>

                <button
                  type="button"
                  onClick={() => void handleCta(copy.id)}
                  disabled={checkoutPending === copy.id}
                  className={`w-full inline-flex items-center justify-center gap-2 px-4 py-3 font-mono text-[11px] tracking-cta uppercase transition-colors disabled:opacity-50 ${
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

        {/* BILL-07 : chaque cellule est lue dans `/api/subscription/tiers`,
            donc dans `TIER_FEATURES`. Plus aucune promesse ecrite ici. */}
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
              {FEATURE_GROUPS.map((groupe) => (
                <Fragment key={groupe.group.en}>
                  <tr className="border-b border-bone/5">
                    <td colSpan={TIER_COPY.length + 1} className="pt-6 pb-2">
                      <p className="font-mono text-[10px] tracking-eyebrow uppercase text-brass">
                        {t(groupe.group.en, groupe.group.fr)}
                      </p>
                    </td>
                  </tr>
                  {groupe.items.map((ligne) => (
                    <tr
                      key={ligne.key}
                      className="border-b border-bone/5 hover:bg-ink-2/40 transition-colors"
                    >
                      <td className="py-3 pr-4 font-mono text-[12px] text-bone-2">
                        {t(ligne.label.en, ligne.label.fr)}
                      </td>
                      {TIER_COPY.map((copy) => {
                        const apiTier = apiTiersById[copy.id];
                        return (
                          <td key={copy.id} className="py-3 px-3 text-center">
                            {!apiTiers && !tiersError ? (
                              <span className="font-mono text-[11px] text-bone-4">…</span>
                            ) : ligne.numeric ? (
                              <FeatureValue value={formatLimit(apiTier, ligne.key, lang)} />
                            ) : (
                              <FeatureValue value={featureValue(apiTier, ligne.key)} />
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </Fragment>
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

      {/* BILL-07 : le modal « le rideau se lève bientôt » est retire — le
          bouton Pro ouvre le Checkout Stripe. Ce qui reste a montrer, c'est
          un refus eventuel du backend. */}
      {checkoutError && (
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pb-8">
          <p className="border border-error/40 bg-error/5 px-4 py-3 font-mono text-[12px] text-error">
            {t(
              `Checkout is unavailable (${checkoutError}). Please retry, or email us.`,
              `Le paiement est indisponible (${checkoutError}). Réessayez ou écrivez-nous.`,
            )}
          </p>
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
