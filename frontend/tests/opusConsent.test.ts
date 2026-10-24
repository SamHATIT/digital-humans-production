/**
 * VAGUE 2 / file C — GL-22 : écran de consentement Opus.
 *
 * Le site promet « Opus on opt-in, cost shown before each call ». Le backend
 * refuse un lancement Pro sans décision (409 `consentement_opus_requis`) et
 * un montant accepté qui n'est plus l'estimation (409
 * `consentement_opus_montant_perime`). Ce module lit ces refus, construit le
 * corps du lancement et porte le texte de l'écran ; la page ne fait que rendre.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { parseApiError } from '../src/lib/apiContracts.ts';
import {
  OPUS_CONSENT_TEXT_VERSION,
  buildStartBody,
  opusConsentText,
  readOpusConsentRequest,
} from '../src/lib/opusConsent.ts';

const estimation = {
  requis: true,
  modele: 'claude-opus-5',
  modele_repli: 'claude-sonnet-5',
  credits_par_appel: 960,
  credits_repli_par_appel: 192,
  appels_max: 7,
  credits_estimes: 6720,
  credits_repli_estimes: 1344,
  texte_version: 'gl22-v1-20261024',
  raison: '',
};

test('un 409 consentement_opus_requis rend l’estimation à afficher', () => {
  const err = parseApiError(409, {
    detail: { code: 'consentement_opus_requis', error: 'consentement_opus_requis', message: 'm', estimation },
  });
  assert.deepEqual(readOpusConsentRequest(err), { motif: 'requis', estimation });
});

test('un 409 montant périmé rend la nouvelle estimation', () => {
  const err = parseApiError(409, {
    detail: { code: 'consentement_opus_montant_perime', error: 'consentement_opus_montant_perime', message: 'm', estimation },
  });
  assert.deepEqual(readOpusConsentRequest(err), { motif: 'montant_perime', estimation });
});

test('contrôle négatif : un autre refus n’est pas un consentement à demander', () => {
  assert.equal(readOpusConsentRequest(parseApiError(409, { detail: 'conflit' })), null);
  assert.equal(readOpusConsentRequest(parseApiError(403, { detail: { error: 'feature_not_available' } })), null);
  assert.equal(readOpusConsentRequest(new Error('x')), null);
});

test('accepter envoie le montant affiché, refuser n’en envoie aucun ; les deux envoient la version du texte', () => {
  assert.deepEqual(buildStartBody(4, ['pm', 'architect'], { decision: 'accepte', estimation }), {
    project_id: 4,
    selected_agents: ['pm', 'architect'],
    consentement_opus: 'accepte',
    credits_opus_acceptes: 6720,
    texte_version_opus: OPUS_CONSENT_TEXT_VERSION,
  });
  assert.deepEqual(buildStartBody(4, ['pm'], { decision: 'refuse', estimation }), {
    project_id: 4,
    selected_agents: ['pm'],
    consentement_opus: 'refuse',
    texte_version_opus: OPUS_CONSENT_TEXT_VERSION,
  });
  assert.deepEqual(buildStartBody(4, ['pm']), { project_id: 4, selected_agents: ['pm'] });
});

test('le texte de l’écran dit le coût, le modèle de repli et la portée, en FR et en EN', () => {
  const fr = opusConsentText(estimation, 'fr');
  assert.match(fr.body, /6\s?720 crédits/);
  assert.match(fr.body, /cette exécution/);
  assert.match(fr.refuse, /Sonnet/);
  assert.match(fr.refuseNote, /1\s?344 crédits/);
  const en = opusConsentText(estimation, 'en');
  assert.match(en.body, /6,720 credits/);
  assert.match(en.body, /this run/);
  assert.match(en.refuse, /Sonnet/);
  // Reprise R3 : la version envoyée avec la décision (test précédent) est
  // vérifiée et tracée par le serveur ; l'égalité avec la constante du
  // serveur est testée côté backend (test_la_version_du_texte_du_frontend_
  // est_celle_du_serveur), pas ici contre un littéral.
});

test('le repli annoncé sur l’exécution est lu depuis `degraded`, et seulement lui', async () => {
  const { readOpusFallbackNotices } = await import('../src/lib/opusConsent.ts');
  const progress = {
    degraded: [
      { motif: 'rag_unavailable', detail: 'RAG', at: 't0' },
      { motif: 'opus_repli_sonnet', detail: 'Opus refusé : Marcus est servi par claude-sonnet-5.', at: 't1' },
    ],
  };
  assert.deepEqual(readOpusFallbackNotices(progress), [
    'Opus refusé : Marcus est servi par claude-sonnet-5.',
  ]);
  assert.deepEqual(readOpusFallbackNotices({ degraded: [] }), []);
  assert.deepEqual(readOpusFallbackNotices(null), []);
});
