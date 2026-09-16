/**
 * Lecture des paliers servis par `GET /api/subscription/tiers`.
 *
 * BILL-07 (audit Astra du 06/09, L733) : la page de tarifs lisait bien le prix
 * et les credits depuis l'API, mais son tableau de comparaison etait une
 * constante ecrite a la main qui contredisait la matrice du serveur
 * (`backend/app/models/subscription.py`, `TIER_FEATURES`) — SDS et un projet
 * annonces au Free, BUILD/Git/SFDX annonces au Pro, projets illimites annonces
 * au Team. Et sur erreur de chargement, `formatCredits(undefined)` affichait
 * « Illimité ».
 *
 * Ce module ne contient **aucune valeur commerciale** : ni prix, ni nombre de
 * credits, ni « inclus / non inclus ». Il ne porte que les libelles des lignes
 * et la facon de lire la reponse. La verite reste le serveur (decision D9 du
 * 03/09, `tier_config` + `TIER_FEATURES`).
 *
 * Module pur, sans dependance, teste par `frontend/tests/tierFeatures.test.ts`.
 */

export type DisplayLang = 'en' | 'fr';

/** La forme utile de ce que sert `/api/subscription/tiers`. */
export interface PublicTierLike {
  tier: string;
  name: string;
  price_eur_monthly: number | null;
  credits: number | null;
  credits_period: 'day' | 'month' | null;
  features: Record<string, boolean | number | null>;
  limitations: string[];
}

interface Bilingue {
  en: string;
  fr: string;
}

export interface FeatureRow {
  /** Cle exacte de `TIER_FEATURES` cote serveur. */
  key: string;
  label: Bilingue;
  /** Une limite se lit comme un nombre, pas comme une coche. */
  numeric?: boolean;
}

export interface FeatureGroup {
  group: Bilingue;
  items: FeatureRow[];
}

/**
 * Les lignes du tableau de comparaison. Chaque `key` doit exister dans
 * `TIER_FEATURES` cote serveur : c'est ce qui empeche de re-inventer une
 * fonctionnalite qui n'existe pas dans la matrice.
 */
export const FEATURE_GROUPS: FeatureGroup[] = [
  {
    group: { en: 'Conversation', fr: 'Dialogue' },
    items: [
      { key: 'chat_sophie', label: { en: 'Chat with Sophie (PM)', fr: 'Dialogue avec Sophie (PM)' } },
      { key: 'chat_olivia', label: { en: 'Chat with Olivia (BA)', fr: 'Dialogue avec Olivia (BA)' } },
      { key: 'chat_full_team', label: { en: 'Chat with the full ensemble', fr: "Dialogue avec l'ensemble complet" } },
      { key: 'persistent_memory', label: { en: 'Persistent memory', fr: 'Mémoire persistante' } },
      { key: 'upload_documents', label: { en: 'Document upload', fr: 'Téléversement de documents' } },
    ],
  },
  {
    group: { en: 'SDS Phase', fr: 'Phase SDS' },
    items: [
      { key: 'br_extraction', label: { en: 'Business Requirements extraction', fr: 'Extraction des Business Requirements' } },
      { key: 'uc_generation', label: { en: 'Use Cases generation', fr: 'Génération des Use Cases' } },
      { key: 'solution_design', label: { en: 'Solution Design', fr: 'Solution Design' } },
      { key: 'sds_document', label: { en: 'SDS document', fr: 'Document SDS' } },
      { key: 'export_word', label: { en: 'Word export', fr: 'Export Word' } },
      { key: 'max_brs_per_project', label: { en: 'Max BRs per project', fr: 'BRs max par projet' }, numeric: true },
      { key: 'max_projects', label: { en: 'Max projects', fr: 'Projets max' }, numeric: true },
    ],
  },
  {
    group: { en: 'BUILD Phase', fr: 'Phase BUILD' },
    items: [
      { key: 'build_phase', label: { en: 'BUILD phase (code generation)', fr: 'Phase BUILD (génération de code)' } },
      { key: 'sfdx_deployment', label: { en: 'SFDX deployment', fr: 'Déploiement SFDX' } },
      { key: 'git_integration', label: { en: 'Git integration', fr: 'Intégration Git' } },
      { key: 'multi_environment', label: { en: 'Multi-environments', fr: 'Multi-environnements' } },
    ],
  },
  {
    group: { en: 'Advanced', fr: 'Avancé' },
    items: [
      { key: 'custom_templates', label: { en: 'Custom templates', fr: 'Templates personnalisés' } },
      { key: 'priority_support', label: { en: 'Priority support', fr: 'Support prioritaire' } },
      { key: 'sso_integration', label: { en: 'SSO', fr: 'SSO' } },
      { key: 'audit_logs', label: { en: 'Audit logs', fr: "Journaux d'audit" } },
      { key: 'on_premise', label: { en: 'On-premise deployment', fr: 'Déploiement on-premise' } },
    ],
  },
];

