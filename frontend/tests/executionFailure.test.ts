/**
 * VAGUE 1 / file D — BILL-11 : « le refus de credits reste invisible dans le
 * parcours reellement utilise » (Astra L807).
 *
 * Mesure du 16/09 sur `f78e8ad` : la route
 * `GET /api/pm-orchestrator/execute/{id}/progress` sert bien un champ
 * `failure_reason` — cable par le lot B1-bis, avec son test
 * (`test_vague_b_b1_credits.py::test_la_route_de_progression_rend_le_motif_du_refus`)
 * — mais `useExecutionStream` ne le lit pas, et
 * `ExecutionMonitoringPage` propose toujours « Rejouer l'acte ». Un client
 * dont les credits sont epuises rejoue donc une action impossible, sans
 * jamais lire pourquoi.
 *
 *   node --experimental-strip-types --test frontend/tests/executionFailure.test.ts
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  CODE_CREDITS_INSUFFISANTS,
  canRetryExecution,
  readFailureReason,
} from '../src/lib/executionFailure.ts';

// ─────────────────────────────────────────────────────────────────────
// BILL-11 — le refus de credits est lisible et ne propose pas de rejouer
// ─────────────────────────────────────────────────────────────────────

test('le motif d echec sert par /progress est lu', () => {
  const motif = readFailureReason({
    status: 'failed',
    failure_reason: {
      code: 'insufficient_credits',
      message: 'Credits insuffisants : palier free, 50 credits/jour.',
    },
  });
  assert.ok(motif);
  assert.equal(motif.code, CODE_CREDITS_INSUFFISANTS);
  assert.match(motif.message, /free/);
});

test('aucun motif invente quand le backend n en donne pas', () => {
  // Le backend rend `failure_reason: null` tant que la cause n'est pas
  // reconnue — c'est voulu (regle 6). Le frontend ne doit pas combler.
  assert.equal(readFailureReason({ status: 'failed', failure_reason: null }), null);
  assert.equal(readFailureReason({ status: 'failed' }), null);
  assert.equal(readFailureReason(null), null);
});

test('un refus de credits ne propose pas de rejouer', () => {
  const progress = {
    status: 'failed',
    failure_reason: { code: 'insufficient_credits', message: 'Credits insuffisants.' },
  };
  assert.equal(canRetryExecution(progress), false);
});

test('un echec pour une autre cause reste rejouable', () => {
  // Controle negatif : sans lui, un correctif qui masquerait toujours le
  // bouton passerait le test precedent tout en cassant le rattrapage d'un
  // timeout, qui est legitimement rejouable.
  assert.equal(canRetryExecution({ status: 'failed', failure_reason: null }), true);
  assert.equal(
    canRetryExecution({
      status: 'failed',
      failure_reason: { code: 'llm_timeout', message: 'Delai depasse.' },
    }),
    true,
  );
});

test('une execution qui n a pas echoue ne propose pas de rejouer', () => {
  assert.equal(canRetryExecution({ status: 'running' }), false);
  assert.equal(canRetryExecution({ status: 'completed' }), false);
  assert.equal(canRetryExecution(null), false);
});
