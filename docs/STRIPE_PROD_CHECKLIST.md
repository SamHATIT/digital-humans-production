# STRIPE-004 — Checklist bascule mode test → prod

> Document de pilotage pour la bascule Stripe test → live. À exécuter
> uniquement quand la décision business d'ouvrir Pro/Team publiquement
> est prise. **Aujourd'hui (2 mai 2026) on reste en mode test.**

---

## État actuel (test)

| Variable .env | Valeur | Note |
|---|---|---|
| `STRIPE_SECRET_KEY` | `sk_test_…` | Sandbox |
| `STRIPE_PUBLISHABLE_KEY` | `pk_test_…` | Sandbox |
| `STRIPE_WEBHOOK_SECRET` | `whsec_…` | Webhook test |
| `STRIPE_PRICE_ID_PRO` | `price_test_…` | Pro 49€/mois (test) |
| `STRIPE_PRICE_ID_TEAM` | `price_test_…` | Team 1490€/mois (test) |

Conditions commerciales validées (mémoire 29 avr) :
- 1.5% + 0.25€ par carte EEA
- 2.5% + 0.25€ par carte UK
- 0€ frais fixes (setup, mensuel)
- Renégociation possible au-delà de ~80k€/mois de volume

---

## Checklist exécution (à dérouler en séance dédiée)

### Étape 1 — Préparer le compte Stripe live (côté Sam, 15-30 min)

- [ ] Compléter l'activation du compte Stripe live (si pas encore fait) :
  IBAN, justificatif d'identité, justificatif d'adresse, formulaire fiscal
- [ ] Vérifier que l'activation est validée (mail Stripe + dashboard sans
  bandeau d'activation)
- [ ] Vérifier les conditions commerciales appliquées (Settings → Pricing) :
  EEA 1.5% + 0.25€, UK 2.5% + 0.25€

### Étape 2 — Créer les produits live (côté Sam, ~10 min)

- [ ] Dashboard Stripe → toggle **View live data** (top-left)
- [ ] Products → Create product :
  - Nom : "Digital Humans Pro"
  - Description : "5 000 crédits / mois · 5 projets · SDS + BUILD · Git, SFDX, support prioritaire"
  - Pricing : 49.00 EUR · Recurring · Monthly
  - Statement descriptor : "DIGITAL HUMANS PRO"
  - **Noter le `price_id` live** (commence par `price_…`, sans `_test_`)
- [ ] Products → Create product :
  - Nom : "Digital Humans Team"
  - Description : "50 000 crédits / mois · projets illimités · multi-env · workspaces partagés"
  - Pricing : 1490.00 EUR · Recurring · Monthly
  - Statement descriptor : "DIGITAL HUMANS TEAM"
  - **Noter le `price_id` live**

### Étape 3 — Configurer le Customer Portal live (côté Sam, ~5 min)

- [ ] Dashboard Stripe (live) → Settings → Customer Portal
- [ ] Activer le portal
- [ ] Cocher : update payment method, view invoices, cancel subscription
- [ ] Allow plan changes : oui (Pro ↔ Team)
- [ ] Branding : logo Digital Humans, couleur ink/brass
- [ ] Save

### Étape 4 — Créer le webhook live (côté Sam, ~5 min)

