/**
 * VAGUE 1 / file D — PROD-11 : le wizard perd des informations determinantes.
 *
 * Constat d'Astra L546, re-mesure le 16/09 sur `f78e8ad` :
 *
 *  1. Le PDF choisi n'est conserve **que par son nom**
 *     (`onPickFile` : `update('uploaded_file_name', file.name)`), jamais
 *     televerse, alors que l'ecran annonce « Sophie le lira pendant le
 *     casting ».
 *  2. L'edition Salesforce est transformee en produit :
 *     `enterprise -> 'Sales Cloud'`, `unlimited -> 'Service Cloud'`. Une
 *     edition de licence et un produit sont deux choses differentes ; le
 *     projet part donc avec un produit que l'utilisateur n'a pas choisi.
 *  3. `industry` et `selected_agents` sont envoyes a
 *     `POST /api/pm-orchestrator/projects`, dont le schema `ProjectCreate`
 *     ne les declare pas : ils sont ignores. `industry` n'existe ni dans le
 *     schema ni dans le modele `Project` — mesure par grep, aucune ligne.
 *     Le secteur choisi au premier acte disparait donc entierement.
 *  4. Les couts affiches a l'acte IV (SDS 800, BUILD 3500, Express +20 %)
 *     sont des constantes du fichier, sans transmission ni mecanisme
 *     d'execution correspondant.
 *
 * Decision prise pour le point 1, sans demi-mesure : **la fonction est
 * retiree**. Motif mesure — `agents/roles/salesforce_pm.py` (Sophie, qui
 * extrait les BR) passe `rag_context=None` et n'interroge jamais le RAG
 * projet ; seuls Olivia, Marcus et Lucas passent `project_id` a
 * `get_salesforce_context`. Meme televerse, le PDF ne serait pas lu au moment
 * ou l'ecran promet qu'il l'est. Et le palier Free n'a pas
 * `upload_documents`. Promettre moins et le tenir.
 *
 *   node --experimental-strip-types --test frontend/tests/wizardPayload.test.ts
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CHAMPS_ACCEPTES,
  buildProjectPayload,
  type WizardInput,
} from '../src/lib/wizardPayload.ts';

const SAISIE: WizardInput = {
  name: '  LogiFleet — Service Cloud  ',
  industry: 'logistics',
  salesforce_product: 'service_cloud',
  salesforce_edition: 'enterprise',
  description: 'Refonte du suivi de flotte pour 400 techniciens itinerants.',
  business_goals: 'Reduire de 30% le temps de traitement des interventions.',
  constraints: 'Pas de developpement Apex sur mesure en phase 1.',
};

test('le nom est transmis nettoye', () => {
  const payload = buildProjectPayload(SAISIE);
  assert.equal(payload.name, 'LogiFleet — Service Cloud');
});

test("l'edition n'est plus transformee en produit", () => {
  // Le defaut : `enterprise -> 'Sales Cloud'`. Deux concepts differents.
  const payload = buildProjectPayload(SAISIE);
  assert.equal(payload.salesforce_product, 'Service Cloud');

  const autre = buildProjectPayload({ ...SAISIE, salesforce_product: 'sales_cloud' });
  assert.equal(autre.salesforce_product, 'Sales Cloud');
});

test("l'edition choisie suit le projet au lieu d'etre perdue", () => {
  // Elle n'a pas de colonne dediee : plutot que de la jeter, elle est portee
  // par le texte des exigences, que l'extraction lit reellement.
  const payload = buildProjectPayload(SAISIE);
  assert.match(payload.business_requirements, /Enterprise/i);
});

test('le secteur choisi au premier acte ne disparait pas', () => {
  // `industry` n'existe ni dans `ProjectCreate` ni dans le modele `Project` :
  // l'envoyer comme champ revient a le perdre.
  const payload = buildProjectPayload(SAISIE);
  assert.match(payload.business_requirements, /logistique|logistics/i);
});

test('le brief, les objectifs et les contraintes sont tous transmis', () => {
  const payload = buildProjectPayload(SAISIE);
  assert.match(payload.business_requirements, /400 techniciens/);
  assert.match(payload.business_requirements, /30%/);
  assert.match(payload.business_requirements, /Apex sur mesure/);
});

test('le corps envoye ne contient que des champs que le schema accepte', () => {
  // Envoyer un champ ignore donne l'illusion qu'il est pris en compte.
  const payload = buildProjectPayload(SAISIE);
  for (const cle of Object.keys(payload)) {
    assert.ok(
      CHAMPS_ACCEPTES.includes(cle),
      `${cle} n'est pas declare par ProjectCreate : il serait ignore`,
    );
  }
});

test('aucun champ de fichier ni de priorite ne subsiste', () => {
  // PROD-11 : ni `uploaded_file_name` (jamais televerse), ni `priority`
  // (Express +20 % sans mecanisme d'execution).
  const payload = buildProjectPayload(SAISIE) as Record<string, unknown>;
  assert.equal(payload.uploaded_file_name, undefined);
  assert.equal(payload.priority, undefined);
  assert.equal(payload.selected_agents, undefined);
});

test('les champs obligatoires du schema sont toujours presents', () => {
  const payload = buildProjectPayload({
    name: 'Projet minimal',
    industry: '',
    salesforce_product: '',
    salesforce_edition: 'other',
    description: 'Une description suffisamment longue pour le schema.',
    business_goals: '',
    constraints: '',
  });
  assert.ok(payload.name.length > 0);
  assert.ok(payload.salesforce_product.length > 0);
  assert.ok(payload.organization_type.length > 0);
  // `ProjectCreate` impose min_length=10 sur les exigences.
  assert.ok(payload.business_requirements.length >= 10);
});

test('un produit inconnu ne devient pas un produit invente', () => {
  // Regle 6 : plutot « Platform », le socle neutre, qu'un Cloud choisi au
  // hasard pour le client.
  const payload = buildProjectPayload({ ...SAISIE, salesforce_product: 'nawak' });
  assert.equal(payload.salesforce_product, 'Platform');
});
