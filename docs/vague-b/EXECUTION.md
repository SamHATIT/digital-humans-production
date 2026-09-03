# Exécution de la vague B — correctifs pré-ouverture

Branche `claude/vague-b-20260903`, issue de `main` (`608a09a`, vague A
déployée le 03/09). Bac à sable Claude Code (clone GitHub), **pas le VPS**.
Rien n'est mergé : Sam et Claude relisent la branche avant tout merge. La
branche a été poussée sur `origin` au fil des intégrations (le harnais du bac
à sable l'exige à chaque arrêt) ; aucun `--force`, aucune action sur `main`,
`.env`, `digital_humans_db` ni les services systemd. Le VPS n'a été touché
qu'en lecture seule, pour le lot B8 (§1.B8).

Organisation : un orchestrateur, un sous-agent par lot, un périmètre de
fichiers exclusif par lot, un `git worktree` et une base PostgreSQL jetable
par lot (`digital_humans_test_b1` … `_b9`, `_b1bis`, `_b7bis`), pour que les
suites lancées en parallèle ne se détruisent pas (`conftest.py` fait
`create_all` puis `drop_all` à chaque test). B0 puis B1 seuls, en séquence ;
puis B2, B3, B4, B5, B6, B7, B8, B9 et B1-bis en parallèle ; B7-bis après
B8, parce qu'il touche le même fichier. Modèles : Opus pour B1, B1-bis, B4 ;
Sonnet pour les autres et pour tous les tests ; orchestrateur Fable 5.1.

Deux lots ont été ouverts par l'orchestrateur, hors liste de la mission,
pour ne pas livrer un état cassé (§1.B1-bis, §1.B7-bis). Ils sont des
commits séparés : Sam peut les écarter.

Chaque « vérifié » ci-dessous est une commande jouée dont la sortie est
collée, par le sous-agent puis, pour les critères de fin, rejouée par
l'orchestrateur sur la tête finale (§5). Tout le reste est dit « lu, non
exécuté ».

---

## Suite de tests — avant / après

| | failed | passed | xfailed | errors |
|---|---|---|---|---|
| Chiffre VPS du 03/09 **annoncé** (après vague A) | 15 | 611 | 7 | 0 |
| **Mesuré** ici à B0 (`98c8527`, base `digital_humans_test`) — référence de la vague | **4** | **622** | **7** | **0** |
| Après B1 (`78ae68c`) | 4 | 632 | 7 | 0 |
| **Tête de branche, mesurée par l'orchestrateur** (`0f26762`) | **4** | **682** | **7** | **0** |

Écart VPS / bac à sable : 15 − 4 = 11 = les 11 `test_lot_e` (rouges sur le
VPS parce que la prod vit sous `/root/workspace`, objet de B9, §1.B9). Les
4 rouges sont nominatifs, antérieurs à la vague, sans lot attribué ; non
touchés, non marqués `xfail` :
`test_auth.py::test_login_success`, `test_auth.py::test_get_current_user_success`,
`test_auth.py::test_get_current_user_no_token`,
`test_emma_phase3.py::TestWBSAfterValidation::test_wbs_requires_validation_success`.

Comptage : 622 + 10 (B1) + 5 (B6) + 7 (B7) + 10 (B3) + 3 (B8) + 2 (B9)
+ 8 (B1-bis) + 11 (B4) + 4 (B7-bis) = 682.

---

## 1. Fait — commande et sortie par lot

### B0 — Référence *(pas de code)*

PostgreSQL 16 démarré (`pg_ctlcluster 16 main start`, pas de systemd dans le
conteneur), base `digital_humans_test` créée, venv `backend/venv`
(Python 3.11.15) installé depuis `requirements-test.txt`.

```
$ venv/bin/pip check                              → No broken requirements found.
$ venv/bin/pip show httpx arq redis | grep Version → 0.27.2 / 0.28.0 / 5.3.1
$ TEST_DATABASE_URL=…/digital_humans_test python -m pytest tests/ -q
4 failed, 622 passed, 7 xfailed, 232 warnings in 405.73s (0:06:45)
FAILED tests/test_auth.py::test_login_success - assert 401 == 200
FAILED tests/test_auth.py::test_get_current_user_success - KeyError: 'access_...
FAILED tests/test_auth.py::test_get_current_user_no_token - assert 401 == 403
FAILED tests/test_emma_phase3.py::TestWBSAfterValidation::test_wbs_requires_validation_success
```

Le log de B0 porte aussi la sonde de démarrage de la vague A (règle 9,
adresse sondée au boot, pas écrite ici) :
`[LLM] FOURNISSEUR LOCAL INOPERANT — gpu_nemotron: … injoignable (ConnectError: [Errno 111] Connection refused)`.
Dans le bac à sable, aucun fournisseur local ne répond : attendu.

### B1 — Compteur de crédits *(commit `78ae68c`, Opus)*

Défaut confirmé tel quel dans le code : `LLMRequest.user_id: Optional[int] = None  # None = skip credit hook`,
`complete()` sautait préflight et débit sur `None`, aucun appel de
l'orchestrateur ne renseignait `user_id`. Périmètre élargi par
l'orchestrateur à `backend/app/services/llm_service.py` : c'est le pont réel
entre les agents (`generate_llm_response`) et le routeur, et aucun autre lot
ne le touche.

Test rouge d'abord, `tests/test_vague_b_b1_credits.py`, écrit avant tout
correctif, par le **chemin réel** `PMOrchestratorServiceV2._run_agent` →
`PMAgent.run` (vrai agent) → `generate_llm_response` → `LLMRouterService.complete`,
seul `_call_provider` simulé :

```
9 failed in 4.30s
E  AssertionError: 1 appel(s) LLM mais 0 ligne(s) credit_transactions : le compteur ne suit pas les appels
E  ImportError: cannot import name 'CreditOwnerMissingError'
E  AttributeError: 'LLMRequest' object has no attribute 'sans_compte'
E  Failed: DID NOT RAISE InsufficientCreditsError   (×2 : Free 300/jour, Pro 15 000/mois)

$ pytest tests/test_vague_b_b1_credits.py            → 10 passed        # APRÈS
$ pytest tests/test_credit_service.py + B1           → 28 passed        # 19 existants intacts
$ grep -rn "None = skip credit hook" backend/        → (vide)
$ pytest tests/ -q
4 failed, 632 passed, 7 xfailed in 407.40s            # mêmes 4 rouges, +10
```

Correctif : `user_id` résolu depuis `executions.user_id` (colonne
`nullable=False`) dans `llm_service.generate_llm_response*` ; variable de
contexte `credit_owner(...)` posée par l'orchestrateur pour les appels du
même run sans `execution_id` ; `LLMRequest.sans_compte=True` pour le
concierge public ; `complete()` et `_credit_preflight` **refusent** au lieu
de sauter (`CreditOwnerMissingError` nomme l'appelant). Résolution
volontairement non mise en cache (un cache par `execution_id` survit au
`drop_all` des tests et facturerait le mauvais compte).

### B1-bis — Trois appels LLM hors orchestrateur, motif du refus rendu au client *(commit `698c164`, Opus, ouvert par l'orchestrateur)*

Pourquoi : B1 a mesuré que trois sites d'appel d'agents hors orchestrateur
ne passent aucun propriétaire de crédits et **lèvent depuis B1** —
`sophie_chat_service.py:188` (chat projet Sophie), `change_request_service.py:139`
et `:444` (classification des CR), `hitl_routes.py:181` (chat HITL). D10 dit
« `user_id` obligatoire sur tout appel LLM agent ». Sans ce lot, B1 déployé
seul casse ces trois fonctions. Second point : le critère 4 de B1
(« `InsufficientCreditsError` remontée à l'API avec un message clair ») n'était
atteint par aucun chemin HTTP (B1 l'a établi par exécution : `202` au
lancement, job ARQ, `/progress` sans le motif).

```
$ pytest tests/test_vague_b_b1bis_credits_hors_orchestrateur.py      # AVANT
6 failed, 1 passed
E  {"detail":"appel LLM sans proprietaire de credits : agent_type='sophie', execution_id=None,
   appelant=app.services.sophie_chat_service.chat:188. …"}   assert 500 == 200
E  AssertionError: aucun motif d'echec dans la reponse : {… 'status': 'failed' …}
$ pytest tests/test_vague_b_b1bis_credits_hors_orchestrateur.py      # APRÈS
8 passed
$ pytest tests/ -q
4 failed, 640 passed, 7 xfailed in 422.98s                            # mêmes 4 rouges, +8
```

Correctif : `user_id` obligatoire (mot-clé) sur `sophie_chat_service.chat`,
`change_request_service.analyze_impact` / `create_from_chat`, passé par les
routes depuis `current_user.id` ; `failure_reason` (`code`, `message`) rendu
par `/execute/{id}/progress` et par le flux SSE quand une exécution `failed`
porte la signature d'`InsufficientCreditsError`. Message mesuré :
« Credits insuffisants : le palier « free » est plafonne a 300 credits par
jour. Cet appel en demandait 96, il en restait 0. … » — palier lu dans
`users`, limite dans `tier_config`, aucun chiffre en dur.
Contrôles négatifs : un `Timeout` ne rend pas de motif ; une exécution en
cours non plus (garde mutée `if False` → `1 failed`, restaurée → `8 passed`).
Un rouge introduit par le lot et rattrapé par la suite :
`test_vague3_correspondance::test_l_api_ne_depend_pas_de_l_orchestrateur_a_l_import`
(les aides étaient d'abord dans `pm_orchestrator_service_v2.py`, importé par
une route) — déplacées dans `api/routes/orchestrator/_helpers.py`,
`pm_orchestrator_service_v2.py` finalement inchangé. Écart de périmètre :
la mission nommait `api/routes/pm_orchestrator.py` (ré-export de 18 lignes) ;
la route vit dans `orchestrator/execution_routes.py`.

### B2 — Routage par tier *(aucun commit, Sonnet)*

Arrêté : `docs/vague-b/DECISIONS_SAM.md` ligne D2 = **À TRANCHER**
(échéance 15/09). Aucun fichier modifié (`git status --short` vide).
Reconnaissance exécutée, à lire avec §3.1 :

```
get_tier_for_agent("zorro")  → AgentTier.WORKER
[ROUTAGE] Agent inconnu 'zorro' (normalise : 'zorro') — repli sur WORKER. … Cles connues : admin, aisha, apex, … zara
get_tier_for_agent("marcus") → AgentTier.ORCHESTRATOR
```
L'agent inconnu produit déjà un `warning` nommant l'agent et les clés
valides, puis un repli **documenté** sur `WORKER` : le critère « pas de repli
silencieux » est déjà tenu sur ce point.

```
tier_overrides.free.orchestrator_default = anthropic/claude-sonnet      (llm_routing.yaml:154-155)
model_pricing (008/010) : claude-sonnet-* → allowed_tiers = pro,team
preflight Free / Sonnet  → ModelNotAllowedError: Model 'claude-sonnet-4-6' not allowed for tier 'free' (user 1)
preflight "gpu_nemotron/nemotron" → UnknownModelError: No pricing row for model 'gpu_nemotron/nemotron'
```
Sonde `gpu_nemotron` au démarrage : `main.py:283` → `verifier_fournisseurs_locaux`
(`llm_router_service.py:264`), sortie observée au B0 ci-dessus.

### B3 — RGPD consentement *(commit `69d7465`, Sonnet)*

Chemin d'inscription réel établi par lecture et exécution : `SignupPage.tsx`
appelle `auth.signupRequest` (`POST /signup-request` → `POST /signup-confirm`),
pas `auth.register` ; `/register` reste monté. Les deux chemins exigent le
consentement. `consent_ip_hash` : SHA-256(ip + `CHAT_IP_SALT`), même méthode
et même variable que `chat_logs.ip_hash`, refus explicite si le sel est vide.

```
$ pytest tests/test_vague_b_b3_consentement.py       # AVANT (sources stashées)
AttributeError: module 'app.api.routes.auth' has no attribute 'CURRENT_TERMS_VERSION'
$ pytest tests/test_vague_b_b3_consentement.py       # APRÈS
10 passed in 8.89s      # absent/faux/version périmée → 400 ; vrai → 201 et 3 colonnes lues en base ; sel absent → 500 explicite
$ npx tsc -b --noEmit ; echo rc=$?                    → rc=0
$ pytest tests/ -q
4 failed, 642 passed, 7 xfailed in 441.22s            # mêmes 4 rouges, +10
```

Migration `013_consent_cgv_users`, rejouée par l'orchestrateur sur
`digital_humans_test_b3` recréée (schéma par `create_all` du modèle, puis
`alembic stamp 012_pro_79eur_15000_credits`) :

```
apres create_all (modele B3)      : consent_cgv_at,consent_ip_hash,consent_version
upgrade head (colonnes deja la)   : consent_cgv_at,consent_ip_hash,consent_version   # idempotent
downgrade -1                      : []
upgrade head                      : consent_cgv_at,consent_ip_hash,consent_version
2e cycle downgrade/upgrade        : consent_cgv_at,consent_ip_hash,consent_version
alembic current                   : 013_consent_cgv_users (head)
\d users : consent_cgv_at timestamptz | consent_version varchar(16) | consent_ip_hash varchar(64)
```
**Non exécutée sur prod.**

Écarts de périmètre, signalés par le sous-agent : `app/utils/email_token.py`
et `app/schemas/user.py` (le jeton de confirmation doit porter la preuve de
consentement, comme il porte déjà `hashed_password`), `tests/test_auth.py`
(2 tests d'inscription adaptés, sinon rouges sans rapport avec leur sujet),
`api.ts::auth.signupRequest` en plus de `auth.register`. Aucun de ces
fichiers n'appartient à un autre lot. Version des CGV `"1.0"` : constante
introduite par le lot, **non tranchée par Sam** (§3).

### B4 — RGPD droits art. 15, 17, 20 *(commit `cacc236`, Opus)*

Inventaire écrit d'abord : `docs/vague-b/INVENTAIRE_DONNEES_PERSONNELLES.md`,
34 tables (les `__tablename__` de `app/models/*.py`), colonne de
rattachement, nature, sort, moyen de vérification. Deux prémisses de la
mission infirmées par la mesure (§2). Routes : `GET /api/account/export`,
`DELETE /api/account` ; `main.py` : une ligne `include_router` et son import.

```
$ pytest tests/test_vague_b_b4_droits_rgpd.py         # AVANT
7 failed, 4 errors     E  {"detail":"Not Found"} / assert 404 == 200
$ pytest tests/test_vague_b_b4_droits_rgpd.py         # APRÈS
11 passed in 11.87s
# après suppression, mesuré : login 401, export 404, GET /api/auth/me 403
# mutation : filtre Project.user_id retiré du DELETE → 2 failed (second compte purgé, chunks Chroma)
# mutation : garde des racines de fichiers → if False → 1 failed
$ pytest tests/ -q
4 failed, 643 passed, 7 xfailed in 426.67s            # mêmes 4 rouges, +11
```

Conception commandée par le schéma : `credit_transactions.user_id` est
`nullable=False` + `ondelete=CASCADE` (`credit.py:78-82`), donc un
`DELETE FROM users` détruirait le grand livre ; sans migration (interdite au
lot), l'art. 17 est réalisé par **anonymisation en place** de la ligne
`users` (e-mail → `compte-supprime-<id>@anonymised.invalid`, RFC 6761,
`is_active=False`) et suppression physique du reste (projets et dépendances,
`chat_logs` rattachés par `email_collected`, chunks Chroma document par
document via `delete_project_document_chunks`, sur un Chroma temporaire en
test). Aucune migration produite.

### B5 — Rétention des conversations Sophie *(aucun commit, Sonnet)*

Arrêté : D3 = **À TRANCHER**. Aucun fichier modifié. Reconnaissance :
`WorkerSettings` (`app/workers/worker.py:56-65`) n'a pas de `cron_jobs` ;
`arq 0.28.0`, `arq.cron` s'importe ; `chat_log.py:13` annonce en docstring
« rows are auto-deleted after 90 days (cron job to add) » — intention, pas
implémentation ; seul écrivain de `chat_logs` : `sophie_concierge_service.py`
(lignes 230, 286) ; `POST /api/public/concierge/forget/{session_uuid}` supprime
par `session_uuid`, patron réutilisable ; unit `backend/digital-humans-worker.service`
présente dans le dépôt (service systemd distinct), état réel en prod non
mesuré. Aucun texte légal du dépôt ne fixe de durée pour `chat_logs`.

### B6 — `/health` sans recompte à chaque appel *(commit `abc37e7`, Sonnet)*

Défaut confirmé : `_check_chroma()` (`main.py`) appelait `rag_health_check()`
en direct à chaque `GET /health`, soit un `coll.count()` par collection
(cinq). D8 appliquée.

```
$ pytest tests/test_vague_b_b6_health_cache.py        # AVANT (sources stashées)
5 failed   AttributeError: … has no attribute 'reset_rag_health_cache'
$ pytest tests/test_vague_b_b6_health_cache.py -v     # APRÈS
5 passed in 3.42s
$ pytest tests/test_vague_a_a6_rag_count_off_loop.py tests/test_lot_g_health_and_boot.py tests/test_vague2_lot4_boot.py tests/test_vague2_lot3_observabilite.py -q
36 passed
$ pytest tests/ -q
4 failed, 637 passed, 7 xfailed in 432.93s            # mêmes 4 rouges, +5
```

Correctif : `rag_service.get_cached_rag_health()` / `set_rag_health_cache()`
/ `reset_rag_health_cache()`, `RAG_HEALTH_CACHE_TTL_SECONDS = 30 * 60`
(réglage nommé) ; cache périmé → rendu tel quel + rafraîchissement en tâche de
fond, un seul à la fois ; cache jamais peuplé → un comptage synchrone unique
(choix documenté : pas d'état inventé qui rendrait 503 à tort) ; la sonde de
démarrage (A6) alimente le cache au lieu de jeter son comptage. Ouvert d'A6
traité au passage : `rag_health_task` annulée au shutdown si non terminée.

### B7 — Une seule source pour les tiers *(commit `c9effce`, Sonnet)*

Emplacement réel du prompt : `backend/prompts/agents/sophie_pm.yaml`
(`backend/app/agents/prompts/` n'existe pas). `GET /api/subscription/tiers`
existait déjà, public (aucune dépendance d'authentification), mais lisait
`TIER_FEATURES` (dict Python), jamais `tier_config` : réutilisé et corrigé
(pas de `/api/public/tiers` en doublon).

```
$ git stash push -- app/api/routes/subscription.py
$ pytest tests/test_vague_b_b7_tiers_source_unique.py -k get_tiers   → 2 failed   # AVANT
$ git stash pop
$ pytest tests/test_vague_b_b7_tiers_source_unique.py               → 7 passed   # APRÈS
$ npx tsc -b --noEmit ; echo EXIT=$?                                → EXIT=0
$ pytest tests/ -q
4 failed, 639 passed, 7 xfailed in 432.00s            # mêmes 4 rouges, +7
```

Le test qui prouve la source : il **modifie** une valeur de `tier_config` sur
la base jetable et vérifie que l'API la reflète ; contrôle négatif : une
valeur de `TIER_FEATURES` ne change pas la réponse. Nouveau module
`app/services/tier_config_service.py` (lecture de `tier_config`,
`get_tier_summary_text()`). `Pricing.tsx` : plus aucun prix ni crédit en dur,
chargement depuis l'API, états de chargement et d'erreur explicites, aucun
chiffre de repli. `sophie_pm.yaml` : bloc « PRICING TIERS » remplacé par
`{{tier_summary}}`. Pas de test de rendu frontend : aucun runner dans
`package.json` (signalé, pas contourné).

### B7-bis — Substitution de `{{tier_summary}}` dans le concierge *(commit `0f26762`, Sonnet, ouvert par l'orchestrateur)*

Pourquoi : après B7, `converse()` ne substituait que `{{visitor_language}}`,
`{{history}}`, `{{user_message}}` ; le concierge public envoyait la chaîne
littérale `{{tier_summary}}` au LLM. Le fichier appartenait à B8 : lot
séquencé après le commit de B8.

```
$ pytest tests/test_vague_b_b7bis_concierge_tiers.py -v     # AVANT
4 failed   AssertionError: le placeholder litteral {{tier_summary}} a ete envoye au LLM tel quel
$ pytest tests/test_vague_b_b7bis_concierge_tiers.py -v     # APRÈS
4 passed   # fr, en ; mutation de tier_config entre deux tours répercutée ; langue du visiteur pilote le résumé
$ pytest A5 + B1 + B7 + B8 + credit_service -q               → 43 passed
$ pytest tests/ -q   (sur bc9ca2b + ce lot)
4 failed, 663 passed, 7 xfailed in 430.66s
```

Correctif : deux lignes dans `converse()` (`await asyncio.to_thread(get_tier_summary_text, db, visitor_language)`
puis `.replace("{{tier_summary}}", …)`), un import. Aucune valeur numérique en
dur dans les assertions : tout est relu de la base jetable.

### B8 — Deux compteurs muets *(commit `cce4d90`, Sonnet)*

1. `chat_logs.tokens_in/tokens_out` : `LLMResponse` expose `tokens_in`/`tokens_out`
(`llm_router_service.py:126-131`), le concierge lisait `tokens_input`/`tokens_output`.

```
$ pytest tests/test_vague_b_b8_compteurs.py     # AVANT     assert None == 17
$ pytest tests/test_vague_b_b8_compteurs.py     # APRÈS     3 passed
# valeurs distinctes 17/42 puis 99/3, colonnes vérifiées séparément (pas d'inversion) ;
# routeur sans attributs → None en base, 0 dans ConciergeReply, pas d'exception
$ pytest tests/ -q
4 failed, 635 passed, 7 xfailed                  # mêmes 4 rouges, +3
```

2. `daily.sh` : `docs/vague-b/CORRECTIF_DAILY_RC.md`. L'orchestrateur a lu le
VPS en lecture seule (03/09) : trois copies identiques
(`md5sum 2d64675b…` : `/root/workspace/dh-comite/bin/daily.sh`, `…/dh-comite-v3/…`,
`/root/export-dh/comite/…`), lancées par `/etc/cron.d/dh-comite-rituels`
(07:30 UTC, `docker exec dh-comite`). **Le constat de la mission (« RC=1 alors
que `claude -p` réussit ») ne se retrouve pas dans le journal** :
`grep -n "RC=[1-9]" /var/log/dh-comite-cron.log` → vide ; toutes les lignes
`daily terminé RC=` du 08/08 au 03/09 valent `RC=0` (§2). Ce qui est mesuré :
`briefs/incidents.log` porte `2026-08-29 ALERTE : brief non produit — inconnue [claude RC=0]`
alors que `daily-2026-08-29.meta.json` dit `is_error:false, subtype:success,
num_turns:29, 752 s, 7,33 USD` — la raison est « inconnue » parce que
`jq 'select(.is_error==true)'` ne produit rien sur `is_error=false`, et `RC`
n'entre dans aucune condition d'alerte (affiché seulement). Sous
`set -euo pipefail`, mesuré localement : `RC` reflète le code du dernier
élément non nul du pipe, donc `claude`, pas `cat` (sauf le cas étroit `cat` en
échec et `claude` réussi). Le document propose un bloc fondé sur `is_error` /
`subtype` du JSON et sur l'existence du brief, testé contre quatre
`meta.json` factices (vrai / faux / vide / absent), sans URL ni port.

### B9 — `test_lot_e` contre la réalité de la prod *(commit `bc9ca2b`, Sonnet)*

Chaque assertion lue : `test_no_machine_specific_default_path` (10
paramétrisations) et `test_sf_admin_persist_dir_defaults_to_settings`
vérifiaient « ne commence pas par un des trois préfixes », pas « dérive du
checkout » ; les 10 attributs dérivent tous de `Path(__file__).resolve()`
(`app/config.py:97-134`). Option A retenue (`docs/vague-b/ARBITRAGE_CHEMIN_PROD.md`) :
chaque attribut est vérifié via un `Settings` frais, sa variable `DH_<ATTR>`
retirée, contre `settings.PROJECT_ROOT.resolve()` par `is_relative_to()` ; une
surcharge explicite reste acceptée. `FORBIDDEN_PREFIXES` ne sert plus qu'à
`test_no_hardcoded_absolute_path_in_source`, qui scanne le **texte** de trois
fichiers pour un littéral copié, jamais une valeur de chemin. Option B
chiffrée par grep : 84 fichiers, 153 occurrences.

Preuve de règle 10, rejouée par l'orchestrateur sur la tête finale, copie
`tar` de l'arbre sous `/root/workspace/digital-humans-production-verif`
(une copie, pas un lien : `Path.resolve()` déréférence les liens) :

```
== nouveau test depuis /root/workspace/digital-humans-production-verif/backend
27 passed in 0.08s
== contrôle négatif : ancien test (main) depuis le même chemin
11 failed, 14 passed in 0.28s
(copie supprimée ; /root/workspace n'existe plus)
```
Contrôle négatif du sous-agent : `CHROMA_PATH` forcé vers
`/opt/digital-humans/rag/chromadb_data` → `AssertionError: … outside the checkout root … — a hardcoded machine-specific path`.
Suite : `4 failed, 634 passed, 7 xfailed` (+2 tests permanents).

---

## 2. Non confirmé — constats qui ne se sont pas vérifiés

| Constat | Verdict |
|---|---|
| Référence VPS « 15 failed, 611 passed, 7 xfailed » | **Mesuré ici : 4 / 622 / 7.** L'écart est exactement les 11 `test_lot_e` (B9) ; le nombre total de tests coïncide (626 = 626). |
| B8 : « `daily.sh` affiche `RC=1` alors que `claude -p` réussit » | **Non retrouvé** dans `/var/log/dh-comite-cron.log` (lecture seule, 03/09) : aucun `RC≠0` du 08/08 au 03/09. Le défaut mesuré est l'inverse : une alerte partie avec `RC=0` et une raison « inconnue » (§1.B8). Où Sam a vu `RC=1` n'est pas établi. |
| B8 : « probablement le `|| RC=$?` qui capture le code du `cat` » | **Ne tient pas** sous `set -o pipefail` (mesuré) ; seul le cas `cat` en échec et `claude` réussi le produirait. |
| B4 : « purge Chroma des collections liées aux projets du compte » | **Il n'y a pas de collection par projet** : cinq collections fixes (`rag_service.py:47-53`), isolation par métadonnée de chunk. Purge document par document. |
| B4 : « `chat_logs` porte `ip_hash` » comme seule IP | **`audit_logs` porte l'IP en clair** dans deux colonnes, `ip_address` et `actor_id` (`audit_middleware.py:132-133`) — seule table du dépôt avec une IP non hachée, sans lien vers un compte. |
| B7 : prompt de Sophie sous `backend/app/agents/prompts/` ; endpoint `/api/public/tiers` absent | Prompt sous `backend/prompts/agents/sophie_pm.yaml` ; `GET /api/subscription/tiers` existait déjà, public, mais lisait le code au lieu de la table. |
| B1 : « `credit_transactions` = 0 pour 222 `llm_interactions` », « `executions.user_id` 131/131 » | Chiffres de prod, **non vérifiables** depuis le bac à sable. Vérifié : `Execution.user_id` est `nullable=False`, la propagation est structurellement possible. |
| B1 : `_resolve_tier_for_execution` comme résolveur analogue | Nuance : il résout par `execution → project → project.user_id` ; B1 lit `executions.user_id`. Les deux divergent si un projet change de propriétaire. |
| B1-bis : périmètre « `api/routes/pm_orchestrator.py` » | Ré-export de 18 lignes ; la route de progression vit dans `orchestrator/execution_routes.py`. |
| B6 : « 32 tests » dans les quatre fichiers de référence | 36 mesurés (4 + 10 + 13 + 9), tous verts. |
| B3 : chemin d'inscription = `POST /register` | Le frontend passe par `signup-request` / `signup-confirm` ; les deux chemins couverts. |
| B2 : « agent inconnu → repli silencieux » | Déjà un `warning` nommant l'agent et les clés valides, repli documenté sur `WORKER`. |
| Bac à sable : suites parallèles | Un rouge transitoire (`test_register_user_success`) est apparu pendant la mesure de référence de B8 (huit suites sur le même serveur PostgreSQL) et passe isolé ; B4 a rencontré des `create_all`/`drop_all` croisés par un processus orphelin sur sa base. Fragilité de `conftest.py` (`create_all` à l'import de `app.main` + `create_all`/`drop_all` par test), pas causée par la vague. Aucune de ces suites n'est celle rapportée ici. |

---

## 3. Ouvert — ce qui reste, et pourquoi

1. **Déployer B1 sans B2 bloque le tier Free** (mesuré par B1 et B2). Avant
   B1, `user_id=None` sautait le préflight : le Free tournait en Sonnet, non
   facturé, non contrôlé. Depuis B1, `tier_overrides.free → anthropic/claude-sonnet`
   (`llm_routing.yaml:154`) rencontre `model_pricing` (`claude-sonnet-* → pro,team`)
   et lève `ModelNotAllowedError` au préflight de tout agent orchestrateur
   Free. Aucun modèle n'est autorisé au Free dans `model_pricing` hors Haiku,
   que D5 exclut. Et aucun modèle local n'est tarifé (`UnknownModelError`
   sur `gpu_nemotron/nemotron`, règle 6 : on ne facture pas ce qu'on ne sait
   pas tarifer). Chaîne à trancher **avant** merge : D2, puis B2
   (`tier_overrides.free → nemotron`, D6), puis une ligne `model_pricing`
   pour le modèle local (migration 014), puis la sonde de démarrage à relire
   contre le fournisseur réellement choisi. B2 et B5 s'arrêtent sur D2 et D3
   comme la mission l'exige.
2. **Frontend : le motif du refus de crédits n'est pas affiché.**
   `useExecutionStream.ts:23` (`interface ExecutionProgress`, ajouter
   `failure_reason`) et `ExecutionMonitoringPage.tsx:531` (bloc « Failure
   rescue » : rendre le message ; pour `insufficient_credits`, remplacer
   « Rejouer l'acte » par un renvoi vers les tarifs). `useExecutionProgress.ts`
   porte une seconde interface sans aucun consommateur : à supprimer plutôt
   qu'à maintenir. Hors périmètre de la vague.
3. **Reconnaissance du refus par signature de message** (`_helpers.py`) :
   couplage assumé avec `str(InsufficientCreditsError)`, gardé par un test
   qui construit l'exception réelle. Disparaît le jour où les agents
   propagent l'exception par son type au lieu de `str(e)` (`agents/roles/*.py`,
   `_run_agent_interne`) — un lot à part. `failure_reason` ne couvre que les
   crédits (timeout, circuit breaker, budget : sans motif).
4. **Version des CGV `"1.0"`** (B3, `auth.CURRENT_TERMS_VERSION` et
   `api.ts::auth.CGV_VERSION`) : introduite par le lot, à confirmer par Sam ;
   le backend refuse toute autre valeur (400 nommant reçu/attendu).
5. **Révocation stricte du jeton** (B4) : le JWT est sans état ;
   `is_active=False` donne une révocation de fait (403 mesuré). Une liste
   noire de `jti` exigerait `app/utils/auth.py` (hors périmètre) :
   proposition dans le rapport B4. `stripe_customer_id` conservé, aucune
   répercussion vers Stripe. Un chunk ingéré sans `document_id` (le code
   l'autorise) échapperait à la purge.
6. **`audit_logs` avec IP en clair** (`actor_id = ip_address`,
   `audit_middleware.py:132-133`) : une demande d'effacement ne peut pas les
   atteindre, et la requête d'effacement elle-même en produit une. Correctif
   dans le middleware, hors périmètre.
7. **`journal_webhook.py:24`** : `BUILD_SCRIPT = Path("/root/workspace/digital-humans-production/scripts/journal/build.py")`,
   un vrai chemin machine dans du code applicatif (trouvé par B9, hors
   périmètre).
8. **`feature_access.py:280`** (`get_user_tier_info`, `GET /api/subscription/my-subscription`)
   et `POST /api/subscription/upgrade-to/{tier}` renvoient encore
   `price_display` depuis `TIER_FEATURES` — même défaut que celui corrigé
   par B7 sur `/tiers`, autres endpoints.
9. **`create_from_chat` avale ses échecs** (`except Exception: … return None`) :
   une CR non créée reste silencieuse (B1-bis, hors défaut du lot).
10. **`daily.sh`** : correctif documenté, non appliqué (dépôt `dh-comite`,
    VPS). Trois copies identiques ; laquelle fait foi n'est pas établi.
11. **B5** : quand D3 est tranchée — `cron_jobs` sur `WorkerSettings`,
    fonction de purge sur `created_at`, index sur `created_at` à mesurer,
    docstring de `chat_log.py:13` à corriger, état réel de
    `digital-humans-worker.service` à mesurer en prod.
12. **Les 4 rouges antérieurs** (`test_auth` ×3, `test_emma_phase3` ×1) :
    toujours sans lot.
13. **Trailers de commit** : tous les commits de la vague portent le trailer
    `Co-Authored-By` exigé par le harnais ; la consigne « aucune mention de
    modèle » n'est donc pas tenue dans les messages. Historique non réécrit
    (vague A avait laissé la question à Sam).

---

## 4. Non fait par choix

- **Aucun merge, aucune action sur `main`, `.env`, `digital_humans_db`, les
  services systemd.** Le VPS n'a été lu que pour B8 (`daily.sh`, journal
  cron, `incidents.log`, `meta.json`), sans aucune écriture.
- **B2 et B5 : aucun code.** D2 et D3 sont « À TRANCHER » ; écrire
  `tier_overrides` ou une durée de purge aurait été une décision produit
  prise à la place de Sam.
- **B1 : `credit_service.py` non modifié** (lecture seule) ;
  `_credit_post_charge` ne lève toujours pas (le jeton est déjà consommé,
  échouer ne le rend pas) — journal passé de `ERROR` à `CRITICAL`, une ligne
  de crédit perdue étant exactement le défaut du lot. `execute_workflow`
  complet non joué en test (24 états, RAG, sfdx) : `_run_agent`, point de
  passage unique des 24 sites, avec le vrai agent PM.
- **B1-bis : pas de motif sur la route de lancement** (`202` avant que le
  job ARQ ne commence : le refus n'existe pas encore) ; pas de champ `code`
  écrit dans `executions.logs` (aurait obligé à modifier `execute_workflow`
  sans rien dire des exécutions déjà en échec).
- **B4 : pas de migration** (`credit_transactions.user_id` NOT NULL +
  CASCADE commande l'anonymisation en place) ; art. 22 hors périmètre (D11) ;
  aucune purge de `journalctl`.
- **B6 : `llm_local_probe_task` (sonde A9) non annulée au shutdown** — seule
  `rag_health_task` l'est, pour rester dans le périmètre RAG ; pas de
  conversion `on_event` → `lifespan`.
- **B7 : `app/models/subscription.py` lu, non modifié** : `TIER_FEATURES`
  reste la source des drapeaux de fonctionnalités et des libellés (D9 ne
  couvre que crédits et prix) ; son champ `price` n'alimente plus `/tiers`.
- **B9 : pas de correction de `journal_webhook.py`**, ni des services
  systemd (non suivis dans le dépôt, non chiffrés).
- **Les 4 rouges antérieurs** ni corrigés ni marqués `xfail`, sur
  instruction.
- **Migrations 013 : produite et testée sur base jetable, jamais exécutée
  sur prod.** Aucune migration 014.

---

## 5. Journal et ligne pytest finale

```
$ git log --oneline main..HEAD
0f26762 fix(concierge): substitue {{tier_summary}} dans le prompt public de Sophie
cacc236 feat(rgpd): droits d'acces, de portabilite et d'effacement du compte (art. 15, 17, 20)
698c164 fix(credits): facturer les trois appels LLM d'agents hors orchestrateur, et rendre le motif du refus au client
bc9ca2b fix(tests): test_lot_e vérifie que les chemins dérivent du checkout, pas une liste de préfixes interdits
cce4d90 fix(concierge): tokens_in/tokens_out persistes dans chat_logs, correctif documente pour daily.sh RC
69d7465 fix(rgpd): consentement CGV explicite obligatoire a l'inscription (B3)
c9effce fix(tiers): une seule source pour les tiers publics — tier_config (D9)
abc37e7 fix(health): cache le comptage RAG (TTL 30 min), fini le recomptage a chaque appel
78ae68c fix(credits): facturer les appels LLM des agents au proprietaire de l'execution
98c8527 Vague B : mission et decisions posees sur la branche
```

(plus le commit qui porte ce document.) Aucun commit B2 ni B5 : lots
arrêtés sur D2 et D3. Les commits des sous-agents ont été intégrés par
`cherry-pick` depuis leurs worktrees, sans conflit, dans l'ordre B6, B7, B3,
B8, B9, B1-bis, B4, B7-bis.

Suite complète rejouée par l'orchestrateur sur `0f26762`, base
`digital_humans_test`, venv `backend/venv` (Python 3.11.15), aucune autre
suite en parallèle :

```
$ cd backend && python -m pytest tests/ -q -p no:cacheprovider
4 failed, 682 passed, 7 xfailed, 298 warnings in 452.40s (0:07:32)

FAILED tests/test_auth.py::test_login_success - assert 401 == 200
FAILED tests/test_auth.py::test_get_current_user_success - KeyError: 'access_...
FAILED tests/test_auth.py::test_get_current_user_no_token - assert 401 == 403
FAILED tests/test_emma_phase3.py::TestWBSAfterValidation::test_wbs_requires_validation_success
$ grep -c "^ERROR tests" pytest_final.log
0
```

Critères de fin rejoués par l'orchestrateur sur la même tête :

```
$ grep -rn "None = skip credit hook" backend/ --include=*.py ; echo rc=$?      → rc=1 (0 occurrence)
$ venv/bin/alembic heads                                                        → 013_consent_cgv_users (head)
$ grep -nE "[0-9]+ ?(crédits|credits|€|EUR)|€ ?[0-9]+" frontend/src/pages/Pricing.tsx ; echo rc=$?   → rc=1
$ grep -nE "€|[0-9]{3,} ?(cr[eé]dits|credits)|SDS/mois|SDS per month|/mois|/month" backend/prompts/agents/sophie_pm.yaml ; echo rc=$?  → rc=1
$ grep -n "tokens_input\|tokens_output" backend/app/services/sophie_concierge_service.py   → 1 ligne, un commentaire
$ grep -n "tier_summary" backend/app/services/sophie_concierge_service.py                  → import + substitution
$ grep -n "consent" backend/app/models/user.py ; ls backend/alembic/versions/013*          → colonnes + 013_consent_cgv_users.py
$ grep -n "@router" backend/app/api/routes/account.py                                      → GET /export, DELETE ""
$ ls docs/vague-b/  → ARBITRAGE_CHEMIN_PROD.md CORRECTIF_DAILY_RC.md DECISIONS_SAM.md INVENTAIRE_DONNEES_PERSONNELLES.md MISSION.md (+ ce fichier)
$ python -m py_compile app/main.py app/services/{sophie_concierge_service,llm_service,llm_router_service,account_service,tier_config_service}.py app/api/routes/orchestrator/_helpers.py → OK
$ (cd frontend && npx tsc -b --noEmit ; echo rc=$?)                                        → rc=0
$ test_lot_e depuis /root/workspace/… : 27 passed (nouveau) / 11 failed, 14 passed (ancien)  → §1.B9
```

`Pricing.tsx` garde des chiffres qui ne sont ni crédits ni prix (« BRs max
par projet : 30 / 100 », classes Tailwind) : hors critère.

Pas de merge. Branche poussée. Sam relit.
