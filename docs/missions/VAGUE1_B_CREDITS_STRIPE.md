# Mission Claude Code — Vague 1 / File B — Crédits et Stripe (AS-07)

**Date de rédaction :** 16/09/2026 · **Fenêtre :** 18 → 22/09 · **Branche :** `claude/vague1-b` · **Préalable :** vague 0 (AS-02) fusionnée.

## Lis d'abord
1. `docs/audit-20260906/rapport-astra.md` — les constats ci-dessous, aux lignes indiquées. C'est la commande ; les emplacements y sont précis.
2. `docs/BACKLOG_GOLIVE_2026-10-01.md` — §1 (calibration), §2 (go-live), §4 (plan).
3. `docs/missions/RAPPORT_VAGUE0_AS02.md` — comment lancer la suite en sécurité.

## Constats de la file
| Constat | Ligne | Titre | Gravité | Effort |
|---|---|---|---|---|
| **BILL-01** | L633 | Les crédits ne sont pas réservés atomiquement : dépassements et lignes perdues | bloquant | 14–22 h |
| **BILL-04** | L683 | L’état Stripe n’est pas robuste aux événements désordonnés, impayés et abonnements multiples | bloquant Pro | 10–16 h |
| **BILL-08** | L754 | L’arrondi n’est pas un plafond supérieur et les modèles inconnus sont tarifés par ressemblance | majeur ; règle à stabiliser avant la première facture | 3–5 h |
| **BILL-09** | L777 | Le budget public du concierge est calculé à zéro et peut être effacé | bloquant si le concierge reste public | 4–6 h |
| **BILL-10** | L793 | Les coûts USD sont écrits plusieurs fois et le local reçoit un coût fictif | majeur | 4–6 h |

## Objectif — critère de sortie d'Astra
> Solde = journal ; la concurrence ne dépasse pas les plafonds ; le paiement initial crédite ; doublon/désordre ne recharge pas deux fois ; impayé traité explicitement.

## Contexte mesuré 15-16/09
- `model_pricing` : lignes ajoutées à la main le 15/09 pour la calibration (`muse-glimmer`, `qwen38`, `gpt-oss-120b`, `deepseek-v4-*`, `glm-5-3-flash-260828`, palier team). BILL-08 « modèles inconnus tarifés par ressemblance » est donc un vrai risque : un modèle servi non listé doit être **refusé**, pas tarifé au plus proche.
- `credit_balances` du compte admin (user 2) initialisé à 100 000 le 15/09 (était 0 avec un palier Team) : la création d'un compte ne pose pas le solde du palier — à vérifier et à corriger si confirmé.
- Sandbox Stripe paramétrée avant la sortie du Pro (Sam, 16/09) : utilise-la pour BILL-04 (événements désordonnés, impayés, abonnements multiples) avec le CLI Stripe ou des webhooks rejoués. Aucun test contre le compte Stripe live.
- **Décision Sam en attente (avant le 22/09) : carte bancaire à l'inscription Free ou non** (DEC-2026-0809-10). Code les deux chemins derrière un drapeau de configuration, testés tous les deux ; ne présume pas.

## Ordre conseillé
BILL-01 (réservation atomique, 14-22 h, le plus long — commence par lui) → BILL-08 (refus des modèles inconnus, plafond supérieur) → BILL-10 (coût USD écrit une fois, local à 0 réel) → BILL-04 (Stripe) → BILL-09 (si le concierge reste ouvert ; sinon l'écrire « non fait, concierge fermé »).

## Tests attendus
Concurrence : N appels simultanés avec un solde pour N-1 → exactement N-1 réussissent, la ligne perdante est journalisée, le solde = somme du journal. Stripe : webhook rejoué deux fois → un seul crédit ; événements dans le désordre → état final correct ; impayé → statut explicite et accès fermé.


## Règles (chacune vient d'un incident daté — `dh-discipline-de-preuve`)
1. Distinguer « exécuté » de « lu ». Livrer commandes et sorties, pas des conclusions.
2. Lire l'assertion, pas la couleur du test.
3. Test rouge avant correctif ; contrôle négatif quand le correctif discrimine deux cas.
4. Mesurer la référence (état de la suite, comportement actuel) avant de partir d'un chiffre du rapport — le rapport date du 06/09, des choses ont bougé (SEC-01/02 fermés, phase 5 réparée le 15/09, secrets purgés le 16/09).
5. `grep` les appelants avant de proposer une architecture : une route sans appelant se démonte.
6. Jamais de repli silencieux : valeur inconnue refusée, service injoignable = échec explicite.
7. Un défaut trouvé n'est pas un trophée.

## Cadre commun de la vague 1
- **Préalable absolu** : la vague 0 (AS-02, environnement de correction sûr) est fusionnée. Lance la suite uniquement avec `TEST_DATABASE_URL` sur une base jetable. Jamais sur `digital_humans_db`.
- Une branche par file : `claude/vague1-<file>` depuis `claude/vague-c-20260906`. Un commit par correctif (défaut, cause, correctif, preuve exécutée, en français). PR ouverte, pas de fusion.
- **Fichiers partagés entre files** — un seul intégrateur : `backend/app/services/pm_orchestrator_service_v2.py` et `backend/app/workers/*` → file **C** ; `backend/app/services/credit*` et `stripe*` → file **B** ; `backend/app/api/routes/orchestrator/*` → file **C** pour la reprise, **D** pour les contrats d'API ; si tu dois toucher un fichier d'une autre file, écris le diff dans ton rapport et **ne le commets pas**.
- Ne touche ni `backend/.env`, ni les services systemd, ni la prod. Ne redémarre rien.
- Rapport final `docs/missions/RAPPORT_VAGUE1_<FILE>.md` : fait avec preuve / non confirmé / reste ouvert / non fait et pourquoi. Les constats **infirmés** valent autant que les confirmés.
