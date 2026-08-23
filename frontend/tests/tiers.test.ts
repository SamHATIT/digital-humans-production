/**
 * VAGUE 2 — LOT 3 : enums de paliers desalignes cote frontend.
 *
 * Le defaut : `SubscriptionBadge.tsx` connaissait `free | premium | enterprise`
 * alors que le backend sert `free | pro | team | enterprise`
 * (`app/models/subscription.py`). `premium` n'existe plus cote serveur et
 * `team` etait absent de `FeatureGate` : l'UI proposait des actions vouees au
 * 403, et un compte Team etait traite comme un compte inconnu.
 *
 * Le raccrochage demande par l'audit : le palier requis vient du payload de
 * `FeatureAccessError` (`error`, `feature`, `required_tier`, `upgrade_url`),
 * pas d'une constante recopiee a la main.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  TIER_ORDER,
  TIERS,
  hasTier,
  normalizeTier,
  parseFeatureAccessError,
  tierLabel,
} from '../src/lib/tiers.ts';

test('les quatre paliers du backend sont connus', () => {
  assert.deepEqual([...TIERS], ['free', 'pro', 'team', 'enterprise']);
});

test('team est ordonne entre pro et enterprise', () => {
  assert.ok(TIER_ORDER.free < TIER_ORDER.pro);
  assert.ok(TIER_ORDER.pro < TIER_ORDER.team);
  assert.ok(TIER_ORDER.team < TIER_ORDER.enterprise);
});

test('premium est un alias historique de pro, pas un palier', () => {
  // `credit_service._resolve_credit_tier` fait la meme correspondance cote
  // serveur : un compte encore marque `premium` en base est un compte Pro.
  assert.equal(normalizeTier('premium'), 'pro');
  assert.ok(!(TIERS as readonly string[]).includes('premium'));
});

test('un palier inconnu retombe sur free, jamais sur une erreur muette', () => {
  assert.equal(normalizeTier('platine'), 'free');
  assert.equal(normalizeTier(undefined), 'free');
  assert.equal(normalizeTier(null), 'free');
});

test('un compte team a acces a ce qui exige pro', () => {
  // Le defaut concret : `team` absent de la table d'ordre valait `undefined`,
  // la comparaison rendait `false`, et un compte Team se voyait refuser une
  // fonctionnalite Pro par l'UI alors que le backend la lui accordait.
  assert.equal(hasTier('team', 'pro'), true);
  assert.equal(hasTier('team', 'team'), true);
  assert.equal(hasTier('team', 'enterprise'), false);
});

test('un compte pro n a pas acces a ce qui exige team', () => {
  assert.equal(hasTier('pro', 'team'), false);
  assert.equal(hasTier('free', 'pro'), false);
  assert.equal(hasTier('enterprise', 'team'), true);
});

test('un compte encore marque premium a les droits de pro', () => {
  assert.equal(hasTier('premium', 'pro'), true);
  assert.equal(hasTier('premium', 'team'), false);
});

test('les libelles couvrent les quatre paliers', () => {
  assert.equal(tierLabel('free'), 'Free');
  assert.equal(tierLabel('pro'), 'Pro');
  assert.equal(tierLabel('team'), 'Team');
  assert.equal(tierLabel('enterprise'), 'Enterprise');
});

test('le payload de FeatureAccessError est lu tel que le backend l envoie', () => {
  // Forme exacte de `app/utils/feature_access.py:FeatureAccessError`.
  const body = {
    detail: {
      error: 'feature_not_available',
      feature: 'build_phase',
      required_tier: 'team',
      message: "La fonctionnalité 'build_phase' nécessite un abonnement Team",
      upgrade_url: '/pricing',
    },
  };
  const parsed = parseFeatureAccessError(body);
  assert.ok(parsed);
  assert.equal(parsed.feature, 'build_phase');
  assert.equal(parsed.requiredTier, 'team');
  assert.equal(parsed.upgradeUrl, '/pricing');
});

test('un payload deja deballe est accepte', () => {
  const parsed = parseFeatureAccessError({
    error: 'feature_not_available',
    feature: 'sds_document',
    required_tier: 'pro',
    upgrade_url: '/pricing',
  });
  assert.ok(parsed);
  assert.equal(parsed.requiredTier, 'pro');
});

test('une erreur qui n est pas un refus de palier rend null', () => {
  assert.equal(parseFeatureAccessError({ detail: 'Not authorized' }), null);
  assert.equal(
    parseFeatureAccessError({ detail: { error: 'limit_exceeded', limit_name: 'x' } }),
    null,
  );
  assert.equal(parseFeatureAccessError(null), null);
});

test('un required_tier absent du payload retombe sur pro', () => {
  // Le backend n'envoie jamais ce cas, mais un palier inconnu ne doit pas
  // rendre l'invite d'upgrade illisible.
  const parsed = parseFeatureAccessError({
    detail: { error: 'feature_not_available', feature: 'x' },
  });
  assert.ok(parsed);
  assert.equal(parsed.requiredTier, 'pro');
});
