/**
 * VAGUE 1 / file D — BILL-07 : « prix correct, produit vendu incorrect ».
 *
 * Constat d'Astra (rapport du 06/09, L733), re-mesure le 16/09 sur `f78e8ad` :
 * `Pricing.tsx` lit bien prix et credits depuis `/api/subscription/tiers`,
 * mais la table de comparaison est une constante `FEATURES` ecrite a la main
 * qui **contredit** la matrice du serveur (`app/models/subscription.py`) :
 *
 *   | ligne affichee                    | page      | serveur (TIER_FEATURES) |
 *   |-----------------------------------|-----------|-------------------------|
 *   | Free · extraction des BR          | incluse   | br_extraction: False    |
 *   | Free · document SDS Word/PDF      | incluse   | sds_document: False     |
 *   | Free · projets max                | 1         | max_projects: 0         |
 *   | Pro  · phase BUILD                | incluse   | build_phase: False      |
 *   | Pro  · deploiement SFDX           | incluse   | sfdx_deployment: False  |
 *   | Pro  · integration Git            | incluse   | git_integration: False  |
 *   | Team · projets                    | illimites | max_projects: 100       |
 *   | Team · templates personnalises    | inclus    | custom_templates: False |
 *
 * Et `formatCredits(undefined)` affichait **« Illimité »** quand l'appel API
 * echouait : le pire affichage possible sur une donnee absente.
 *
 * Ce module porte la lecture ; `Pricing.tsx` ne fait plus que rendre.
 *
 *   node --experimental-strip-types --test frontend/tests/tierFeatures.test.ts
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  FEATURE_GROUPS,
  featureValue,
  formatCredits,
  formatLimit,
  formatPrice,
  type PublicTierLike,
} from '../src/lib/tierFeatures.ts';

const FREE: PublicTierLike = {
  tier: 'free',
  name: 'Free',
  price_eur_monthly: 0,
  credits: 50,
  credits_period: 'day',
  features: {
    chat_sophie: true,
    chat_olivia: true,
    chat_full_team: false,
    br_extraction: false,
    sds_document: false,
    build_phase: false,
    max_projects: 0,
    max_brs_per_project: 0,
  },
  limitations: ['Chat avec Sophie et Olivia uniquement'],
};

const TEAM: PublicTierLike = {
  tier: 'team',
  name: 'Team',
  price_eur_monthly: 1490,
  credits: 100000,
  credits_period: 'month',
  features: { build_phase: true, max_projects: 100, custom_templates: false },
  limitations: [],
};

const ILLIMITE: PublicTierLike = {
  ...TEAM,
  tier: 'enterprise',
  features: { ...TEAM.features, max_projects: null },
};

// ─────────────────────────────────────────────────────────────────────
// 1. Donnee absente : jamais « illimite »
// ─────────────────────────────────────────────────────────────────────

test('un tier absent de la reponse API n affiche pas « Illimité »', () => {
  // Le defaut exact de BILL-07 : sur erreur de chargement, la page annoncait
  // des credits illimites. C'est la promesse la plus chere possible sur une
  // valeur qu'on n'a pas.
  for (const langue of ['fr', 'en'] as const) {
    const rendu = formatCredits(undefined, langue);
    assert.doesNotMatch(rendu.toLowerCase(), /illimit|unlimited/);
  }
  assert.match(formatCredits(undefined, 'fr').toLowerCase(), /indisponible/);
  assert.match(formatCredits(undefined, 'en').toLowerCase(), /unavailable/);
});

test('des credits nuls dans la reponse ne deviennent pas « Illimité »', () => {
  const casse: PublicTierLike = { ...FREE, credits: null, credits_period: null };
  assert.doesNotMatch(formatCredits(casse, 'fr').toLowerCase(), /illimit/);
});

test('les credits presents sont rendus avec leur rythme', () => {
  assert.match(formatCredits(FREE, 'fr'), /50/);
  assert.match(formatCredits(FREE, 'fr'), /jour/);
  assert.match(formatCredits(TEAM, 'fr'), /mois/);
});

test('un prix absent reste « sur devis », jamais zero', () => {
  assert.match(formatPrice(undefined, 'fr').toLowerCase(), /devis/);
  assert.match(formatPrice(undefined, 'en').toLowerCase(), /request/);
  assert.match(formatPrice(TEAM, 'fr'), /1\s?490/);
});

// ─────────────────────────────────────────────────────────────────────
// 2. La matrice affichee vient du serveur
// ─────────────────────────────────────────────────────────────────────

test('chaque ligne du tableau nomme une cle de la matrice serveur', () => {
  const cles = FEATURE_GROUPS.flatMap((g) => g.items.map((i) => i.key));
  assert.ok(cles.length >= 8, 'tableau de comparaison vide');
  assert.equal(new Set(cles).size, cles.length, 'cle dupliquee dans le tableau');
  for (const cle of cles) {
    assert.match(cle, /^[a-z][a-z0-9_]*$/, `cle non canonique : ${cle}`);
  }
});

test('le Free ne se voit pas attribuer le SDS ni la phase BUILD', () => {
  // Les deux lignes que la page affichait comme incluses alors que le serveur
  // les refuse. Sans ce test, on republierait la meme promesse.
  assert.equal(featureValue(FREE, 'sds_document'), false);
  assert.equal(featureValue(FREE, 'br_extraction'), false);
  assert.equal(featureValue(FREE, 'build_phase'), false);
});

test('le Pro ne se voit pas attribuer BUILD, SFDX ni Git', () => {
  const pro: PublicTierLike = {
    ...TEAM,
    tier: 'pro',
    features: { build_phase: false, sfdx_deployment: false, git_integration: false },
  };
  assert.equal(featureValue(pro, 'build_phase'), false);
  assert.equal(featureValue(pro, 'sfdx_deployment'), false);
  assert.equal(featureValue(pro, 'git_integration'), false);
});

test('une cle absente de la reponse n est pas rendue comme incluse', () => {
  // Fail closed : afficher « inclus » sur une cle inconnue ferait proposer une
  // action que le backend refusera en 403.
  assert.equal(featureValue(FREE, 'cle_inconnue'), false);
  assert.equal(featureValue(undefined, 'build_phase'), false);
});

// ─────────────────────────────────────────────────────────────────────
// 3. Limites : distinguer « illimite » de « inconnu »
// ─────────────────────────────────────────────────────────────────────

test('une limite numerique est rendue telle quelle', () => {
  assert.equal(formatLimit(TEAM, 'max_projects', 'fr'), '100');
  assert.equal(formatLimit(FREE, 'max_projects', 'fr'), '0');
});

test('une limite explicitement nulle est « illimité », une limite absente ne l est pas', () => {
  // La distinction que BILL-07 reclame : `max_projects: null` cote serveur veut
  // bien dire « sans plafond » ; une cle absente veut dire « on ne sait pas ».
  assert.match(formatLimit(ILLIMITE, 'max_projects', 'fr').toLowerCase(), /illimit/);
  assert.doesNotMatch(formatLimit(FREE, 'cle_absente', 'fr').toLowerCase(), /illimit/);
  assert.match(formatLimit(undefined, 'max_projects', 'fr').toLowerCase(), /indisponible/);
});
