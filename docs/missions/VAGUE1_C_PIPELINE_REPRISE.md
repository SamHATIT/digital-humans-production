# Mission Claude Code — Vague 1 / File C — Pipeline, jobs et reprises (AS-08 + calibration)

**Date de rédaction :** 16/09/2026 · **Fenêtre :** 18 → 22/09 · **Branche :** `claude/vague1-c` · **Préalable :** vague 0 (AS-02) fusionnée.

## Lis d'abord
1. `docs/audit-20260906/rapport-astra.md` — les constats ci-dessous, aux lignes indiquées. C'est la commande ; les emplacements y sont précis.
2. `docs/BACKLOG_GOLIVE_2026-10-01.md` — §1 (calibration), §2 (go-live), §4 (plan).
3. `docs/missions/RAPPORT_VAGUE0_AS02.md` — comment lancer la suite en sécurité.

## Constats de la file
| Constat | Ligne | Titre | Gravité | Effort |
|---|---|---|---|---|
| **PROD-01** | L378 | Un chat Sophie peut immobiliser toute la boucle API | bloquant | 6–10 h |
| **PROD-07** | L478 | Échecs de production, de QA et de persistance transformés en SDS terminé | bloquant Pro | 12–20 h |
| **PROD-12** | L562 | Le format « livrable terminé » n’a pas un contrat unique | bloquant Pro | 8–12 h |
| **PROD-04** | L422 | Le démarrage du worker invalide toutes les exécutions actives | bloquant | 8–12 h |
| **PROD-05** | L438 | La table de reprise corrigée saute précisément la phase qu’il fallait reprendre | bloquant | 6–10 h |
| **PROD-06** | L460 | Les portes HITL peuvent perdre la décision ou boucler | bloquant si ces portes sont proposées au lancement | 10–16 h |

## Objectif — critère de sortie d'Astra
> Panne injectée après chaque phase : pas de travail oublié, pas de succès partiel caché, pas de retry concurrent, export seul sans nouveau LLM.

## Ce que la calibration du 15/09 a confirmé empiriquement (quatre exécutions parallèles, `docs/BACKLOG_GOLIVE_2026-10-01.md` §1)
- **PROD-04 = CAL-11** : au démarrage, chaque worker marque FAILED toutes les exécutions RUNNING, y compris celles d'un autre worker (mesuré 18:0x : 179 tuée par le redémarrage des workers de calibration). Ne nettoyer que si le job arq est réellement absent.
- **PROD-05 = CAL-03** : `/resume` ne connaît que `phase2_ba` pour un FAILED alors que `last_completed_phase` permet `phase3`/`phase5` ; `_determine_resume_point()` doit dériver de `last_completed_phase`.
- **PROD-06 ≈ CAL-02/04** : une exécution tuée par `job_timeout` reste RUNNING sans erreur jusqu'au prochain redémarrage ; machine à états qui refuse `sds_phase3_running → queued` à la reprise.
- **CAL-01** : `job_timeout = 3600` global dans `worker.py` (remis à 3 600 le 16/09) — à rendre dépendant du profil de routage ou du modèle.
- **CAL-05** : `tasks.py` ignore comme fantôme tout job dont l'exécution est FAILED — empêche une reprise explicite.
- **CAL-07** : `/resume` et la reprise d'architecture enfilent toujours sur `digital-humans` ; aucune annulation (`allow_abort_jobs` absent), aucun point d'arrêt coopératif.
- **GL-10** : RAG documentaire en panne silencieuse toute la journée du 15/09 (OpenAI 429) ; `[RAG HEALTH] OK` affiché pendant la panne (= OPS-01, file D/vague 2 pour la sonde) ; règle de Sam : **alerte admin immédiate** (Telegram + journal + dashboard), pas de message client, exécution marquée `degraded: rag_unavailable`.
- **CAL-08 / CAL-09** (Emma) : faux positifs sur variantes terminologiques d'objets ; score après révision = 85,0 % identique sur quatre exécutions (plafond ou valeur assignée — à lire dans le code, pas à supposer).
- Références : `llm_interactions` contient l'horodatage de chaque appel — utilise-la pour tes tests de reprise.

## Ordre conseillé
PROD-04/CAL-11 (le plus dangereux avec plusieurs workers) → PROD-05/CAL-03 + CAL-05 → PROD-06/CAL-02/CAL-04 (timeout → FAILED explicite, transitions) → CAL-07 (file/profil mémorisés sur l'exécution, annulation coopérative) → GL-10 (alerte admin RAG + marque degraded) → PROD-07 → PROD-12 → PROD-01 → CAL-08/09 si le temps.

## Tests attendus
Injection de panne après chaque phase (kill du job, timeout, exception) : l'exécution passe FAILED avec message, la reprise reprend à `last_completed_phase` sans rejouer, aucun appel LLM en double (compter dans `llm_interactions`). Deux workers : le redémarrage de l'un ne touche pas les exécutions de l'autre.


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