- [ ] Dashboard Stripe (live) → Developers → Webhooks → Add endpoint
- [ ] Endpoint URL : `https://app.digital-humans.fr/api/billing/webhook`
- [ ] Events à écouter (cocher exactement ces 5) :
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_succeeded`
  - `invoice.payment_failed`
- [ ] **Noter le `webhook_secret` live** (`whsec_…`)

### Étape 5 — Mise à jour `.env` (côté Claude, ~2 min)

- [ ] Backup `.env` :
  ```bash
  cp /root/workspace/digital-humans-production/backend/.env \
     /root/workspace/digital-humans-production/backend/.env.backup-pre-stripe-live-$(date +%Y%m%d)
  ```
- [ ] Remplacer dans `.env` :
  ```env
  STRIPE_SECRET_KEY=sk_live_<NOUVELLE_VALEUR>
  STRIPE_PUBLISHABLE_KEY=pk_live_<NOUVELLE_VALEUR>
  STRIPE_WEBHOOK_SECRET=whsec_<NOUVELLE_VALEUR>
  STRIPE_PRICE_ID_PRO=price_<PRO_ID_LIVE>
  STRIPE_PRICE_ID_TEAM=price_<TEAM_ID_LIVE>
  ```
- [ ] Vérifier qu'aucune valeur `sk_test_` ou `price_test_` ne traîne
- [ ] `systemctl restart digital-humans-backend`
- [ ] Vérifier dans les logs : pas d'erreur d'init Stripe

### Étape 6 — Activer Mod 24 dans le frontend (côté Claude, ~5 min)

Dans `frontend/src/pages/Pricing.tsx`, fonction `handleCta` :
- [ ] Pour Pro : remplacer `setShowProModal(true);` par `startStripeCheckout('pro');`
- [ ] Pour Team : remplacer le bloc mailto par
  `if (tier === 'team') { startStripeCheckout('team'); return; }`
- [ ] Le composant ProModal et l'état `showProModal` peuvent être conservés
  comme fallback (si on veut le réactiver pour annoncer un changement)
- [ ] Build + déploiement frontend :
  ```bash
  cd frontend && npm run build
  rsync -av --delete dist/ /var/www/app-studio/
  ```

### Étape 7 — Validation E2E live (côté Sam, ~15 min)

- [ ] Ouvrir https://app.digital-humans.fr/pricing en navigation privée
- [ ] Cliquer "S'abonner" sur Pro avec un compte test propre
- [ ] Compléter le checkout avec une carte de test Stripe (`4242 4242 4242 4242`)
- [ ] Vérifier la redirection vers `/billing/success`
- [ ] Vérifier dans Stripe live que la subscription apparaît
- [ ] Vérifier en DB :
  ```sql
  SELECT id, email, subscription_tier, stripe_customer_id
  FROM users WHERE email = '<test_email>';
  -- subscription_tier doit être 'pro'
  ```
- [ ] Vérifier les crédits :
  ```sql
  SELECT user_id, included_credits, used_credits, last_reset_at
  FROM credit_balances WHERE user_id = <test_user_id>;
  -- included_credits doit être 5000
  ```
- [ ] Vérifier dans les logs que le webhook a bien handle l'event :
  ```bash
  journalctl -u digital-humans-backend -n 200 | grep -E "stripe|subscription"
  ```
- [ ] Tester le portal : depuis le compte, cliquer "Manage subscription"
  → Stripe Customer Portal → cancel → vérifier que `subscription_tier`
  redescend à 'free' au moment du `subscription.deleted` event

### Étape 8 — Communication & monitoring (~15 min)

- [ ] Annoncer l'ouverture publique aux beta-testeurs (newsletter / Slack)
- [ ] Activer alerting Stripe : Dashboard → Settings → Notifications →
  cocher payment failures + chargebacks
- [ ] Programmer pour J+7 : passer en revue le funnel d'acquisition
  (visites pricing → conversions → churn) pour calibrer les ajustements

---

## Rollback rapide (en cas de problème post-bascule)

Si quelque chose casse en live, retour test en 2 min :

1. `cp backend/.env.backup-pre-stripe-live-<date> backend/.env`
2. Inverser le swap Mod 24 dans `Pricing.tsx` (commit revert)
3. `systemctl restart digital-humans-backend`
4. Build frontend + redéploiement
5. Désactiver le webhook live dans Stripe dashboard
6. Investiguer offline avec les logs

---

## Notes & garde-fous

- Les `price_id` test ne sont **PAS** valides en live (et inversement).
  Toute transaction live avec un `price_test_` échouera.
- Stripe ne migre pas automatiquement les Customer entre test et live.
  Les utilisateurs existants en test n'auront pas de Customer live tant
  qu'ils n'auront pas refait un checkout.
- La rotation des secrets Stripe doit être faite **avant** le passage live :
  les `sk_test_` exposés (ex: dans des logs) ne sont pas dangereux en
  prod live mais à hygiéniser quand même.
- Le webhook `journal/rebuild` Ghost et le webhook `billing/webhook`
  Stripe sont indépendants (pas de conflit de routing nginx).

---

## Suivi

| Date | Étape | Statut | Note |
|---|---|---|---|
| 2026-05-02 | Code STRIPE-001 + STRIPE-002 + Mod 24 prêts | ✅ | Mode test, boutons "Bientôt" |
| TBD | Étapes 1-4 (côté Stripe Dashboard) | ⏳ | Décision business attendue |
| TBD | Étapes 5-7 (côté code + valid live) | ⏳ | |
| TBD | Étape 8 (communication) | ⏳ | |

