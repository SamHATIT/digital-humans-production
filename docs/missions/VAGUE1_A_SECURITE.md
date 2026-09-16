# Mission Claude Code — Vague 1 / File A — Sécurité (AS-01 reste, AS-03, AS-04, AS-05)

**Date de rédaction :** 16/09/2026 · **Fenêtre :** 18 → 22/09 · **Branche :** `claude/vague1-a` · **Préalable :** vague 0 (AS-02) fusionnée.

## Lis d'abord
1. `docs/audit-20260906/rapport-astra.md` — les constats ci-dessous, aux lignes indiquées. C'est la commande ; les emplacements y sont précis.
2. `docs/BACKLOG_GOLIVE_2026-10-01.md` — §1 (calibration), §2 (go-live), §4 (plan).
3. `docs/missions/RAPPORT_VAGUE0_AS02.md` — comment lancer la suite en sécurité.

## Constats de la file
| Constat | Ligne | Titre | Gravité | Effort |
|---|---|---|---|---|
| **SEC-11** | L203 | Le blog public déclenche des dépenses et accepte une injection d’option CLI | bloquant | 1–2 h pour fermer ; 5–8 h pour sécuriser l’outil |
| **SEC-05** | L102 | Le chat HITL recharge le livrable d’un autre client dans sa classification | bloquant | 2–4 h |
| **SEC-06** | L127 | Deux clients peuvent écraser la même version SDS sur disque | bloquant | 6–10 h |
| **SEC-19** | L360 | Deux lectures et des références secondaires échappent encore au cloisonnement | majeur | 3–5 h |
| **SEC-12** | L221 | Inscription legacy sans vérification d’adresse et rattachement abusif des conversations | bloquant | 6–10 h |
| **SEC-09** | L173 | URLs Salesforce et Git arbitraires : SSRF et fuite de credentials | bloquant pour les tests de connexion accessibles | 6–10 h |
| **SEC-10** | L187 | Le HTML des livrables redevient actif dans l’origine du Studio | bloquant | 6–10 h |
| **SEC-15** | L269 | Corps sensibles, jetons Git et authentification Salesforce se retrouvent dans les sorties | bloquant | 6–10 h |
| **SEC-03** | L53 | Les sorties d’agents permettent encore des écritures hors workspace | bloquant sur tout chemin BUILD ou testeur accessible | 8–12 h |
| **SEC-08** | L159 | La règle « jamais en production Salesforce » n’est pas générale | bloquant si une fonction de déploiement reste accessible | 2–3 h pour fermer ; 6–10 h pour le contrôle complet |
| **BILL-05** | L701 | Les portes Free/Pro sont contournables par des chemins secondaires | bloquant | 6–10 h |

## Objectif — critères de sortie d'Astra
- **AS-01 reste** : aucun outil interne accessible avec un simple compte ; le blog public ne déclenche aucune dépense et n'accepte aucune injection (SEC-11). SEC-01/02 sont fermés depuis le 06/09 (cc89ca8) — vérifie-le, ne le refais pas.
- **AS-03** : A ne lit, ne modifie, ne supprime rien de B — contexte LLM, références secondaires, fichiers, conversations concierge compris (SEC-05/06/19, puis SEC-12).
- **AS-04** : HTML malveillant inerte ; secrets absents des prompts et des logs ; destinations réseau bornées ; aucune écriture hors racine (SEC-09/10/15, SEC-03 pour les chemins conservés).
- **AS-05** : toutes les écritures BUILD refusées pour Free/Pro — démarrage, retry, validation de porte, appel direct de service — **côté serveur, worker compris**, sans effet de bord (SEC-08, BILL-05). Périmètre décidé par Sam le 15/09 : Free + Pro ouverts, BUILD fermé.

## Ordre conseillé
SEC-11 (1-2 h, ferme une dépense) → SEC-05 → SEC-19 → SEC-06 → BILL-05 + SEC-08 (garde serveur unique, testée par appel direct de service) → SEC-10 → SEC-15 → SEC-09 → SEC-12 → SEC-03 (si le temps ; sinon reste ouvert, dit tel quel).

## Tests attendus (tous rouges avant correctif)
Deux tenants A et B créés par fixture ; pour chaque constat interclients, un test « A tente de lire/écrire B » qui échoue en 403/404 sans effet de bord, et son contrôle négatif « A sur A » qui réussit. Pour BILL-05/SEC-08 : un test par chemin secondaire (route, retry, gate, service direct, worker).


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
