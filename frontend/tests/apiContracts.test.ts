/**
 * VAGUE 1 / file D — PROD-10 (contrats frontend/API) et BILL-11 (refus de
 * credits invisible).
 *
 * Constats d'Astra L526 et L807, re-mesures le 16/09 sur `f78e8ad` :
 *
 *  PROD-10
 *   1. `apiCall` finit par `return response.json()` : une suppression reussie
 *      en **204 No Content** a un corps vide, `json()` jette, et l'interface
 *      annonce un echec apres une suppression reelle.
 *   2. Une erreur structuree (`FeatureAccessError` : `detail` est un objet)
 *      devient `new Error(error.detail)` -> `Error("[object Object]")` :
 *      le palier requis, le code et l'URL d'upgrade sont perdus.
 *   3. `ProjectDetailPage.sendChat` lit `resp.assistant_message` ; la route
 *      `POST /api/projects/{id}/chat` rend `message` (`SophieResponse`) : la
 *      reponse **reussie** de Sophie n'apparait jamais.
 *   4. `submitCR` force `status: 'submitted'` alors que la route rend
 *      `status: 'analyzed'` : le bouton d'approbation disparait jusqu'au
 *      rechargement.
 *
 * Le cinquieme parcours (refus de credits invisible) est BILL-11 :
 * `frontend/tests/executionFailure.test.ts`.
 *
 * La lecture vit dans deux modules purs ; les pages ne font que rendre.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { ApiError, parseApiError, readChatReply, readCrStatus } from '../src/lib/apiContracts.ts';

// ─────────────────────────────────────────────────────────────────────
// PROD-10 — erreurs structurees
// ─────────────────────────────────────────────────────────────────────

test('une erreur de palier conserve son code, son palier et son URL', () => {
  const corps = {
    detail: {
      error: 'feature_not_available',
      feature: 'build_phase',
      required_tier: 'team',
      message: "La fonctionnalité 'build_phase' nécessite un abonnement Team",
      upgrade_url: '/pricing',
    },
  };
  const err = parseApiError(403, corps);

  assert.ok(err instanceof ApiError);
  assert.equal(err.status, 403);
  assert.equal(err.code, 'feature_not_available');
  assert.equal(err.requiredTier, 'team');
  assert.equal(err.upgradeUrl, '/pricing');
  // Le defaut exact : le message devenait "[object Object]".
  assert.doesNotMatch(err.message, /\[object Object\]/);
  assert.match(err.message, /build_phase/);
});

test('une erreur de quota conserve ses chiffres', () => {
  const err = parseApiError(403, {
    detail: {
      error: 'limit_exceeded',
      limit_name: 'max_projects',
      current: 1,
      limit: 1,
      tier: 'free',
      message: 'Limite atteinte: 1/1. Passez à un abonnement supérieur.',
      upgrade_url: '/pricing',
    },
  });
  assert.equal(err.code, 'limit_exceeded');
  assert.match(err.message, /1\/1/);
  assert.doesNotMatch(err.message, /\[object Object\]/);
});

test('un detail textuel reste le message', () => {
  const err = parseApiError(404, { detail: 'Project not found' });
  assert.equal(err.message, 'Project not found');
  assert.equal(err.status, 404);
  assert.equal(err.code, undefined);
});

test('une erreur de validation FastAPI (liste) reste lisible', () => {
  const err = parseApiError(422, {
    detail: [{ loc: ['body', 'message'], msg: 'field required', type: 'value_error.missing' }],
  });
  assert.match(err.message, /field required/);
  assert.doesNotMatch(err.message, /\[object Object\]/);
});

test('un corps illisible ne produit pas un message vide', () => {
  // Regle 6 : mieux vaut « HTTP 500 » qu'un message vide qui laisse croire
  // que rien ne s'est passe.
  for (const corps of [null, undefined, {}, 'boom', 42]) {
    const err = parseApiError(500, corps);
    assert.ok(err.message.length > 0, `message vide pour ${JSON.stringify(corps)}`);
    assert.equal(err.status, 500);
  }
});

// ─────────────────────────────────────────────────────────────────────
// PROD-10 — formes de reponse lues par les pages
// ─────────────────────────────────────────────────────────────────────

test('la reponse de Sophie est lue sous le nom que le backend envoie', () => {
  // `SophieResponse` (backend/app/schemas/project_conversation.py) rend
  // `message`. La page lisait `assistant_message`, qui n'existe pas.
  assert.equal(readChatReply({ message: 'Bonjour, je vous écoute.' }), 'Bonjour, je vous écoute.');
  assert.equal(readChatReply({ assistant_message: { message: 'legacy' } }), 'legacy');
  assert.equal(readChatReply({ response: 'autre forme' }), 'autre forme');
});

test('une reponse de chat vide ne devient pas une bulle vide', () => {
  assert.equal(readChatReply({}), null);
  assert.equal(readChatReply(null), null);
  assert.equal(readChatReply({ message: '   ' }), null);
});

test('le statut de CR vient de la reponse, pas d une constante', () => {
  // `POST .../change-requests/{id}/submit` rend `status: "analyzed"` : la
  // page forcait « submitted » et faisait disparaitre le bouton d'approbation.
  assert.equal(readCrStatus({ status: 'analyzed' }, 'submitted'), 'analyzed');
  assert.equal(readCrStatus({ change_request: { status: 'approved' } }, 'submitted'), 'approved');
});

test('un statut de CR absent retombe sur la valeur demandee, pas sur un statut invente', () => {
  assert.equal(readCrStatus({}, 'submitted'), 'submitted');
  assert.equal(readCrStatus(null, 'submitted'), 'submitted');
  assert.equal(readCrStatus({ status: 'nawak' }, 'submitted'), 'submitted');
});
