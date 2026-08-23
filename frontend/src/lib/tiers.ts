/**
 * Vocabulaire des paliers d'abonnement, cote frontend.
 *
 * VAGUE 2 / LOT 3 — audit croise du 21/08/2026.
 *
 * Le defaut : `SubscriptionBadge.tsx` connaissait `free | premium | enterprise`
 * alors que le backend sert quatre paliers, `free | pro | team | enterprise`
 * (`backend/app/models/subscription.py:SubscriptionTier`). Deux consequences :
 *
 *  - `premium` n'existe plus cote serveur. Un badge cale dessus ne correspond a
 *    aucun compte reel.
 *  - `team` etait absent de la table d'ordre de `FeatureGate`. La comparaison
 *    `tierOrder[userTier] >= tierOrder[requiredTier]` rendait alors `false` sur
 *    un `undefined` : **un compte Team se voyait refuser par l'UI une
 *    fonctionnalite que le backend lui accorde.**
 *
 * L'audit demande de raccrocher au payload de `FeatureAccessError`
 * (`error`, `feature`, `required_tier`, `upgrade_url`) plutot qu'a une
 * constante recopiee : c'est `parseFeatureAccessError` ci-dessous. Le serveur
 * reste la source de verite sur ce qu'il faut pour acceder a quoi ; le
 * frontend n'a plus qu'a l'afficher.
 *
 * Module pur, sans dependance, teste par `frontend/tests/tiers.test.ts`.
 */

/** Les paliers servis par le backend, dans l'ordre croissant de droits. */
export const TIERS = ['free', 'pro', 'team', 'enterprise'] as const;

export type Tier = (typeof TIERS)[number];

/** Ordre des paliers. `team` y figure — c'est tout l'objet du correctif. */
export const TIER_ORDER: Record<Tier, number> = {
  free: 0,
  pro: 1,
  team: 2,
  enterprise: 3,
};

const TIER_LABELS: Record<Tier, string> = {
  free: 'Free',
  pro: 'Pro',
  team: 'Team',
  enterprise: 'Enterprise',
};

/**
 * Alias historiques. `premium` est l'ancien nom de `pro` : le backend fait la
 * meme correspondance dans `credit_service._resolve_credit_tier`, pour les
 * comptes crees avant le passage a quatre paliers.
 */
const TIER_ALIASES: Record<string, Tier> = {
  premium: 'pro',
};

/**
 * Ramene une valeur venue du serveur, du stockage local ou d'une URL a un
 * palier connu.
 *
 * Un palier inconnu retombe sur `free` — le moins-disant. C'est le seul repli
 * sur : accorder par defaut ferait proposer par l'UI des actions que le backend
 * refusera en 403, ce qui est exactement le defaut qu'on corrige.
 */
export function normalizeTier(value: unknown): Tier {
  if (typeof value !== 'string') return 'free';
  const lowered = value.trim().toLowerCase();
  if ((TIERS as readonly string[]).includes(lowered)) return lowered as Tier;
  return TIER_ALIASES[lowered] ?? 'free';
}

/** `true` si `userTier` couvre `requiredTier`. */
export function hasTier(userTier: unknown, requiredTier: unknown): boolean {
  return TIER_ORDER[normalizeTier(userTier)] >= TIER_ORDER[normalizeTier(requiredTier)];
}

/** Libelle affichable d'un palier. */
export function tierLabel(value: unknown): string {
  return TIER_LABELS[normalizeTier(value)];
}

/** Ce que le backend envoie dans un 403 de palier. */
export interface FeatureAccessRefusal {
  feature: string;
  requiredTier: Tier;
  message: string;
  upgradeUrl: string;
}

/**
 * Lit le payload de `FeatureAccessError` — la seule source de verite sur le
 * palier requis par une fonctionnalite.
 *
 * Accepte la reponse complete (`{ detail: {...} }`, forme de FastAPI) comme le
 * `detail` deja deballe, selon la couche qui appelle. Rend `null` pour toute
 * autre erreur, y compris `limit_exceeded`, qui n'est pas un refus de palier.
 *
 * `required_tier` absent retombe sur `pro` : le backend ne produit pas ce cas,
 * mais une invite d'upgrade illisible serait pire qu'une invite approximative.
 */
export function parseFeatureAccessError(body: unknown): FeatureAccessRefusal | null {
  if (!body || typeof body !== 'object') return null;

  const outer = body as Record<string, unknown>;
  const candidate =
    outer.error === 'feature_not_available'
      ? outer
      : (outer.detail as Record<string, unknown> | undefined);

  if (!candidate || typeof candidate !== 'object') return null;
  if (candidate.error !== 'feature_not_available') return null;

  const feature = typeof candidate.feature === 'string' ? candidate.feature : '';
  const requiredTier =
    typeof candidate.required_tier === 'string'
      ? normalizeTier(candidate.required_tier)
      : 'pro';

  return {
    feature,
    requiredTier,
    message:
      typeof candidate.message === 'string'
        ? candidate.message
        : `Cette fonctionnalité nécessite un abonnement ${TIER_LABELS[requiredTier]}`,
    upgradeUrl:
      typeof candidate.upgrade_url === 'string' ? candidate.upgrade_url : '/pricing',
  };
}