function indisponible(lang: DisplayLang): string {
  return lang === 'fr' ? 'Indisponible' : 'Unavailable';
}

function nombre(valeur: number, lang: DisplayLang): string {
  return new Intl.NumberFormat(lang === 'fr' ? 'fr-FR' : 'en-US').format(valeur);
}

/**
 * Prix mensuel affichable.
 *
 * Un tier absent de la reponse (Enterprise n'a pas de ligne `tier_config`)
 * rend « sur devis » — jamais un nombre, jamais zero.
 */
export function formatPrice(tier: PublicTierLike | undefined, lang: DisplayLang): string {
  if (!tier || tier.price_eur_monthly === null || tier.price_eur_monthly === undefined) {
    return lang === 'fr' ? 'Sur devis' : 'On request';
  }
  return `${nombre(tier.price_eur_monthly, lang)}€`;
}

/**
 * Credits inclus, avec leur rythme.
 *
 * BILL-07 : sur donnee absente, rend « Indisponible ». Jamais « Illimité » —
 * c'etait la promesse la plus chere possible faite sur une valeur qu'on n'a
 * pas (regle 6 : une valeur inconnue se refuse, elle ne se devine pas).
 */
export function formatCredits(tier: PublicTierLike | undefined, lang: DisplayLang): string {
  if (!tier || tier.credits === null || tier.credits === undefined || !tier.credits_period) {
    return indisponible(lang);
  }
  const unite =
    tier.credits_period === 'day'
      ? lang === 'fr'
        ? 'crédits / jour'
        : 'credits / day'
      : lang === 'fr'
        ? 'crédits / mois'
        : 'credits / month';
  return `${nombre(tier.credits, lang)} ${unite}`;
}

/**
 * Valeur booleenne d'une fonctionnalite, lue dans la reponse du serveur.
 *
 * Fail closed : une cle absente vaut `false`. Rendre « inclus » sur une cle
 * inconnue ferait proposer par l'interface une action que le backend refuse
 * en 403 — exactement le defaut corrige par le lot 3 de la vague 2.
 */
export function featureValue(tier: PublicTierLike | undefined, key: string): boolean {
  if (!tier || !tier.features) return false;
  return tier.features[key] === true;
}

/**
 * Limite numerique affichable.
 *
 * Trois cas, volontairement distincts :
 *   - la cle porte un nombre          -> ce nombre ;
 *   - la cle est presente et vaut null -> « illimité » (c'est ce que veut dire
 *     `max_projects: None` cote serveur) ;
 *   - la cle ou le tier est absent     -> « indisponible », jamais « illimité ».
 */
export function formatLimit(
  tier: PublicTierLike | undefined,
  key: string,
  lang: DisplayLang,
): string {
  if (!tier || !tier.features || !(key in tier.features)) return indisponible(lang);
  const valeur = tier.features[key];
  if (valeur === null) return lang === 'fr' ? 'Illimité' : 'Unlimited';
  if (typeof valeur === 'number') return nombre(valeur, lang);
  if (typeof valeur === 'boolean') return valeur ? (lang === 'fr' ? 'Oui' : 'Yes') : '—';
  return indisponible(lang);
}
