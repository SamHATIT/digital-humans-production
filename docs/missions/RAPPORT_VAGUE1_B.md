# Rapport — Vague 1 / File B — Crédits et Stripe (AS-07)

**Date :** 16/09/2026 · **Branche :** `claude/vague1-b`, depuis
`claude/vague-c-20260906` à `f78e8ad` (PR #11 de la vague 0 fusionnée).
**Mission :** `docs/missions/VAGUE1_B_CREDITS_STRIPE.md`.
**Constats traités :** BILL-01, BILL-04, BILL-08, BILL-09, BILL-10.

> **Environnement — je ne suis pas sur le VPS.** Tout ce qui suit a été joué
> dans un bac à sable Claude Code (Python 3.11, PostgreSQL 16 et Redis
> locaux), avec le bootstrap hermétique de la vague 0. Le réseau sortant est
> refusé par le bac à sable **et** par le bootstrap : **la sandbox Stripe n'a
> pas été appelée**, le CLI Stripe non plus. Voir §6 pour ce qui reste à y
> jouer. Rien n'a été exécuté sur le VPS, aucun service redémarré, aucun
> `backend/.env` touché.

Chaque « fait » ci-dessous est une commande jouée dont la sortie est collée.
Le reste est dit « lu, non exécuté ».

---

## 0. Mesure avant / après (règle 4)

Commande, identique dans les deux cas :

```bash
cd /home/user/wt-vague1-b/backend
export $(cat /root/.dh_test_db.env)
env -u GITHUB_TOKEN ./venv/bin/python -m pytest tests/ -q -p no:cacheprovider
```

| État | Résultat |
|---|---|
| **Avant**, `f78e8ad` (mesuré par moi, pas repris d'un document) | `31 failed, 695 passed, 2 skipped, 7 xfailed in 194.12s` |
| **Après**, `de92267` | `32 failed, 762 passed, 2 skipped, 7 xfailed in 248.70s` |

**+67 verts, +1 rouge.** Les 68 tests que j'ajoute (11 BILL-01, 20 BILL-08,
7 BILL-10, 21 BILL-04, 9 BILL-09) passent tous ; le compte tombe juste :
695 + 68 − 1 = 762.

Comparaison des listes de `FAILED` (`comm` sur les deux listes triées) :

```
=== nouveaux rouges (après \ avant) ===
FAILED tests/test_lot_g_db_sessions.py::test_open_websockets_do_not_pin_connections
=== rouges disparus (avant \ après) ===
(aucun)
```

Le seul rouge nouveau est le test que la vague 0 avait déjà signalé instable
(`RAPPORT_VAGUE0_AS02.md` §0 : 2 échecs / 3 sur la tête de branche, 1 / 3 sur
`abcc04f`). Mesuré par moi sur `de92267`, isolément, trois fois :

```
1 passed, 25 warnings in 7.13s
1 passed, 25 warnings in 6.54s
1 failed, 25 warnings in 6.22s
```

Il est passé dans ma mesure « avant » et a échoué dans ma mesure « après » :
c'est le comportement d'un test instable. **Je n'ai pas re-mesuré son taux
d'échec sur `f78e8ad` lui-même** — je m'appuie sur la mesure de la vague 0 pour
dire qu'il l'était déjà. Non corrigé (hors périmètre, OPS-06).

L'orchestrateur annonçait `32 failed, 694 passed` sur la tête précédente
(`5d35156`). Ma mesure sur `f78e8ad` donne **31 / 695** : l'écart est le test
instable `test_lot_g_db_sessions.py::test_open_websockets_do_not_pin_connections`,
signalé instable par la vague 0, qui est passé dans ma mesure. Les 31 rouges
sont exactement ceux du tableau de la vague 0 :

| Fichier | Rouges | Cause (lue, non corrigée — OPS-06) |
|---|---|---|
| `test_lot_c_injection_commandes.py` | 27 | routeur `agent_tester` commenté dans `app/main.py:147` |
| `test_auth.py` | 3 | inscription sans consentement |
| `test_emma_phase3.py` | 1 | chemin VPS en dur |

Aucun n'a été corrigé ni marqué `xfail`, conformément à la consigne.

---

## 1. Fait, avec preuve

### 1.1 BILL-01 — réservation atomique des crédits

Commits `41343d5` (test rouge) et `6430cc0` (correctif).

**Constat confirmé, mesuré sur PostgreSQL** — 8 débits concurrents acceptés
pour un solde de 7 :

```
assert 8 == (8 - 1)
E   AssertionError: ['ok', 'ok', 'ok', 'ok', 'ok', 'ok', ...]
10 failed, 1 passed, 36 warnings in 5.45s
```

Le test tourne sur la base PostgreSQL de session, **une session SQLAlchemy par
fil**. `tests/test_credit_service.py` utilise un SQLite mémoire, où
`FOR UPDATE` n'est pas rendu : il ne pouvait rien prouver sur l'atomicité.

Correctif — un cycle de vie explicite au journal, toutes les écritures de
`used_credits` sous `SELECT … FOR UPDATE` de la ligne de solde :

| Méthode | Rôle |
|---|---|
| `reserve()` | retient l'estimation **avant** le réseau, ligne `reservation` |
| `settle()` | réécrit la ligne en `charge` au coût **mesuré**, rend le reliquat |
| `release()` | rend tout sur échec, garde une ligne à 0 avec le motif |
| `charge()` | débit direct, même verrou |
| `verify_ledger()` | l'invariant d'Astra : solde = journal |
| `list_pending_reservations()` | réservations non réglées, réconciliables |

Une tentative refusée laisse une ligne `refused` à 0 : « chaque appel d'un
compte produit une ligne » est désormais vrai, y compris pour les refus et les
échecs. Le plafond journalier compte `charge` + `reservation`, donc les appels
en vol. Le routeur réserve, règle, libère ; un repli change de modèle donc de
tarif, sa réservation est reprise.

**Défaut que j'ai moi-même introduit et que le test a trouvé** :
`with_for_update()` rend l'objet déjà présent dans la carte d'identité de la
session sans relire ses colonnes. Le verrou était pris, l'incrément calculé
sur une valeur périmée — 8 réservations concurrentes, une seule comptée.
`populate_existing()` corrige. Ce n'est pas un trophée, c'est une dette payée
avant le commit.

Preuve :

```
env -u GITHUB_TOKEN ./venv/bin/python -m pytest \
  tests/test_vague1_b_bill01_reservation_atomique.py -q -p no:cacheprovider
11 passed, 24 warnings in 7.35s        (avant : 10 failed, 1 passed)
```

Aucune migration : `transaction_type` est un `VARCHAR(20)`, le plus long type
vaut 11 caractères.

### 1.2 BILL-08 — arrondi supérieur, refus des modèles inconnus, opt-in

Commits `9d5cf9e` (test rouge) et `173d88e` (correctif).

Trois volets confirmés :

1. `ROUND_HALF_UP` : `_credits_for_tokens(tarif, 1200, 0)` rendait 1, pas 2
   (`assert 1 == 2`). Corrigé en `ROUND_CEILING`. Un compte rond ne monte pas
   d'un cran (1,0 → 1) ; le moindre dépassement monte (1,001 → 2) ; minimum
   1 crédit dès que le brut est positif ; 0 pour un appel vide.
   **Unité publiée : 1 crédit, par appel.**
2. Repli par sous-chaîne : `DID NOT RAISE UnknownModelError` pour un nom absent
   de `model_pricing` contenant « sonnet ». Correspondance exacte désormais
   exigée ; un `is_active=False` vaut retiré.
3. `requires_opt_in` n'était lu nulle part. Il l'est (`opt_in=` sur
   charge/reserve/preflight) ; l'opt-in s'ajoute au palier, il ne le remplace
   pas.

**Mesure qui a changé la portée du volet 2** — identifiants `model_id` du YAML
croisés avec les lignes créées par les migrations :

```
SERVIS SANS LIGNE DE TARIF : claude-haiku-4-5-20251001, claude-opus-5,
claude-sonnet-5, deepseek-v4-flash-ga-260731, deepseek-v4-pro-ga-260813,
glm-5-3-flash-260828, gpt-4o, gpt-4o-mini, mistral-nemo, mistral:7b-instruct,
mixtral, muse-glimmer
```

Les **trois** modèles Anthropic que le profil `cloud` route n'ont aucune ligne
de tarif : aujourd'hui, chaque appel cloud est facturé par ressemblance sur une
version antérieure, et c'est cette version antérieure qui est écrite dans
`credit_transactions.model_used`. Supprimer le repli sans rien d'autre aurait
donc refusé **tout** appel cloud. D'où la migration **016**, qui ajoute les
alias explicites vers un tarif versionné — tarifs repris à l'identique des
lignes de même famille, aucun changement de prix, seulement un nom exact.

Preuve :

```
env -u GITHUB_TOKEN ./venv/bin/python -m pytest tests/test_credit_service.py \
  tests/test_vague1_b_bill08_arrondi_et_modeles_inconnus.py \
  tests/test_vague1_b_bill01_reservation_atomique.py \
  tests/test_vague_b_b1_credits.py \
  tests/test_vague_b_b1bis_credits_hors_orchestrateur.py \
  tests/test_b2_pricing_nemotron.py -q -p no:cacheprovider
74 passed, 42 warnings in 25.61s       (BILL-08 seul avant : 8 failed, 12 passed)
```

### 1.3 BILL-10 — un seul écrivain du coût USD (partiellement : voir §3)

Commits `66042e4` (test rouge) et `b15dbf9` (correctif de mon périmètre).

Les trois mécanismes, **mesurés** avant tout correctif :

```
apres record_cost (wrapper LLM)     : total_cost = 0.018
apres _track_tokens (orchestrateur) : total_cost = 0.036
cout reel de l'appel                : 0.018
-> l'appel est compte 2 fois

_calculate_cost(10 000 jetons, modele='muse-glimmer')       = $0.066
_calculate_cost(10 000 jetons, modele='nemotron-lightning') = $0.066
_calculate_cost(10 000 jetons, modele='')                   = $0.066

_resolve_pricing('modele-jamais-vu') -> {'input': 3.0, 'output': 15.0}
_resolve_pricing('muse-glimmer')     -> {'input': 3.0, 'output': 15.0}
estimate_cost('muse-glimmer', 1M, 0) -> $3.0
```

Corrigé dans mon périmètre : `_resolve_pricing` ne replie plus sur « default » ;
un modèle local garde un coût **connu et nul** ; tout le reste lève
`UnknownPricingError`. `record_cost(..., cost_usd=)` écrit le coût **mesuré**
quand il est fourni — `0.0` est une mesure, c'est `None` qui veut dire inconnu
(d'où un test `is not None`, jamais un test de vérité). `record_cost` est
déclaré écrivain unique de `executions.total_cost`, et
`llm_service.generate_llm_response` lui transmet le coût du routeur.

```
env -u GITHUB_TOKEN ./venv/bin/python -m pytest \
  tests/test_vague1_b_bill10_cout_usd_ecrit_une_fois.py -q -p no:cacheprovider
7 passed, 31 warnings in 3.76s         (avant : échec à l'import)
```

**Le second écrivain vit chez la file C** : voir §5. Tant que ce diff n'est pas
appliqué, **le double comptage subsiste sur le chemin orchestrateur** — ce
constat reste ouvert, il n'est pas clos par mon commit.

### 1.4 BILL-04 — état Stripe robuste

Commits `4989d47` (test rouge, modèles, migration 017) et `b809dc0` (correctif).

**Trouvé en écrivant le test, et qui change la gravité du constat.** Avec le
SDK installé (`stripe==15.1.0`), l'objet rendu par `construct_event` n'est plus
un dictionnaire :

```
stripe SDK : 15.1.0
type de l'objet       : Subscription
isinstance(obj, dict) : False
hasattr(obj, 'get')   : False
obj.get('customer')   -> AttributeError : get
```

Les quatre gestionnaires faisaient exactement cet appel
(`stripe_service.py:241` et suivants) : **le webhook rendait 500 sur tout
événement réel**, et Stripe rejouait indéfiniment. Ce n'est pas un raffinement
de robustesse — le parcours Pro ne pouvait pas fonctionner. Ce défaut
n'apparaît pas dans l'audit du 06/09 : le rapport est antérieur, et personne
n'avait rejoué d'événement depuis.

Correctif :

- `_en_dict()` normalise l'objet du SDK une fois, en entrée ;
- **idempotence portée par la clé primaire** de `stripe_events` : l'identifiant
  est inséré avant traitement ; un doublon ne s'insère pas, donc ne recharge
  pas. Ce n'est plus un test applicatif qu'on peut oublier ;
- **désordre** : `last_event_created` garde l'horodatage Stripe du dernier
  événement appliqué ; un événement antérieur est refusé (`stale`) ;
- **abonnements multiples** : `reconcilier_palier()` **dérive** le palier de
  l'ensemble des lignes `stripe_subscriptions`. Supprimer un ancien abonnement
  ne rétrograde plus un compte encore payé ; supprimer le dernier rétrograde
  bien (contrôle négatif) ;
- **impayé** : `past_due`/`unpaid` ouvrent une grâce **datée** (`grace_until`,
  5 jours par défaut, `DH_STRIPE_GRACE_IMPAYE_JOURS`). Passée cette date,
  l'accès se ferme sans attendre un `deleted` de Stripe, dont la venue dépend
  d'une configuration de recouvrement non vérifiable côté application ;
- **paiement initial** : allocation posée une seule fois
  (`initial_credits_granted_at`), et le palier est dérivé **avant** la
  recharge. Dans l'autre ordre, le compte était encore Free et recevait 0
  crédit — le symptôme même de « le nouveau Pro peut rester sans crédits ». Le
  test l'a attrapé ;
- **motifs de facturation** : seul `subscription_cycle` recharge. Le
  commentaire disait « seulement subscription_cycle », le code acceptait tout
  sauf `subscription_create` — une facture d'ajustement rechargeait le quota ;
- **file de réconciliation** : price inconnu ou client introuvable ne sont plus
  acquittés en 200 puis perdus ; l'événement est conservé **avec sa charge**,
  lisible par `evenements_a_reconcilier()` ;
- `POST /api/billing/cancel` : `limit=1` n'annulait que le **premier**
  abonnement actif — un client qui en avait deux continuait d'être débité pour
  l'autre. Tous sont annulés.

```
env -u GITHUB_TOKEN ./venv/bin/python -m pytest \
  tests/test_vague1_b_bill04_stripe_robuste.py -q -p no:cacheprovider
21 passed, 54 warnings in 14.72s       (avant : 20 failed, 1 passed)
```

Les événements sont des **charges JSON conformes au format Stripe, signées
avec un secret factice** (`t=…,v1=HMAC-SHA256`) et POSTées sur la vraie route :
c'est le vrai `stripe.Webhook.construct_event` qui vérifie, et le vrai
dispatcher qui traite. Contrôle négatif inclus : une signature invalide est
refusée en 400.

### 1.5 BILL-09 — budget du concierge

Commits `b0eefc4` (test rouge) et `de92267` (correctif).

Mesuré :

```
_calculate_cost('anthropic/claude-sonnet-4-6', 10 000, 2 000) = $0.0
_calculate_cost('anthropic/claude-sonnet',     10 000, 2 000) = $0.06
clés du bloc pricing : anthropic/claude-haiku, anthropic/claude-opus,
                       anthropic/claude-sonnet, local/...
plafond journalier   : 20.0 USD
```

Le fournisseur forcé n'a pas de clé de prix : chaque tour public comptait 0 et
le plafond ne montait jamais.

Correctif :

- `_resoudre_tarif()` : clé exacte → clé dont le `model_id` correspond à la
  forme versionnée → coût **connu et nul** pour un fournisseur local/GPU →
  **refus** (`UnknownProviderPricingError`). Un tarif inconnu ne vaut plus
  zéro. Sur le chemin d'une réponse déjà obtenue, le trou est **crié en
  CRITICAL** au lieu d'être avalé : un appel déjà facturé par le fournisseur ne
  doit pas devenir une erreur côté client ;
- le concierge appelle `anthropic/claude-sonnet`, forme déclarée qui a un tarif
  et résout vers le `model_id` réellement servi ;
- table `concierge_budget_jours` (migration 018) : un total et un nombre de
  tours par jour, **sans aucune donnée personnelle**. `/forget` efface les
  messages du visiteur — c'est son droit — sans pouvoir effacer le garde-fou ;
- **réservation atomique** : `reserver_budget` vérifie et retient sous
  `FOR UPDATE` de la ligne du jour ; `regler_budget` remplace l'estimation par
  le coût mesuré ; `liberer_budget` rend si le tour n'aboutit pas ;
- **plafond de tours par jour** (`MAX_REQUETES_JOUR`) : « un coût monétaire nul
  n'est pas une capacité infinie ».

```
env -u GITHUB_TOKEN ./venv/bin/python -m pytest \
  tests/test_vague1_b_bill09_budget_concierge.py -q -p no:cacheprovider
9 passed, 25 warnings in 3.00s         (avant : échec à l'import)
```

### 1.6 DEC-2026-0809-10 — carte bancaire à l'inscription Free

Décision de Sam non prise (attendue avant le 22/09). Les **deux chemins**
existent dans `stripe_service` derrière `DH_FREE_SIGNUP_REQUIRES_CARD` et sont
testés : drapeau faux = client Stripe seul (comportement actuel) ; drapeau vrai
= session Checkout en mode `setup`, qui recueille une carte sans la débiter.
Une valeur non reconnue vaut **faux** : elle ne tombe pas dans la branche
permissive. Le branchement du parcours d'inscription est un diff non commis
(§5).

---

## 2. Non confirmé / ce qui s'est révélé différent du rapport

- **Le chiffre de référence.** L'orchestrateur annonçait `32 failed, 694
  passed` ; la mesure sur `f78e8ad` donne `31 failed, 695 passed`. L'écart est
  le test instable déjà signalé par la vague 0, pas une régression.
- **BILL-08 volet « modèles inconnus » est plus grave que décrit.** L'audit dit
  « un nouveau modèle *pourrait* être tarifé au tarif d'une ancienne version ».
  La mesure montre que c'est le cas **pour la totalité du trafic cloud
  actuel** : aucun des trois `model_id` servis n'a de ligne de tarif.
- **BILL-04 est plus grave que décrit.** L'audit décrit une fragilité aux
  événements désordonnés. La mesure montre que le webhook **ne traite aucun
  événement** avec le SDK installé (`AttributeError: get`). L'audit du 06/09 ne
  pouvait pas le voir sans rejouer un événement.
- **Rien n'est infirmé.** Les cinq constats de ma file sont tous confirmés par
  la mesure. Je n'ai pas de constat réfuté à déclarer — ce qui est en soi une
  information : l'audit du 06/09 était juste sur ces cinq points, et en-dessous
  de la réalité sur deux.

---

## 3. Reste ouvert

- **BILL-10, moitié orchestrateur.** Le double comptage subsiste tant que la
  file C n'a pas appliqué le diff de §5. Mon correctif rend l'écrivain unique
  correct ; il ne supprime pas le second écrivain, qui n'est pas à moi.
- **`requires_opt_in` d'Opus — décision de Sam.** La migration 016 pose
  `requires_opt_in = false` sur `claude-opus-5`. Raison : la migration 010 a
  ouvert Opus au palier Pro pour Marcus, le produit n'a **aucun** recueil de
  consentement, et le profil `cloud` route l'orchestrateur en Opus — laisser
  `true` refuserait toute exécution Pro et Team. Le mécanisme existe désormais
  et est testé : **une ligne de SQL suffit à l'exiger de nouveau** le jour où
  un consentement explicite existe. Les lignes héritées `claude-opus-4-7`
  gardent `true` et ne sont plus servies.
- **Modèles locaux/GPU sans tarif.** `muse-glimmer`, `deepseek-v4-*`,
  `glm-5-3-*`, `gpt-4o*`, `mistral*` n'ont de ligne dans aucune migration
  (elles ont été ajoutées à la main sur le VPS le 15/09 — GL-08). Ils sont
  désormais **refusés** au lieu d'être mal tarifés, ce qui est l'objet du
  correctif. **À trancher avant de repasser sur un profil GPU** :
  `nemotron-lightning` (parcours Free) est tarifé depuis la migration 014 et
  n'est pas concerné.
- **Migrations non appliquées sur une vraie base.** 016, 017 et 018 n'ont pas
  été jouées par `alembic upgrade` : la suite de tests crée son schéma par
  `Base.metadata.create_all`. Les modèles et les migrations disent la même
  chose, mais je ne l'ai pas *exécuté* — à jouer sur le VPS, en préproduction
  d'abord. Ce qui **a** été exécuté, c'est la cohérence de la chaîne :

  ```
  $ ./venv/bin/python -m alembic heads
  018_budget_concierge (head)
  $ ./venv/bin/python -m alembic history | head -3
  017_etat_stripe_persiste -> 018_budget_concierge (head), Budget opérationnel du concierge…
  016_tarifs_modeles_servis -> 017_etat_stripe_persiste, État Stripe persisté…
  015_free_50_credits_jour -> 016_tarifs_modeles_servis, Tarifs des modèles réellement servis…
  ```

  Une seule tête, pas de branche parallèle créée par mes trois migrations.
- **`stripe_events.payload`** conserve la charge brute, qui peut contenir un
  email de client. Rétention à décider avec RGPD-01 ; je ne l'ai pas tranchée.
- **31 rouges antérieurs** (§0), non corrigés, non marqués `xfail`.

---

## 4. Non fait, et pourquoi (choix, pas reliquat)

- **BILL-02, BILL-03, BILL-05, BILL-06, BILL-07, BILL-11** : hors de ma file.
  Le critère de sortie citait « le paiement initial crédite », qui relève de
  BILL-03 : cette partie-là est faite (§1.4), pas le reste de BILL-03.
- **Aucun appel à la sandbox Stripe** : réseau sortant refusé par le bac à
  sable et par le bootstrap hermétique. J'ai rejoué des webhooks signés plutôt
  que de prétendre l'avoir fait. §6 liste ce qui reste.
- **Pas de réécriture de `tests/test_credit_service.py` vers PostgreSQL** : il
  reste sur SQLite mémoire. Les preuves de concurrence vivent dans un fichier
  dédié qui tourne sur la base de session ; réécrire l'existant aurait mélangé
  le correctif et un déménagement de fixtures.
- **Pas d'installation de dépendance** : le venv est partagé par les quatre
  agents. Aucune dépendance ne manque — `stripe==15.1.0` est déjà dans
  `requirements.txt` et installé.
- **Pas de correction des 31 rouges antérieurs**, consigne explicite.

---

## 5. Diffs non commis, destinés à d'autres files

Les deux fichiers sont dans `docs/missions/diffs-vague1-b/` et **commis en tant
que documents**, pas appliqués au code.

| Diff | Destinataire | Objet |
|---|---|---|
| `BILL10-file-C-orchestrateur.diff` | **File C** | Retirer le second écrivain de `executions.total_cost` dans `pm_orchestrator_service_v2.py` (7 appelants listés, 2 à conserver pour les compteurs de jetons, 5 à retirer). Sans lui, BILL-10 reste à moitié ouvert. |
| `DEC-0809-10-inscription-free-carte.diff` | **File parcours** | Brancher `preparer_inscription_free()` dans `auth.py`. À n'appliquer que si Sam répond « oui » avant le 22/09 ; sinon il n'y a rien à faire, le drapeau vaut faux. |

Je n'ai touché ni `pm_orchestrator_service_v2.py`, ni `app/workers/*`, ni
`app/api/routes/orchestrator/*`.

**Fichiers partagés que j'ai modifiés sans être nommé intégrateur** —
`llm_router_service.py`, `budget_service.py`, `llm_service.py`,
`sophie_concierge_service.py`, `billing.py` : tous sont des **emplacements
explicites de mes constats** dans le rapport Astra (BILL-01, BILL-09, BILL-10,
BILL-04). Aucun n'est attribué à une autre file par la mission. Je le signale
pour que la fusion en tienne compte.

---

## 6. Ce qui reste à jouer sur la sandbox Stripe du VPS

**La sandbox Stripe n'a pas été appelée.** Les gestionnaires sont prouvés
contre des webhooks signés rejoués ; ce qui suit demande un vrai Stripe et doit
être joué avant l'ouverture du Pro :

1. **Checkout réel de bout en bout** : `POST /api/billing/checkout` → page
   hébergée → carte de test → vérifier que `customer.subscription.created`
   arrive, que le palier passe Pro et que les 15 000 crédits sont posés **une
   fois**.
2. **Renouvellement** : forcer un cycle (`stripe trigger
   invoice.payment_succeeded` avec `billing_reason=subscription_cycle`) et
   vérifier une seule ligne `reset`.
3. **Rejeu réel** : « Resend » du même événement depuis le tableau de bord
   Stripe → la réponse doit porter `duplicate: true`, aucun crédit ajouté.
4. **Désordre réel** : livrer un `updated` ancien après un `updated` récent
   (Stripe CLI, `--webhook-endpoint`) → `stale: true`, état inchangé.
5. **Impayé** : carte `4000 0000 0000 0341`, laisser la relance échouer →
   vérifier `grace_until` posé, puis que l'accès se ferme à l'échéance sans
   attendre `deleted`.
6. **Abonnements multiples** : deux Checkout successifs pour le même client →
   vérifier que le palier retenu est le plus élevé et que
   `POST /api/billing/cancel` les annule **tous**.
7. **Price inconnu** : créer un prix hors `STRIPE_PRICE_ID_*` → l'événement
   doit finir en `pending_reconciliation` avec sa charge, et non acquitté et
   perdu.
8. **Rotation du secret de webhook** : non vérifiable ici (l'audit le disait
   déjà) ; à vérifier chez le fournisseur.
9. **Migrations** : `alembic upgrade head` (016, 017, 018) en préproduction,
   puis contrôler que `model_pricing` porte bien les trois `model_id` servis.
10. **Vérification d'ensemble après 9** : sur une exécution réelle, comparer
    `executions.total_cost` à la somme des `cost_usd` des `llm_interactions` —
    ils doivent être égaux une fois le diff de la file C appliqué.

---

## 7. Tableau, constat par constat

| Constat | État | Preuve | Reste |
|---|---|---|---|
| **BILL-01** réservation atomique | ✅ corrigé | `11 passed` (avant `10 failed, 1 passed`), 8 débits pour 7 crédits mesurés sur PostgreSQL | — |
| **BILL-04** état Stripe | ✅ corrigé | `21 passed` (avant `20 failed, 1 passed`) ; webhooks signés rejoués | sandbox VPS (§6) |
| **BILL-08** arrondi + modèles inconnus | ✅ corrigé | `74 passed` sur les 6 suites de crédits ; migration 016 | opt-in Opus à trancher (§3) |
| **BILL-09** budget concierge | ✅ corrigé | `9 passed` ; `$0.0` → tarif résolu, budget ineffaçable, réservation sous verrou | — |
| **BILL-10** coût USD | 🟡 moitié | `7 passed` ; double comptage 0.018→0.036 mesuré | diff file C (§5) |
| **DEC-0809-10** carte Free | ✅ deux chemins | 3 tests, valeur inconnue = faux | décision Sam + branchement (§5) |

---

## 8. Commits de la branche

| Commit | Objet |
|---|---|
| `41343d5` | test rouge BILL-01 — `10 failed, 1 passed` |
| `6430cc0` | fix BILL-01 — réservation atomique sous verrou |
| `9d5cf9e` | test rouge BILL-08 — `8 failed, 12 passed` |
| `173d88e` | fix BILL-08 — `ROUND_CEILING`, refus des inconnus, opt-in, migration 016 |
| `66042e4` | test rouge BILL-10 — double comptage et coût local fictif mesurés |
| `b15dbf9` | fix BILL-10 (périmètre B) — écrivain unique, zéro ≠ inconnu, + diff file C |
| `4989d47` | test rouge BILL-04 — `20 failed, 1 passed` ; modèles + migration 017 |
| `b809dc0` | fix BILL-04 — état persisté, idempotent, ordonné, grâce datée |
| `b0eefc4` | test rouge BILL-09 — `$0.0` mesuré sur le fournisseur forcé |
| `de92267` | fix BILL-09 — tarif résolu, budget ineffaçable, réservation atomique, migration 018 |
| _(docs)_ | ce rapport et les deux diffs non commis |
