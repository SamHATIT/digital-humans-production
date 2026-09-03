# Exécution de la vague A — correctifs pré-ouverture

Branche `claude/vague-a-20260903`, issue de `main` (`d9798f6`). Bac à sable
Claude Code (clone GitHub), **pas le VPS**. Rien n'est poussé, rien n'est
mergé : Sam relit la branche avec Claude avant tout merge.

Organisation : un orchestrateur, un sous-agent par lot, un périmètre de
fichiers exclusif par lot, un `git worktree` et une base PostgreSQL jetable
par lot (`digital_humans_test_a1` … `_a10`) pour que les suites lancées en
parallèle ne se détruisent pas mutuellement (`conftest.py` fait
`create_all` puis `drop_all` à chaque test). A1 seul d'abord ; A2, A4, A5,
A6, A7, A8, A9, A10 en parallèle ; A3 après A4, parce que les deux lots
partagent `backend/app/models/subscription.py` — la mission les déclarait
disjoints, ils ne l'étaient pas (§2).

Chaque « vérifié » ci-dessous est une commande jouée dont la sortie est
collée. Tout le reste est dit « lu, non exécuté ».

---

## Suite de tests — avant / après

| | failed | passed | xfailed | errors |
|---|---|---|---|---|
| Chiffres du 02/09 **annoncés** (VPS) | 24 | 461 | 7 | 118 |
| **Mesuré** ici avant A1 (`f03053a`) | 11 | 474 | 7 | **118** |
| Après A1 (`9087728`) — référence de la vague | 8 | 595 | 7 | 0 |
| Après A4 (`52b2008`) | 8 | 605 | 7 | 0 |
| **Tête de branche, mesurée par l'orchestrateur** (`fff74fc`) | **5** | **616** | **7** | **0** |

Seul le 118 coïncide avec le VPS. C'est la mesure du bac à sable qui fait
référence, conformément à la mission.

Les 8 rouges après A1 sont nominatifs et préexistent à la vague :
`test_auth` ×3, `test_credit_service` ×4 (objet du lot A3),
`test_emma_phase3` ×1. Les 3 `test_auth` et le `test_emma_phase3` n'ont de
lot attribué dans aucun des documents lus (§3).

---

## 1. Fait — commande et sortie par lot

### A1 — httpx plafonné, 118 tests remis en jeu *(commit `9087728`)*

Périmètre : `backend/requirements.txt`, venv. Défaut confirmé tel quel :
pip résolvait `httpx 0.28.1` depuis un `httpx>=0.27.0` non plafonné.

```
$ venv/bin/pip show httpx starlette fastapi | grep -E '^(Name|Version)'
httpx 0.28.1 / starlette 0.27.0 / fastapi 0.104.1

$ pytest tests/ -q                       # AVANT, base digital_humans_test_a1
11 failed, 474 passed, 7 xfailed, 640 warnings, 118 errors in 373.81s
$ grep -c "unexpected keyword argument 'app'" /tmp/pytest_a1_avant.log
124

$ venv/bin/pip install 'httpx>=0.27,<0.28'   → httpx-0.27.2
$ pytest tests/ -q                       # APRÈS
8 failed, 595 passed, 7 xfailed, 1031 warnings in 394.71s
$ grep -c "unexpected keyword argument 'app'" /tmp/pytest_a1_apres.log
0
$ venv/bin/pip check
No broken requirements found.
```

Comptage cohérent : 474 + 118 + 11 = 603 = 595 + 8. Les 118 erreurs
frappaient 14 fichiers, dont ceux qui portent les critères de fin des lots
B, C, G de la vague 1.

Trouvé au passage, hors périmètre A1 : `arq` et `redis` sont importés par
`app/workers/arq_config.py` et `app/main.py` mais absents de
`requirements.txt` ; sans eux `conftest.py` ne s'importe pas. Installés dans
le venv seulement (`arq 0.28.0`, `redis 5.3.1`), déclarés par A2.

### A2 — REQ-001, `arq` et `redis` épinglés *(commit `244829f`)*

