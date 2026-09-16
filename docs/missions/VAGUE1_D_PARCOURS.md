# Mission Claude Code — Vague 1 / File D — Parcours réellement vendus (AS-09 + conformité)

**Date de rédaction :** 16/09/2026 · **Fenêtre :** 18 → 22/09 · **Branche :** `claude/vague1-d` · **Préalable :** vague 0 (AS-02) fusionnée.

## Lis d'abord
1. `docs/audit-20260906/rapport-astra.md` — les constats ci-dessous, aux lignes indiquées. C'est la commande ; les emplacements y sont précis.
2. `docs/BACKLOG_GOLIVE_2026-10-01.md` — §1 (calibration), §2 (go-live), §4 (plan).
3. `docs/missions/RAPPORT_VAGUE0_AS02.md` — comment lancer la suite en sécurité.

## Constats de la file
| Constat | Ligne | Titre | Gravité | Effort |
|---|---|---|---|---|
| **BILL-06** | L717 | Fermer les projets Free casse le seul parcours de dialogue authentifié disponible | bloquant Free | 8–12 h |
| **BILL-07** | L733 | Prix correct, produit vendu incorrect, et abonnement Pro non branché | bloquant commercial | 6–10 h |
| **BILL-11** | L807 | Le refus de crédits reste invisible dans le parcours réellement utilisé | majeur ; avant ouverture pour respecter le contrat annoncé | 4–6 h |
| **PROD-10** | L526 | Contrats frontend/API cassés sur les opérations ordinaires | majeur ; correctifs courts à faire avant ouverture | 4–6 h |
| **PROD-11** | L546 | Le wizard n’envoie pas le PDF et perd des informations déterminantes | bloquant pour la promesse d’upload Pro ; majeur pour les autres points | 6–10 h |
| **OPS-09** | L1036 | Le build frontend strict contient au moins un échec statique identifiable | majeur ; corriger avant livraison des assets | 1–2 h |

## Objectif — critère de sortie d'Astra
> Free dialogue sans projet ; Pro souscriptible ; PDF réellement utilisé ou fonction retirée ; prix, capacités et messages conformes.

Plus trois lignes du backlog go-live :
- **GL-19 (bloquant)** — mentions IA article 50 **dans l'application** : bandeau « vous échangez avec une IA » au premier contact dans le widget concierge et les fenêtres du Studio ; mention « contenu généré par IA » en pied de chaque livrable et dans les métadonnées Word/PDF/HTML. Le site est conforme depuis le 15/09 ; l'obligation court depuis le 02/08/2026.
- **GL-16** — rétention des conversations Sophie : 90 jours tranchés ; `chat_log.py` ne purge pas ; la politique de confidentialité et les CGV doivent dire la même chose ; la promesse « zero data retention » du Free (RGPD-04) est fausse : la rendre vraie ou la retirer.
- **GL-18** — trois compteurs faux sur l'écran d'exécution (tokens, coût, durée) ; source de vérité : `llm_interactions`.

## Contexte mesuré 15-16/09
- Prix du site (source de vérité, `apercu-recent`) : Free 50 crédits/jour ; Pro 79 € HT/mois, 15 000 crédits, 2 SDS ; Team 1 490 € HT/mois, 100 000 crédits ; « Sonnet model » affiché sur le Free alors que le routage réel du Free est Nemotron (profil `cloud`, tier_overrides) — BILL-07 « prix correct, produit vendu incorrect » : aligner le site ou le routage, dire lequel.
- Profil de prod `cloud` depuis le 16/09 (Pro → Sonnet + Marcus Opus).

## Ordre conseillé
OPS-09 (1-2 h, build strict) → GL-19 (bloquant légal) → BILL-07 → BILL-06 → BILL-11 → PROD-10 + GL-18 → GL-16 → PROD-11 (PDF : utilisé ou retiré, pas de demi-mesure).

## Tests attendus
Parcours Free de bout en bout sans projet ; souscription Pro en sandbox Stripe → accès ouvert ; refus de crédits visible dans l'écran réellement utilisé ; Chromium : bandeau IA présent au premier message, mention en pied de livrable ; purge 90 j testée sur une conversation antidatée.


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
