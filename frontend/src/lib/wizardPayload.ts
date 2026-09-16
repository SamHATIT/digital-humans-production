/**
 * Corps envoye par le wizard a `POST /api/pm-orchestrator/projects` — PROD-11.
 *
 * Constat d'Astra L546. Trois pertes mesurees le 16/09 sur `f78e8ad` :
 *
 *  - l'edition Salesforce etait transformee en produit
 *    (`enterprise -> 'Sales Cloud'`, `unlimited -> 'Service Cloud'`) : une
 *    edition de licence et un produit sont deux choses differentes, et le
 *    projet partait avec un produit que personne n'avait choisi ;
 *  - `industry` et `selected_agents` etaient envoyes alors que le schema
 *    `ProjectCreate` ne les declare pas. `industry` n'existe ni dans le
 *    schema ni dans le modele `Project` (grep : aucune ligne) : le secteur
 *    choisi au premier acte disparaissait entierement ;
 *  - `uploaded_file_name` et `priority` etaient portes par le formulaire sans
 *    aucun mecanisme derriere.
 *
 * Regle appliquee ici : ce qui n'a pas de colonne n'est pas jete en silence,
 * il est porte par le texte des exigences — que l'extraction lit reellement.
 * Ce qui n'a pas de mecanisme n'est pas demande.
 *
 * Module pur, teste par `frontend/tests/wizardPayload.test.ts`.
 */

/** Champs declares par `ProjectCreate` (backend/app/schemas/project.py). */
export const CHAMPS_ACCEPTES = [
  'name',
  'description',
  'salesforce_product',
  'organization_type',
  'business_requirements',
  'existing_systems',
  'compliance_requirements',
  'expected_users',
  'expected_data_volume',
  'architecture_preferences',
  'architecture_notes',
  'requirements_text',
] as const;

export type SalesforceEdition = 'enterprise' | 'unlimited' | 'other';

export interface WizardInput {
  name: string;
  industry: string;
  /** Produit choisi par l'utilisateur — distinct de l'edition. */
  salesforce_product: string;
  salesforce_edition: SalesforceEdition;
  description: string;
  business_goals: string;
  constraints: string;
}

export interface ProjectPayload {
  name: string;
  description: string;
  salesforce_product: string;
  organization_type: string;
  business_requirements: string;
}

/**
 * Produits Salesforce proposes. La cle est la valeur du formulaire, la valeur
 * le libelle attendu par le backend.
 */
export const PRODUITS: Record<string, string> = {
  sales_cloud: 'Sales Cloud',
  service_cloud: 'Service Cloud',
  platform: 'Platform',
  experience_cloud: 'Experience Cloud',
  field_service: 'Field Service',
};

const EDITIONS: Record<SalesforceEdition, string> = {
  enterprise: 'Enterprise',
  unlimited: 'Unlimited',
  other: 'Autre / inconnue',
};

const SECTEURS: Record<string, string> = {
  logistics: 'Logistique',
  pharma: 'Pharma',
  healthcare: 'Santé',
  telecom: 'Télécom',
  b2b: 'B2B',
  energy: 'Énergie',
  retail: 'Retail',
  agentforce: 'Agentforce',
  other: 'Autre',
};

/**
 * Le produit demande, ou `Platform` si la valeur est inconnue.
 *
 * Regle 6 : plutot le socle neutre qu'un Cloud choisi au hasard pour le
 * client — c'est exactement ce que faisait la deduction depuis l'edition.
 */
function produit(valeur: string): string {
  return PRODUITS[valeur?.trim?.().toLowerCase?.() ?? ''] ?? 'Platform';
}

function secteur(valeur: string): string | null {
  const cle = valeur?.trim?.().toLowerCase?.() ?? '';
  if (!cle) return null;
  return SECTEURS[cle] ?? valeur.trim();
}

/**
 * Construit le corps de creation de projet.
 *
 * Tout ce qui n'a pas de colonne dediee (secteur, edition) est ecrit dans
 * `business_requirements`, qui est le texte lu par l'extraction des BR : une
 * information qui compte pour l'analyse y arrive, au lieu d'etre envoyee dans
 * un champ que le schema ignore.
 */
export function buildProjectPayload(saisie: WizardInput): ProjectPayload {
  const nom = (saisie.name ?? '').trim();
  const description = (saisie.description ?? '').trim();
  const objectifs = (saisie.business_goals ?? '').trim();
  const contraintes = (saisie.constraints ?? '').trim();

  const contexte: string[] = [];
  const secteurLisible = secteur(saisie.industry);
  if (secteurLisible) contexte.push(`- Secteur : ${secteurLisible}`);
  contexte.push(`- Produit Salesforce : ${produit(saisie.salesforce_product)}`);
  contexte.push(
    `- Édition Salesforce : ${EDITIONS[saisie.salesforce_edition] ?? EDITIONS.other}`,
  );

  const blocs = [
    description,
    `\n## Contexte\n${contexte.join('\n')}`,
    objectifs ? `\n## Objectifs métier\n${objectifs}` : '',
    contraintes ? `\n## Contraintes / hors-périmètre\n${contraintes}` : '',
  ].filter(Boolean);

  return {
    name: nom,
    description,
    salesforce_product: produit(saisie.salesforce_product),
    organization_type: 'New Implementation',
    business_requirements: blocs.join('\n\n'),
  };
}