```
$ grep -inE '^(arq|redis)' backend/requirements.txt; echo rc=$?
rc=1                                                    # AVANT
$ pip install -r backend/requirements.txt --dry-run | grep -iE 'arq|redis'
(vide)
$ pip show arq redis | grep -E '^(Name|Version)'
arq 0.28.0 / redis 5.3.1

$ grep -qiE '^arq==' backend/requirements.txt && grep -qiE '^redis==' backend/requirements.txt && echo OK
OK                                                      # APRÈS
$ pip install -r backend/requirements.txt --dry-run     → rc=0
$ pip check                                             → No broken requirements found.
$ python -c "import tests.conftest; print('conftest importable')"
conftest importable
```

Aucun code Python modifié : pas de suite complète rejouée pour ce lot ; la
suite complète de fin de vague (§5) couvre l'état final.

### A3 — Pro 79 €/mois, crédits Pro 15 000 *(commit `fff74fc`)*

Décisions D1 et D4 lues dans `DECISIONS_SAM.md` (plus de « À TRANCHER »
sur D1 depuis `b78d354`). Lot interrompu une fois par un redémarrage du
conteneur, repris par un second sous-agent sur l'état laissé, chaque point
revérifié par exécution.

Les 4 rouges de `test_credit_service` avaient **deux causes**, pas une :
le seed du test à 2000/49, et `tier="premium"` dans 3 tests, alias qui
résout vers `team` (100 000 crédits), pas vers `pro` — comportement voulu et
documenté deux fois (`credit_service.py:94`, migration
`009_realign_freemium_tiers.py` : « Premium incluait le BUILD → équivalent
à Team »).

```
$ pytest <ancien test_credit_service.py> -q          # contre le code actuel
4 failed, 15 passed
  test_resolve_credit_tier_maps_legacy_premium_to_pro   → assert 'team' == 'pro'
  test_charge_sonnet_pro_user_ok                        → assert 99993 == (2000 - 7)
  test_get_balance_lazy_create                          → assert 100000 == 2000
  test_reset_monthly_resets_used_to_zero_and_refills_included → assert 100000 == 2000
$ pytest tests/test_credit_service.py -q             # après correctif
1 failed, 18 passed        # reste : test_resolve_credit_tier_maps_legacy_premium_to_pro

$ grep -cE "[^0-9 ]49€" frontend/src/pages/Pricing.tsx      → 0
$ npx tsc -b --noEmit                                         → TSC OK
$ grep -q '79 €/mois' backend/app/models/subscription.py && echo OK → OK
$ alembic heads                                               → 012_pro_79eur_15000_credits (head)
```

Migration `012_pro_79eur_15000_credits.py`, données seulement, testée sur
`digital_humans_test_a3` (schéma par `AUTO_CREATE_SCHEMA=true`, seed
reproduisant 008 puis l'effet de 010, `alembic stamp 011_expert_selection`) :

```
avant (011)   : pro | 15000 | 49.00 | "...2000 credits/mois"
upgrade head  : pro | 15000 | 79.00 | "...15000 credits/mois inclus"
downgrade -1  : pro | 15000 | 49.00 | "...2000 credits/mois"
upgrade head  : pro | 15000 | 79.00 | "...15000 credits/mois inclus"
```

**Non exécutée sur prod** (D4). Identifiant de révision raccourci à
27 caractères : `alembic_version.version_num` est un `varchar(32)`, mesuré
(`\d alembic_version`), et le nom initial de 33 caractères faisait échouer
le `stamp`.

Suite complète sur sa base : `8 failed, 613 passed, 7 xfailed` avant (613 =
605 d'A4 + les 8 tests d'A5 et A6, absents du worktree A4) → `5 failed,
616 passed, 7 xfailed` après ; les 5 : `test_auth` ×3, `test_emma_phase3`
×1, `test_resolve_credit_tier_maps_legacy_premium_to_pro`.

**Critère de fin « 4 tests crédits verts » : 3 sur 4.** Le quatrième porte
une assertion contraire au mapping documenté ; le faire passer exigeait
soit de réécrire son assertion (`team`), soit de changer
`credit_service.py`, hors périmètre. Voir §3.

### A4 — clé `llm_haiku` morte *(commit `52b2008`)*

Décision D5. Cartographie par grep : la clé n'existait que dans
`subscription.py` (lignes 73, 124, 175, 225, 330) ; aucun appelant ailleurs
(frontend, services). Test rouge d'abord, `tests/test_vague_a_a4_haiku.py` :

```
$ pytest tests/test_vague_a_a4_haiku.py -q      # AVANT
6 failed, 4 passed in 0.16s
$ pytest tests/test_vague_a_a4_haiku.py -q      # APRÈS
10 passed
$ grep -c llm_haiku backend/app/models/subscription.py
0
$ pytest tests/ -q
8 failed, 605 passed, 7 xfailed                  # mêmes 8 rouges nominatifs, +10
```

Les assertions : `has_feature(tier, "llm_haiku") is False` pour chaque
tier, contrôles positifs `llm_sonnet`/`llm_opus`, absence de la clé dans
tout `TIER_FEATURES`. `has_feature` rendait déjà `False` sans lever pour une
clé absente : non modifiée.

### A5 — concierge public : prémisse non confirmée, garde ajoutée *(commit `47065b1`)*

Voir §2 pour le constat. Ce qui est fait : `tests/test_vague_a_a5_concierge_cloisonnement.py`
(4 tests, ChromaDB temporaire, embeddings fixes, routeur LLM factice,
`CHAT_IP_SALT` monkeypatché) ; `sophie_concierge_service.py` **inchangé**.

```
$ pytest tests/test_vague_a_a5_concierge_cloisonnement.py -v
test_un_tour_concierge_ne_fait_sortir_aucun_chunk_du_projet_999 PASSED
test_le_tour_concierge_persiste_les_deux_tours_sans_contexte_rag PASSED
test_controle_negatif_le_rag_global_sort_bien_le_chunk_du_projet_999 PASSED
test_controle_negatif_get_salesforce_context_sans_projet_sort_la_sentinelle PASSED
4 passed in 1.49s
```

Pouvoir discriminant prouvé par mutation temporaire (un
`get_salesforce_context(...)` injecté dans `converse()`, puis retiré,
`diff` vide vérifié) :

```
E  AssertionError: un chunk tague project_id=999 est arrive jusqu'au prompt du routeur LLM
E  'SENTINELLE-A5-PROJET-999-a7f3c1e9d2b4' is contained here: …
```

`py_compile` OK ; suite complète `8 failed, 599 passed, 7 xfailed` sur sa
base, mêmes 8 rouges.

### A6 — comptage RAG hors boucle d'événements *(commit `b454a93`)*

Le fichier qui journalise `[RAG HEALTH] OK` est `rag_service.py`, mais le
défaut n'y est pas (§2) : c'est `app/main.py::startup_event`, coroutine qui
appelait `rag_health_check()` en synchrone. `/health` était déjà hors boucle
depuis la vague 2 (§4.1). Correctif dans la section startup de `main.py`
seulement : `asyncio.create_task` d'une coroutine qui fait
`await asyncio.to_thread(rag_health_check)`, référencée par
`app.state.rag_health_task`, journal `[RAG HEALTH]` et `probe crashed`
conservés. Choix argumenté : un simple `await asyncio.to_thread` libère la
boucle mais uvicorn n'ouvre pas le port avant la fin du startup ; le critère
« `/health` répond pendant le comptage » exige la tâche de fond.

```
$ pytest tests/test_vague_a_a6_rag_count_off_loop.py -q     # AVANT
E  AssertionError: le startup a dure 3.04 s : le comptage RAG est encore sur la boucle d'evenements
E  assert 3.037442933999955 < 1.0
2 failed, 2 passed
$ pytest tests/test_vague_a_a6_rag_count_off_loop.py -v     # APRÈS
4 passed
$ pytest tests/test_lot_g_health_and_boot.py tests/test_vague2_lot4_boot.py tests/test_vague2_lot3_observabilite.py -q
32 passed
$ pytest tests/ -q
8 failed, 599 passed, 7 xfailed                              # mêmes 8 rouges
```

Le test mesure la durée du startup et celle de `/health` (sondes de
`/health` stubbées, dit en docstring) pendant qu'un faux `count()` dort
3 s, et vérifie que le comptage est encore en cours. Contrôle négatif : le
même faux comptage appelé en synchrone bloque une coroutine témoin ≥ 3 s.

### A7 — watchdog *(commit `51921ee`)*

```
$ HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:1/health || echo 000); echo "[$HTTP]"
[000000]                                     # double 000 reproduit
$ bash -n scripts/dh-watchdog.sh; echo rc=$?
rc=0
$ DRY_RUN=1 STATE=/tmp/wd_a7.state bash scripts/dh-watchdog.sh
DRY_RUN: 🔴 DH ALERTE (20:39Z) : backend /health = 000 | spark /v1/models = 000 | postgresql état indéterminé (systemctl injoignable) | nginx état indéterminé (systemctl injoignable) | n8n état indéterminé (systemctl injoignable)
$ DRY_RUN=1 STATE=/tmp/wd_a7.state bash scripts/dh-watchdog.sh   # rejoué : anti-spam
(vide)
# avec un /health factice à 200 (python -m http.server 8002) :
DRY_RUN: 🔴 DH ALERTE (20:39Z) : spark /v1/models = 000 | postgresql état indéterminé (…) | …
```

`shellcheck` non disponible dans le bac à sable. Sam recopie le script vers
`/usr/local/bin/dh-watchdog.sh` sur le VPS.

### A8 — `smoke_test.sh` réécrit *(commit `3c4839b`)*

Ancien script joué sans backend : `0 passed, 5 failed`, et trois assertions
fausses par construction (`/docs` 200 alors que `DEBUG=False` le ferme ;
routes `pm-orchestrator` sans jeton attendues en 200 ; frontend 3000).
Backend réel démarré dans le bac à sable à `DEBUG=False` (clé Fernet et
`SECRET_KEY` jetables en variables de shell, jamais écrites), Redis local
lancé, ChromaDB temporaire à 1 chunk pour que `/health` rende 200, compte de
test créé par `POST /api/auth/register`.

```
$ bash -n scripts/smoke_test.sh                       → OK
$ SMOKE_USER=… SMOKE_PASS=… bash scripts/smoke_test.sh
=== Résultat: 5 passed, 0 failed ===                  (exit 0)
$ bash scripts/smoke_test.sh                          # sans SMOKE_USER/SMOKE_PASS
ERREUR: SMOKE_USER et SMOKE_PASS doivent être exportés (…)   (exit 1)
$ SMOKE_PASS=mauvais … bash scripts/smoke_test.sh
=== Résultat: 3 passed, 2 failed ===                  (exit 1)
```

Écart documenté dans le script : la mission nomme `/api/projects`, qui
n'existe pas comme route de liste (seulement `/api/projects/{id}`) ; la
route de liste protégée est `/api/pm-orchestrator/projects`.

### A10 — `BACKLOG_TECH.md` supprimé, `SECURITY.md` créé *(commit `22c8a49`)*

```
$ ! test -f docs/BACKLOG_TECH.md && test -f docs/SECURITY.md && echo FIN OK
FIN OK
$ grep -nE "SecurePass|bot[0-9]{6,}:|sk-[A-Za-z0-9]{10,}|[0-9]{9,}" docs/SECURITY.md
(vide)
```

Le premier commit du lot écrivait le mot de passe PostgreSQL en toutes
lettres dans une commande `git log -S` tout en le disant « masqué » ; relu
par l'orchestrateur, renvoyé, amendé avant intégration. Inventaire établi
par grep : jeton de bot Telegram et `chat_id` **en clair dans `CLAUDE.md`**
et dans l'historique ; mot de passe PostgreSQL en dur dans trois fichiers
`backend/app/` (repli de `DATABASE_URL`) ; sept variables lues par le code et
absentes de `backend/.env.example`. Gestionnaire de secrets : « à décider ».

---

## 2. Non confirmé — constats qui ne se sont pas vérifiés dans le code

| Constat de la mission | Verdict |
|---|---|
| Référence « 461 / 24 / 7 / 118 » | **Infirmé dans ce bac à sable** : 474 / 11 / 7 / 118. Seul le 118 coïncide. |
| A5 : « un chunk `project_id=999` ne doit jamais sortir d'une requête concierge » | **Prémisse non confirmée.** `converse()` n'atteint aucune fonction du RAG, ni directement ni via `get_llm_router().complete()` (`llm_router_service.py` n'importe ni `rag`, ni `chroma`). Mesuré : espions posés sur `query_collection`, `query_rag`, `get_salesforce_context`, `get_code_context` — liste d'appels vide au terme d'un tour complet. Aucun cloisonnement à poser ; en inventer un aurait créé un dispositif déclaré et inopérant. Le test reste comme garde, et prouve qu'il détecterait un branchement futur. |
| A6 : « périmètre = le fichier qui journalise `[RAG HEALTH] OK` » | **Le fichier est `rag_service.py`, le défaut est dans son appelant** `main.py::startup_event`. `rag_health_check` est synchrone et c'est correct pour du disque ; `rag_service.py` n'a pas été modifié. |
| A3 / A4 : périmètres « exclusifs » | **Faux** : les deux lots listent `backend/app/models/subscription.py`. Traités en séquence, A4 puis A3. |
| A8 : `/api/projects` doit rendre 401 puis 200 | **Cette route de liste n'existe pas** ; la route protégée réelle est `/api/pm-orchestrator/projects`. |
| D1 : « la description "2000 crédits/mois" de `tier_config` est périmée » | **La description l'était, le chiffre ne l'était pas** : `monthly_credits` Pro vaut 15 000 depuis la migration `010_pro_tier_marcus_opus` (29/04). Seuls `price_eur_monthly` (49 → 79) et `description` étaient à corriger ; la migration 012 réaffirme 15 000 par défensivité. |
| A3 : « 4 tests crédits rouges à cause du chiffre » | **Cause double** : seed périmé **et** `tier="premium"` qui résout vers `team` par conception. Un des quatre (`…legacy_premium_to_pro`) contredit le mapping documenté et reste rouge (§3). |
| A10 : `EXECUTION.md` §5.3 annonçait 7 fichiers portant le mot de passe PostgreSQL | **3 confirmés** (`backend/app/`), les 4 fichiers de test/outillage cités ne portent plus le motif. |
| A10 : `docs/operations/secrets-rotation.md` décrit `GITHUB_TOKEN` dans `backend/.env` | **Infirmé** : c'est un identifiant `GIT_TOKEN` par projet, chiffré dans `project_credentials`. Document non corrigé (hors périmètre). |
| A1 : « httpx 0.28.1 » | **Confirmé** tel quel. |
| A7 : double `000`, sonde Spark absente, pas de mode test | **Confirmés** tels quels. |

---

## 3. Ouvert — ce qui reste, et pourquoi

> **Relecture Sam + Claude, 03/09.** A9 : clos sans correctif — `gemma`/`qwen`
> (ports 18080/18081) désignent le GPU Packet.ai, loué à la demande, où
> tournaient le 10/08 exactement Gemma 4 31B Q8 et Qwen 3.6 27B Q8 (llama.cpp).
> Les `display_name` sont justes ; LLM-DISPLAY (30/08) confondait avec les
> modèles du Spark, déclarés à part. Reste : `base_url_nemotron` (Spark) et
> `gemma` (Packet) partagent le port 18080 → vague B.
> `premium → pro` : le test était faux, corrigé en `→ team` (commit suivant).

- **A9 — `display_name` de `gemma` (port 8080) et `qwen` (port 8081) : à trancher par Sam.** Aucun commit. L'énoncé dit quelles chaînes doivent disparaître (« Gemma 4 31B », « Qwen 3.6 »), pas par quoi les remplacer. Le sous-agent a cherché une source indépendante du YAML : les seules occurrences sont dans `llm_routing.yaml` lui-même (lignes 199, 241, 270 ; 242, 276) ; `docs/benchmarks/local-llm-bench-2026-04-30/` décrit un bench Ollama CPU d'avril, pas le serveur GPU du 10/08 ; ADR-001 précède le GPU ; `CHANGELOG.md` s'arrête au 15/07 ; `PROGRESS.log` absent du clone. L'orchestrateur a complété par lecture seule sur le VPS : `PROGRESS.log` absent aussi, `/root/bin-gpu-demarrage.sh` ne lance que `gpt-oss-120b`, `curl 127.0.0.1:{18080,18081,18082,18083,18001}/v1/models` ne répond sur aucun port, le journal du comité ne nomme pas de version. Question précise : quels modèles exacts (nom et version, tels que lancés par `llama.cpp`) sont derrière `gemma` et `qwen` ? `display_name` n'est lu par aucun code Python (grep) : c'est de la documentation dans le YAML.
- **`test_credit_service::test_resolve_credit_tier_maps_legacy_premium_to_pro` reste rouge.** Son nom et son assertion (`premium → pro`) contredisent le mapping voulu et documenté (`credit_service.py:94`, migration 009 : `premium → team`). Deux issues : corriger le test (asserter `team`, le renommer), ou — si Sam veut réellement `premium → pro` — changer `credit_service.py` et la migration 009. Décision produit, hors A3.
- **Les 3 rouges de `test_auth` et celui de `test_emma_phase3`** préexistent à la vague et n'ont de lot dans aucun document. Non touchés.
- **RAG global non cloisonné par défaut** (trouvé par A5, hors périmètre) : `query_collection(project_id=None)` pose `where=None`, donc aucun filtre ; le concierge public n'est protégé que parce qu'il ne l'appelle pas. Un refus explicite serait cohérent avec la règle « jamais de repli silencieux ». Fichier `rag_service.py`, à arbitrer.
- **`sophie_concierge_service.py` lit `response.tokens_input`/`tokens_output`** (lignes 291-292, 309-310) alors que `LLMResponse` expose `tokens_in`/`tokens_out` (vérifié par exécution par A5). `chat_logs.tokens_*` sont donc toujours `NULL`. Le budget quotidien repose sur `cost_usd`, dont le nom est correct. Non corrigé : second changement sur la même branche.
- **A6 : la tâche de fond n'est pas annulée au shutdown.** Nettoyage dans `shutdown_event`, hors du périmètre « startup seulement ». En pratique la fermeture de la boucle attend l'exécuteur ; aucune nouvelle ligne `Task was destroyed` dans la suite.
- **`alembic upgrade head` casse sur une base vide** (trouvé par A8) : `007_backfill_project_conversations_agent_id` → `NoSuchTableError: project_conversations`. `AUTO_CREATE_SCHEMA=true` sert de repli pour les tests. Hors vague A.
- **`Pricing.tsx` hors Pro** : Free affiche 500 crédits/mois (D6 : 300/jour), Team 50 000 (D1 : 100 000 provisoire), FAQ « SDS ≈ 800 crédits » (D1 : ≈ 1 200). Le prompt concierge `sophie_pm.yaml` annonce « Pro €79/mois, 2 SDS/mois ». Listés par A3, non modifiés (voir aussi `rapport-kimi.md` COH-03 : une seule source, `tier_config`).
- **Secrets en clair dans le dépôt** (A10, `docs/SECURITY.md` §3) : jeton Telegram dans `CLAUDE.md`, mot de passe PostgreSQL dans trois fichiers `backend/app/`. Documentés, ni retirés ni rotés : gestes hors vague A et hors bac à sable.
- **Liens morts vers `docs/BACKLOG_TECH.md`** dans `docs/AGENT_BRIEF.md:31` et `docs/TASKS_MASTER.md:115` ; la spec « MOD40 » qu'il portait ne figure nulle part ailleurs.
- **Trailers de commit** : la consigne de la mission (« aucune mention de modèle ») et celle du harnais (trailer `Co-Authored-By` obligatoire) se contredisent ; quatre commits portent le trailer, quatre non. L'historique n'a pas été réécrit ; Sam tranche avant merge.

---

## 4. Non fait par choix

- **Aucun `git push`, aucun merge, aucune action sur `main`, `.env`, la base `digital_humans_db` ni les services systemd.** Le VPS n'a été touché qu'en lecture seule, pour A9 (§3), sans aucune écriture.
- **A9 non « corrigé » par un nom plausible.** Un `display_name` inventé aurait été une invention sourcée par rien ; un nom générique aurait supprimé une information que Sam peut vouloir exacte.
- **A5 : `sophie_concierge_service.py` non modifié.** Poser un filtre sur un chemin qui n'existe pas serait un dispositif déclaré et inopérant.
- **A6 : pas de `rag_health_check_async()` dans `rag_service.py`**, pas de conversion `on_event` → `lifespan` : deux chemins à maintenir pour zéro gain, et hors périmètre.
- **A1 : `requirements-test.txt` non allégé** bien que son plafond httpx soit désormais dupliqué : il « fait autorité » pour l'environnement de test (vague 2) et se lit seul.
- **A10 : `docs/operations/secrets-rotation.md`, `docs/AGENT_BRIEF.md`, `docs/TASKS_MASTER.md` non corrigés** : hors périmètre.
- **Aucune rotation de secret, aucune migration exécutée ailleurs que sur `digital_humans_test_a3`.**
- **Les 11 valeurs mortes de `resume_from`, `validation_gate_routes.py:211`, `test_deployment_cloisonnement`** (EXECUTION_VAGUE2.md §7) restent hors vague A.

---

## 5. Journal et ligne pytest finale

`main` n'existe pas en local dans le bac à sable ; `origin/main` = `d9798f6`,
base annoncée de la branche.

```
$ git log --oneline origin/main..HEAD
fff74fc fix(A3): Pro 79 €/mois, crédits 15 000 — description tier_config réalignée (D1, D4)
52b2008 fix(A4): retirer la clé de feature morte llm_haiku
47065b1 test(A5): garde de non-regression — le concierge public n'atteint pas le RAG
b454a93 fix(A6): sortir le comptage RAG de la boucle d'evenements au demarrage
22c8a49 docs(A10): supprimer BACKLOG_TECH.md, créer SECURITY.md (inventaire secrets)
3c4839b fix(A8): réécrire scripts/smoke_test.sh avec des assertions justes
51921ee fix(A7): watchdog - double 000, sonde Spark, mode DRY_RUN, systemctl absent
244829f fix(A2): epingler arq et redis dans requirements.txt
9087728 fix(A1): plafonner httpx sous 0.28 pour remettre 118 tests en jeu
f03053a Mission vague A : environnement = bac a sable Claude Code, pas le VPS
b78d354 D1 tranchee : Pro = 15 000 credits/mois
8a188ef Vague A : mission et decisions de Sam posees sur la branche
```

(plus le commit qui porte ce document.) Aucun commit A9 : lot bloqué, §3.

Suite complète rejouée par l'orchestrateur sur `fff74fc`, base
`digital_humans_test`, venv `backend/venv` (Python 3.12.3) :

```
$ cd backend && python -m pytest tests/ -q -p no:cacheprovider
5 failed, 616 passed, 7 xfailed, 1034 warnings in 390.67s (0:06:30)

FAILED tests/test_auth.py::test_login_success - assert 401 == 200
FAILED tests/test_auth.py::test_get_current_user_success - KeyError: 'access_...
FAILED tests/test_auth.py::test_get_current_user_no_token - assert 401 == 403
FAILED tests/test_credit_service.py::test_resolve_credit_tier_maps_legacy_premium_to_pro
FAILED tests/test_emma_phase3.py::TestWBSAfterValidation::test_wbs_requires_validation_success
$ grep -c "^ERROR tests" /tmp/pytest_final.log
0
```

Critères de fin rejoués par l'orchestrateur sur la même tête :

```
$ grep -nE '^(httpx|arq|redis)' backend/requirements.txt
26:httpx>=0.27.0,<0.28   58:arq==0.28.0   59:redis==5.3.1
$ grep -cE "[^0-9 ]49€" frontend/src/pages/Pricing.tsx            → 0
$ grep -q '79 €/mois' backend/app/models/subscription.py          → OK
$ grep -c llm_haiku backend/app/models/subscription.py            → 0
$ bash -n scripts/dh-watchdog.sh && bash -n scripts/smoke_test.sh → OK
$ grep -c 'display_name:.*\(Gemma 4 31B\|Qwen 3.6\)' backend/config/llm_routing.yaml → 2 (A9 non traité)
$ ! test -f docs/BACKLOG_TECH.md && test -f docs/SECURITY.md      → FIN OK
$ python -m py_compile app/services/sophie_concierge_service.py app/main.py → OK
```

Pas de merge. Pas de push. Sam relit.
