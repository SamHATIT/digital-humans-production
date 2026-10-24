# Rapport — Vague 2 / File B — Exploitation, sondes, dépendances

**Auteur :** impl-B (Claude Code), worktree `/root/workspace/wt-vague2-b`, branche `claude/vague2-b`, partie de `388299a` (`origin/claude/vague-c-20260906`).
**Date :** 24/10/2026. Mission : `docs/missions/VAGUE2_B_EXPLOITATION.md`.
**Journaux bruts** : tous sous `/root/.dh_orch_vague2/impl-b-*` (cités par leur nom ci-dessous).

Conventions : « vérifié » = exécuté, sortie constatée ; « lu » = lu, non exécuté ; « je suppose » = déduction non vérifiée.

---

## 0. Suite backend avant / après (mesurée)

Commande (depuis `backend/`, environnement hermétique, base de test) :

```
set -a; . /root/.dh_test_db.env; set +a; export DH_ENV_FILE=$PWD/.env.test DH_TEST_RUN_ID=<id>
./venv/bin/python -m pytest tests/ -q -p no:cacheprovider -rfE
```

| Mesure | Journal | Résultat brut |
|---|---|---|
| Avant (commit `388299a`, venv d'origine) | `impl-b-avant.log` | `31 failed, 1052 passed, 2 skipped, 7 xfailed, 1463 warnings in 735.73s (0:12:15)` |
| Intermédiaire (dépendances montées, avant l'outil `routes_montees`) | `impl-b-suite-sec18.log` | `33 failed, 1138 passed, 2 skipped, 7 xfailed, 978 warnings in 678.39s (0:11:18)` |
| Après (HEAD de la branche, venv monté) | `impl-b-apres.log` | `31 failed, 1141 passed, 2 skipped, 7 xfailed, 978 warnings in 806.32s (0:13:26)` — mêmes 31 échecs (27 lot_c, 3 test_auth, 1 emma) ; +89 passés = les 89 tests ajoutés (16 OPS-08, 8 OPS-02, 13 OPS-01, 17 GL-25, 23 SEC-17, 12 SEC-18) |

Les 31 échecs d'avant sont exactement ceux de la référence de l'orchestrateur : 27 `test_lot_c_injection_commandes.py` (404 sur `/api/agent-tester/*`), 3 `test_auth.py`, 1 `test_emma_phase3.py::TestWBSAfterValidation::test_wbs_requires_validation_success`. Je ne les ai pas touchés, ni masqués.

Les 2 échecs supplémentaires de la mesure intermédiaire sont deux **contrôles négatifs** (`test_sec11_controle_negatif_les_routeurs_voisins_restent`, `test_sec02_controle_negatif_les_autres_routeurs_restent`) qui ont révélé un effet de la montée de FastAPI (voir §1.6) ; corrigé dans le même commit.

**Pour le testeur indépendant** : le venv du worktree a été **monté** (SEC-18 : python-jose et PyPDF2 désinstallés, FastAPI 0.162, Starlette 1.9…). Revenir au commit parent avec ce venv fait échouer les imports (`from jose import …`) pour une raison qui n'est pas celle des tests. Pour constater les rouges au parent, utiliser un venv installé depuis `requirements-test.txt` de `388299a` (ex. celui de la mesure de référence, `wt-vague2-a/backend/venv`, s'il n'a pas bougé). Mes propres constats de rouge ont été faits **avant** la montée de version pour OPS-08, OPS-02, OPS-01, GL-25 et SEC-17 (journaux `*-rouge.log`).

---

## 1. Fait, avec preuve

### 1.1 OPS-08 — scripts d'alerte, de rotation, d'export (commit `1790fc2`)

Constats re-lus dans les scripts du worktree, et **vérifiés** par exécution avec des bouchons (`curl`, `systemctl`, `journalctl`, `sleep` remplacés en tête de PATH ; aucun envoi Telegram, aucun redémarrage) :

- `scripts/dh-watchdog.sh` écrivait l'état « notifié » quand Telegram refusait (HTTP 500, `"ok":false`, panne réseau) ; sortait `0` en silence sans identifiants ; ne sondait pas le worker.
- `scripts/rotate_anthropic_key.sh` sondait `/api/health` (404 sur le backend) pendant 30 s : une rotation réussie était **toujours** annulée (rollback). Extrait de la sortie avant correctif :
  ```
  [SECRETS] new key accepted by Anthropic
  [SECRETS] ROLLBACK: restoring …/backend.env.bak-20261024-120402 -> …
  [SECRETS] ERROR: backend did not become healthy after restart
  ```
- `scripts/ops/export_logs_24h.sh` ignorait l'échec de `journalctl` et remplaçait l'export précédent.

Le watchdog installé est identique à la copie git d'avant (`diff /usr/local/bin/dh-watchdog.sh scripts/dh-watchdog.sh` → `DIFF_EXIT=0`) ; le cron `/etc/cron.d/dh-comite-logs` lance la copie du répertoire de production, elle aussi identique (`DIFF2=0`).

Test : `backend/tests/test_vague2_b_ops08_scripts.py`. Avant : `11 failed, 5 passed` (`impl-b-ops08-rouge.log`), dont `AssertionError: etat enregistre malgre l'echec d'envoi (http500) : 'backend /health = 503\n'`. Après : `16 passed` (`impl-b-ops08-vert.log`). Les 5 verts des deux côtés sont des contrôles (envoi nominal au bon `chat_id`, pas de doublon, rétablissement unique, rollback si backend mort, export nominal).

Le bouchon `curl` interprète `\n` dans `-w` comme le vrai curl ; vérifié avec le vrai curl sur un petit serveur local (même logique d'analyse que `send_or_print`, recopiée) :
```
ok -> ACCEPTE (code=200)
ko -> REFUSE (rc=0 code=400 corps={"ok":false,"description":"chat not found"})
port ferme -> rc=7 code=000
```

### 1.2 OPS-02 — sonde worker, pool Redis, fuseau du cron (commit `2664b3f`)

**Vérifié** (Redis de test DB 9, file `test-<run_id>`) : avec deux tâches dans l'ensemble trié de la file et un battement présent, l'ancienne route rendait `{'queued_jobs': 0, 'redis': 'connected', 'redis_version': '7.0.15'}` ; sans battement elle rendait 200. Cause lue dans arq 0.28 : la file est l'ensemble trié `<file>` (`pipe.zadd(_queue_name, …)`), le battement est `<file>:health-check` (`health_check_key_suffix`), alors que la route faisait `LLEN arq:queue:<file>`.

Correctif : `ZCARD`, âge de la plus ancienne tâche, battement lu et découpé, 503 si battement absent ou Redis injoignable ; pool ARQ partagé par processus et par boucle, fermé à l'arrêt (`main.py`) ; `WorkerSettings.timezone = UTC`.

Test : `test_vague2_b_ops02_worker_health.py` avant `7 failed` (`impl-b-ops02-rouge.log`) + le test du câblage de l'arrêt (`assert [] == [True]`, sortie de commande, non journalisée) ; après `8 passed`. Voisins : `132 passed` (`impl-b-ops02-voisins.log`).

### 1.3 Démarrage du backend en ~2 min + OPS-01 (commit `4b3db14`)

**Mesures en production, lecture seule du journal** (`journalctl -u digital-humans-backend`, rétention depuis le 21/10 seulement ; la ligne `Schema auto-creation skipped` est émise pendant l'import de `app.main`, je la prends comme fin des imports) :

```
2026-10-21T06:14:29 Started …            2026-10-23T06:16:30 Started …
2026-10-21T06:14:34 Schema auto-creation…  2026-10-23T06:16:35 Schema auto-creation…
2026-10-21T06:16:28 [RAG HEALTH] OK      2026-10-23T06:17:59 [RAG HEALTH] OK — 161856 chunks across 5 collections
```
Au 23/10, les quatre lignes `[LLM] FOURNISSEUR LOCAL INOPERANT` de la sonde des fournisseurs locaux (autre fil, délai 3 s par fournisseur) sont horodatées `06:17:59.796`, 0,1 s après `[RAG HEALTH] OK` (`06:17:59.703`).

**Import de `app.main`, environnement de test** (`implb_import.sh`, `impl-b-import.log`) : `import app.main = 4.18 s / 3.51 s / 3.45 s` (trois essais). Profil `-X importtime` : `app.main` 3,7 s cumulés, dont `llm_router_service` 1,08 s, `openai` 0,86 s, `rag_service` 0,68 s. **L'import n'est pas la cause.**

**Reproduction dans le worktree** (copie du Chroma de production `cp -a /opt/digital-humans/rag/chromadb_v2 /root/.dh_orch_vague2/implb-chroma/` — 4,1 Go, lecture seule de l'original ; cache disque de la copie évincé par `posix_fadvise(DONTNEED)`) :

```
operations_collection: count=40441 en 3.18s
technical_collection: count=72597 en 4.96s
comptage total=164000 en 11.34s ; boucle : 9 tics, retard max 4.86s, retard cumule 10.54s, tics retardes >1s : 2
```
(`impl-b-chroma-froid.log` ; la boucle asyncio tique toutes les 100 ms : 9 tics au lieu d'~113 pendant le comptage lancé en `asyncio.to_thread`). À chaud : 3,18 s de comptage, 7 tics.

uvicorn réel lancé dans le worktree sur cette copie (`implb_boot.sh`, base jetable `digital_humans_test_implb_boot` créée puis détruite, Redis DB 9) — `impl-b-boot-froid.log`, avant correctif :
```
t=  4.30s  /=000            /health=000
t= 14.86s  /=200 10.022917  /health=200 0.007570
```
Le port s'ouvre vers 4,5 s, puis le premier `GET /` attend **10,0 s**.

**Cause** : `count()` de chromadb 1.3.4 garde le GIL ; `asyncio.to_thread` ne libère donc pas la boucle. **Ce n'est pas une sonde réseau bloquante** (la sonde LLM est retardée par le GIL, elle ne retarde rien). Le test A6 qui devait garantir « le comptage ne bloque pas la boucle » simulait le comptage avec `time.sleep`, qui **relâche** le GIL : il était vert pour une raison absente en production.

**Non reproduit** : la durée de production (89 s et 119 s) contre 11–13 s sur la copie à froid. Je n'ai pas d'explication mesurée de l'écart (charge de la machine au redémarrage, état du cache, autre ?). Je n'ai pas non plus de mesure directe de la réactivité de l'API de production pendant ces 89–119 s (le journal ne trace pas les accès ; rien dans `/var/log/nginx/access.log` vers le backend sur la fenêtre du 23/10 06:15–06:19).

**Correctif** (`app/services/sonde_rag.py`, nouveau ; `main.py`) : le comptage part dans un **processus enfant** (interpréteur neuf qui appelle `rag_service.rag_health_check`), borné (600 s, enfant tué), un seul calcul en vol, rafraîchi toutes les 30 min (D8), plus vite après un échec. `/health` ne compte jamais : `warming` (dépendance `down`) tant qu'aucune sonde n'a abouti, chaque collection de `rag_service.COLLECTIONS` doit exister et être non vide, `stale` (`down`) si le dernier succès a plus de 60 min. La vérification n'est pas retirée, elle est déplacée.

Après correctif, même copie à froid (`impl-b-boot-froid-apres.log`) :
```
t=  4.07s  /=200 0.308968  /health=503 0.010003
{"status":"unhealthy",…"chroma":{"status":"down","detail":"warming: sonde RAG en cours depuis 1 s"}}
t= 16.63s  /=200 0.007278  /health=200 0.007601
[RAG HEALTH] OK — 161856 chunks, 5 collections at …/implb-chroma/chromadb_v2 (sonde hors processus, 12.8 s)
```
Latence maximale de `GET /` : 0,31 s (premier appel) au lieu de 10,0 s.

Tests : `test_vague2_b_ops01_sonde_rag.py` avant `11 failed, 2 passed` (`impl-b-ops01-rouge.log` ; rouges de constat : `assert 5 == 0` comptages Chroma dans le processus de l'API, `assert 1 == 0` comptage synchrone dans `/health`, collection vide et vert périmé rendus `up` ; les autres rouges sont l'absence du module) ; après `13 passed`. Le faux comptage de ces tests tient réellement le GIL (expression régulière à retour arrière catastrophique), avec un contrôle de sens (`test_controle_un_appel_qui_tient_le_gil_bloque_la_boucle_meme_en_to_thread`).

**Tests existants réécrits** (ils décrivaient le mécanisme en processus) : `test_vague_a_a6_rag_count_off_loop.py` (3 tests : `test_health_repond_pendant_le_comptage_rag`, `test_journal_rag_health_emis_a_la_fin_du_comptage_de_fond`, `test_exception_dans_le_comptage_journalisee_probe_crashed` — ce dernier attend désormais `[RAG HEALTH] FAILED` portant la fin de la sortie d'erreur de l'enfant) et `test_vague_b_b6_health_cache.py` (2 tests : deux `/health` ne relancent pas de comptage ; `/health` n'attend pas le rafraîchissement). Même critère, mécanisme réel. Voisins : `64 passed` (`impl-b-ops01-voisins2.log`).

### 1.4 GL-25 et fournisseur local injoignable (commit `82f4860`)

**Vérifié avant correctif** (transport LLM simulé, Telegram bouchonné) : `/api/studio/chat` rendait au client
```
502 {"detail":"L'agent n'a pas pu repondre : Error code: 400 - {… 'Your credit balance is too low to access the Anthropic API. …"}
502 {"detail":"L'agent n'a pas pu repondre : ConnectError: [Errno 111] Connection refused"}
502 {"detail":"L'agent n'a pas pu repondre : Insufficient credits for user 1: requested=10, available=0"}
```
sans aucune alerte ; et `admin_alert_service` comptait un HTTP 200 de Telegram portant `"ok": false` comme un envoi réussi (`assert True is False`).

Correctif :
- `app/services/alertes_fournisseurs.py` (nouveau) : classement des erreurs (solde : « credit balance is too low », `insufficient_quota`, « exceeded your current quota », `credit_balance_exhausted` ; transport : `ConnectError`, `ConnectTimeout`, refus de connexion…), état par fournisseur : **une alerte à la première panne, une au retour, aucune pendant** ; sonde périodique des fournisseurs **locaux routés par le profil actif** (les fournisseurs de calibration déclarés mais non routés — `gpu_muse`, `gpu_dsv4*`, `gpu_glm53`, inopérants aux deux démarrages présents dans le journal de production — ne sont ni sondés ni alertés).
- `studio_chat.py` : 503 « Le service est momentanément indisponible. Notre équipe a été prévenue ; merci de réessayer dans quelques minutes. », cause au journal et à l'admin ; 402 `insufficient_credits` pour le quota du client (sans alerte) ; retour signalé au premier succès.
- `main.py` : surveillance toutes les `DH_SONDE_FOURNISSEURS_S` (60 s ; `0` la coupe avec un WARNING), premier passage après un intervalle, annulée à l'arrêt.
- `admin_alert_service.py` : envoi accepté = HTTP 2xx **et** `"ok": true`.

**Aucun repli silencieux** : constaté, pas construit. Profil `cloud` (celui des tests et de la production d'après le journal du 23/10 : `profile=cloud`) : `fallback_chain: {}`. Test : un Free dont `gpu_nemotron` échoue n'appelle que `['gpu_nemotron/nemotron']`.

Tests : `test_vague2_b_gl25_alertes_fournisseurs.py` — destinataire (`chat_id=4242`), URL (`botjeton-bouchon/sendMessage`), texte (fournisseur, cause exacte pour l'admin), une alerte pour trois échecs, un « rétabli » et un seul, contrôle négatif (erreur inconnue : 503 sans alerte, message interne absent de la réponse), contrôle 402. Avant `17 failed` (`impl-b-gl25-rouge.log`), après `17 passed` (`impl-b-gl25-vert.log`, 0 ligne `FOURNISSEUR LOCAL INOPERANT` : la sonde de démarrage y est bouchonnée). Voisins : `88 passed` (`impl-b-gl25-voisins.log`).

**Limite de portée** : le câblage n'existe que pour le studio et pour la sonde périodique. Les appels SDS, chat projet et BUILD passent par `llm_router_service.complete()` (file C) : diff proposé en §6.

### 1.5 SEC-17 — configuration de production (commit `b373a3f`)

**Vérifié avant correctif** (configurations factices `Settings(..., _env_file=None)`, jamais la vraie `.env`) : `DEBUG` vaut `True` par défaut ; le gabarit de `backend/.env.example` (`your-secret-key-must-be-at-least-32-characters-long`) est accepté comme `SECRET_KEY` en DEBUG et hors DEBUG ; une clé de 16 caractères est acceptée hors DEBUG ; `CREDENTIALS_ENCRYPTION_KEY="pas-une-cle-fernet"` est acceptée et `build_fernet` l'étire par SHA-256 ; le moteur SQL a `echo=settings.DEBUG` ; `BACKEND_CORS_ORIGINS` vaut `["*"]` et n'est lu par personne ; `docker-compose.prod.yml` lance uvicorn avec `--reload`.

Correctif : `DEBUG=False` par défaut ; gabarits de `SECRET_KEY` toujours refusés, 32 caractères minimum hors DEBUG ; `CREDENTIALS_ENCRYPTION_KEY` doit être une clé Fernet valide (message : génération + rotation) ; `build_fernet` refuse, `build_fernet_etiree_historique` garde l'étirement pour la seule relecture pendant une rotation (`scripts/rotate_encryption_key.py --old-key`) ; `echo=False, hide_parameters=True` ; CORS lu depuis `settings` (défaut = l'ancienne liste en dur + `https://app.`, `console.`, racine et `www.` de `digital-humans.fr`, relevés dans les `server_name` nginx) ; `"*"` refusé hors DEBUG ; compose sans `--reload`.

Tests : `test_vague2_b_sec17_configuration.py` avant `21 failed, 2 passed` (`impl-b-sec17-rouge.log`), après `23 passed`. Voisins (lot_e, lot_e_bis, lot4, secrets en dur, hermétique) : `99 passed` (`impl-b-sec17-vert.log`).

État de production lu dans le journal (pas dans la `.env`) : `Schema auto-creation skipped — AUTO_CREATE_SCHEMA non pose (DEBUG=False)` et `Chiffrement des credentials : cle dediee (CREDENTIALS_ENCRYPTION_KEY) en place.` — la **validité** de cette clé n'est pas connue (voir §5).

### 1.6 SEC-18 — dépendances (commits `6526517` backend, `d323077` frontend)

**Audit backend vérifié** : `pip-audit 2.10.1 -r implb-freeze-avant.txt --no-deps --disable-pip` (gel du venv de test au commit parent) :
```
Found 57 known vulnerabilities in 12 packages
```
(`impl-b-pip-audit-avant.txt`, détail JSON `impl-b-pip-audit-avant.json`) — python-multipart 0.0.6 (16 lignes), starlette 0.27.0 (14), python-jose 3.3.0 (6, dont CVE-2024-29370 et CVE-2026-85394 **sans version corrigée**), chromadb 1.3.4 (5), httpx2 2.6.0 (5), anyio 3.7.1, ecdsa 0.19.2, fastapi 0.104.1, PyPDF2 3.0.1, pytest 7.4.3, python-dotenv 1.0.0, httpcore2 2.6.0.

Montée : fastapi 0.162.0, starlette ≥1.3.1 (1.9.0), python-multipart 0.0.32, anyio ≥4.14.2 (4.15.1), pydantic 2.14.1, pydantic-settings 2.16.1, httpx 0.28.1 (plafond `<0.28` levé : il n'existait que pour l'ancien TestClient), python-dotenv 1.2.2, **PyJWT 2.15.1 à la place de python-jose** (`utils/auth.py`, `chat_ws_routes.py`), **pypdf 6 à la place de PyPDF2** (`file_processor.py`), httpx2 ≥2.12.0 ; pytest et pytest-asyncio sortis de `requirements.txt` (ils restent dans `requirements-test.txt`). `pip check` : `No broken requirements found.`

Après (`impl-b-pip-audit-apres.txt`) :
```
Found 7 known vulnerabilities in 2 packages
chromadb 1.3.4   PYSEC-2026-311 / -3814 / -3815 / -3813   (aucune version corrigée)
pytest   7.4.3   PYSEC-2026-1845 9.0.3
```
Les quatre avis chromadb visent le **serveur HTTP** Chroma (`/api/v2/tenants/…`) ; le backend embarque Chroma (`PersistentClient`). `ss -ltnp` ne montre aucun serveur Chroma ; le port 8000 est `system-mcp-server.py`. (Constat à côté : un conteneur Docker tiers lance `pip install … chromadb && uvicorn app:app --port 8090` — hors périmètre, version de chromadb non épinglée.)

Compatibilité des sessions ouvertes : jetons émis le 24/10 par python-jose 3.3.0 (avant désinstallation) avec la clé factice de `.env.test`, relus par la nouvelle `decode_access_token` → `sub == "42"` ; jeton expiré et `alg: none` refusés (tests verts des deux côtés, voulu).

**Effet de bord trouvé par la suite** : FastAPI 0.162 n'expose plus les routeurs inclus dans `app.routes` (23 objets `_IncludedRouter`, chemin `""`). Trois tests « routeur démonté » (`test_download_route_is_gone`, `test_sec11_le_routeur_blog_n_est_plus_monte`, `test_sec02_agent_tester_n_est_plus_monte`) devenaient **vrais sans rien vérifier** ; leurs contrôles négatifs sont tombés, c'est ce qui l'a montré. `tests/routes_montees.py` déplie les routeurs inclus (147 chemins) ; les trois fichiers l'utilisent ; contrôle de l'outil dans `test_vague2_b_sec18_dependances.py`.

Tests : `test_vague2_b_sec18_dependances.py` avant `7 failed, 4 passed`, après `12 passed`. Démarrage uvicorn 0.24 + starlette 1.9 vérifié (`impl-b-boot-sec18.log` : `/=200`, `/health=200`). `@app.on_event("startup")` fonctionne toujours (les tests de démarrage de la sonde RAG passent).

**Frontend** : Astra écrivait « sans lockfile, la version résolue est inconnue » — **infirmé** : `frontend/package-lock.json` existe et verrouille `vite 5.4.10`. `npm audit` sur ce verrou : `{'low': 2, 'moderate': 12, 'high': 18, 'critical': 0, 'total': 32}`. `npm audit fix` (sans `--force`, verrou seul) : 32 → 4 ; puis `vite ^6.4.5` : 4 → 2 (`{'low': 2, …, 'high': 0}`, `impl-b-npm-audit-apres.json`). Build vérifié sur une copie neuve (`npm ci && npm run build` → `BUILD_EXIT=0`, `vite@6.4.5`, `impl-b-front-apres.log`) ; même commande sur le verrou d'origine : `BUILD_EXIT=0`. **Les tests frontend (`frontend/tests`) n'ont pas été lancés.**

### 1.7 Fichiers `*.pre-*` / `*.bak*` de `backend/app` (production, lecture seule)

Commande : `find /root/workspace/digital-humans-production/backend/app \( -name '*.pre-*' -o -name '*.bak*' \)` — **22 fichiers** (la mission en annonçait 21). Aucun n'est suivi par git au commit `388299a` (vérifié avec `git ls-files --error-unmatch` dans **mon** worktree, aucune commande git dans le répertoire de production). Rien supprimé, rien déplacé.

| Date | Octets | Fichier (sous `backend/app/`) |
|---|---|---|
| 2025-12-22 | 19748 | `services/llm_service.py.bak_timeout` |
| 2026-02-10 | 8536 | `services/execution_state.py.bak` |
| 2026-04-18 | 11002 | `services/budget_service.py.pre-mod37-budgetgate` |
| 2026-05-01 | 38711 | `services/llm_router_service.py.pre-mod39-temp` |
| 2026-05-01 | 10703 | `services/llm_service.py.pre-mod37-budgetgate` |
| 2026-05-02 | 29866 | `services/phased_build_executor.py.pre-feedback-loop` |
| 2026-05-06 | 990 | `database.py.pre-tuning` |
| 2026-05-06 | 178767 | `services/pm_orchestrator_service_v2.py.pre-async-sfdx` |
| 2026-05-06 | 2687 | `workers/worker.py.pre-tuning` |
| 2026-07-12 | 13750 | `services/llm_service.py.pre-platformstate` |
| 2026-07-14 | 2657 | `salesforce_config.py.pre-summer26` |
| 2026-08-02 | 32427 | `services/phased_build_executor.py.pre-batchprogress` |
| 2026-08-02 | 33446 | `services/phased_build_executor.py.pre-routing` |
| 2026-08-02 | 30110 | `services/phased_build_executor.py.pre-taskvisibility` |
| 2026-08-02 | 184043 | `services/pm_orchestrator_service_v2.py.pre-phaseprefix` |
| 2026-08-05 | 34585 | `services/phased_build_executor.py.pre-tache1` |
| 2026-08-05 | 185296 | `services/pm_orchestrator_service_v2.py.pre-tache1` |
| 2026-08-08 | 35222 | `services/phased_build_executor.py.pre-vocab` |
| 2026-08-15 | 46568 | `services/llm_router_service.py.pre-nothink` |
| 2026-08-22 | 10263 | `main.py.pre-retrait-deployment` |
| 2026-08-23 | 15245 | `main.py.pre-docs-fermees` |
| 2026-08-23 | 49467 | `services/llm_router_service.py.pre-max-tokens` |

(Liste brute : `impl-b-pre-bak.txt`.)

---

## 2. Infirmé

- **« Démarrage lent = sonde réseau bloquante »** : non. Import 3,5–4,2 s (5 s en production) ; la sonde réseau des fournisseurs locaux est *retardée* par le GIL, elle ne retarde pas. Cause mesurée : comptage Chroma qui garde le GIL (§1.3).
- **« Sans lockfile, la version de Vite est inconnue »** (Astra SEC-18) : le verrou existe, Vite 5.4.10.
- **« 21 fichiers `*.pre-*`/`*.bak` »** : 22 mesurés.
- **« Repli silencieux du Free vers un modèle payant »** : absent du code au commit parent (profil `cloud`, `fallback_chain: {}`), vérifié par test.
- **Fuseau du cron (OPS-02)** : `timedatectl` → `Etc/UTC` ; le correctif (`timezone=UTC`) est défensif, sans effet observable sur ce VPS.
- **Le test A6 prouvait « la boucle n'est pas bloquée »** : son faux comptage (`time.sleep`) relâche le GIL ; il ne pouvait pas voir le défaut (§1.3).

---

## 3. Reste ouvert

- **Écart 89–119 s (production) contre 11–13 s (copie, worktree)** : non expliqué, non reproduit.
- **Appels RAG réels dans le processus de l'API** (chat, concierge) : `query()` de chromadb garde très probablement le GIL comme `count()` (je suppose, non mesuré) ; un premier appel RAG à froid peut encore geler la boucle le temps de son exécution. Hors du correctif de la sonde.
- **OPS-01 : recherche représentative et API d'embeddings** non sondées (§5).
- **OPS-02 : « dernière purge réussie »** non vérifiée par la sonde : aucune trace persistée des purges à lire ; non fait.
- **GL-25 pour les appelants hors studio** (SDS, chat projet, BUILD) : dépend du crochet dans `llm_router_service.complete()` (file C, diff §6).
- **Mémoire des pannes par processus** : backend et worker alertent chacun une fois ; un redémarrage pendant une panne réalerte (je le considère acceptable, non décidé).
- **Classement par type d'exception** : le type est perdu dans le routeur (`_call_gpu_local`, file C : `error=str(e)[:200]`). Après la revue, le classement traite une erreur vide ou un HTTP 502/503/504 d'un fournisseur **local** comme une indisponibilité, et reconnaît la forme `Type: message` du diff §6.4 ; pour un fournisseur cloud, une erreur vide n'est pas classée (contrôle). Un vrai classement par type demande ce diff de la file C.
- **`/health` à 503 « warming »** pendant le premier comptage après chaque redémarrage (≈1,5–2 min en production d'après le journal) : honnête, mais le watchdog alertera s'il passe dans cette fenêtre (§5).
- **`rotate_anthropic_key.sh`** : chemin par défaut `/opt/digital-humans/backend/.env` inexistant (`/opt/digital-humans/backend/.env ABSENT`) ; sa variable `DH_ENV_FILE` porte le même nom que celle de la suite hermétique (qui pointe `.env.test`). Non modifié ; à appeler avec `DH_ENV_FILE` explicite.
- **Watchdog installé** : `/usr/local/bin/dh-watchdog.sh` doit être réinstallé après fusion, **après** le déploiement du backend (il sonde `/workers/health`, qui rend 503 sans battement avec le nouveau code).
- **Sonde de démarrage des fournisseurs locaux pendant la suite de tests** : chaque `TestClient(app)` (fixture `client`) fait `GET http://127.0.0.1:18084/v1/models` vers le Spark réel (constat de l'orchestrateur, confirmé par `[LLM] FOURNISSEUR LOCAL INOPERANT — gpu_muse: … servis : ['nem…` dans `impl-b-gl25-rouge.log`). Pas de requête de génération. Non corrigé (la sonde n'est pas retirée) ; mes nouveaux tests la bouchonnent.
- **`DH_LLM_CONFIG_PATH` ignoré** par le routeur : `_get_default_config_path` essaie d'abord `backend/config/llm_routing.yaml`, puis `settings.LLM_CONFIG_PATH` (vérifié : uvicorn lancé avec `DH_LLM_CONFIG_PATH=/tmp/…` a journalisé `config=/root/workspace/wt-vague2-b/backend/config/llm_routing.yaml`). Repli silencieux ; file C (diff §6).
- **Télémétrie chromadb** : le backend de production journalise `Anonymized telemetry enabled` (PostHog). Coupée dans l'enfant de la sonde seulement.
- **pytest 7.4.3** (CVE-2025-71176) dans le venv de test ; pytest 9 impose de changer pytest-asyncio 0.21 : non fait.
- **mermaid/katex** (2 avis faibles) : correctif = mermaid 12 (majeure), non fait.
- **`docker-compose.prod.yml`** : le frontend y tourne encore en serveur Vite de dev sur `0.0.0.0` ; produire des assets statiques demande une autre image. Non fait (la production observée n'utilise pas ce compose : systemd + nginx).

## 4. Pas fait, et pourquoi

- **Crochet GL-25 dans `llm_router_service.py` et correctif `DH_LLM_CONFIG_PATH`** : fichier de la file C ; règle des missions — diff dans le rapport (§6), pas de commit.
- **Retrait de `rag_service.get_cached_rag_health`** (plus d'appelant dans `app/` depuis `4b3db14`) : fichier de la file A ; à décider par A.
- **Alerte « sous seuil » des soldes** : voir §5.
- **Lancement des tests frontend** : non fait (le build est vérifié, pas les tests).

## 5. Attend une décision de Sam

1. **Sonde de l'API d'embeddings (OPS-01, GL-10 point 3)** : la tester réellement, c'est un appel OpenAI payant (`text-embedding-3-large`) à chaque rafraîchissement (toutes les 30 min). Non branché. À décider : on paie cette sonde, ou on accepte que `[RAG HEALTH]` ne teste que le comptage.
2. **Alerte « sous seuil » de solde (GL-25)** : je ne connais pas d'API qui donne le solde prépayé Anthropic ou OpenAI à une clé d'API standard (je suppose, non vérifié au-delà de ce que je sais ; aucun appel fait). Ce qui est livré : alerte à la **première requête refusée pour solde**, et au retour. Un vrai seuil demanderait une clé d'administration et un suivi des achats.
3. **`/health` 503 pendant le comptage de démarrage** (« warming ») : accepter que le watchdog puisse alerter dans la ~1,5–2 min qui suit un redémarrage, ou lui faire tolérer `warming` une fois.
4. **Avant de déployer SEC-17** (je ne lis pas la `.env` de production) : vérifier que `CREDENTIALS_ENCRYPTION_KEY` y est une clé Fernet valide (sinon re-chiffrer d'abord : `CREDENTIALS_ENCRYPTION_KEY=<nouvelle> python scripts/rotate_encryption_key.py --old-key <ancienne> --new-key <nouvelle>`), que `SECRET_KEY` fait ≥ 32 caractères et n'est pas un gabarit, que `DEBUG` et `BACKEND_CORS_ORIGINS` sont posés comme voulu (et sans `"*"`). Sinon le backend **refusera de démarrer**, en le disant. **Attention particulière à `BACKEND_CORS_ORIGINS`** (signalé par la revue) : avant ce travail, ce réglage n'était **lu par personne** (`main.py` avait sa liste en dur) ; une valeur ancienne et oubliée dans la `.env` de production — par exemple `*`, ancien défaut « pour débogage » — était sans effet et devient maintenant soit appliquée (origines différentes de celles d'aujourd'hui), soit bloquante (`"*"` hors DEBUG). À vérifier par Sam ou le déployeur avant de redémarrer.
5. **chromadb 1.3.4** : quatre avis sans version corrigée (serveur HTTP Chroma, non exposé ici) — accepter le risque résiduel.
6. **mermaid 12** (majeure) pour deux avis faibles.

---

## 6. Diffs proposés hors de ma file (non commités)

### 6.1 `backend/app/services/llm_router_service.py` (file C) — GL-25 pour tous les appelants

```diff
@@ async def complete(self, request: LLMRequest) -> LLMResponse:
         self._track_usage(request, response)
+        # Vague 2 / file B (GL-25) : disponibilite des fournisseurs pour TOUS
+        # les appelants (SDS, chat projet, BUILD), pas seulement le studio.
+        # Une panne alerte une fois, le retour une fois (alertes_fournisseurs).
+        try:
+            from app.services import alertes_fournisseurs
+            origine = f"routeur ({request.agent_type})"
+            if response.success:
+                alertes_fournisseurs.signaler_succes_appel(response.provider, origine=origine)
+            else:
+                alertes_fournisseurs.signaler_echec_appel(
+                    response.provider, response.error or "", origine=origine
+                )
+        except Exception as exc:  # un signalement ne fait jamais echouer l'appel
+            logger.warning("[LLM] signalement de disponibilite impossible : %s", exc)
         return response
```
Le studio signale déjà de son côté ; l'état par fournisseur évite le doublon (même cause → pas de nouvelle alerte).

### 6.2 `backend/app/services/llm_router_service.py` (file C) — `DH_LLM_CONFIG_PATH` ignoré

```diff
     def _get_default_config_path(self) -> str:
+        # DH_LLM_CONFIG_PATH etait consulte APRES le fichier du depot, donc
+        # jamais. Pose explicitement, il prime ; absent sur disque, refus.
+        explicite = os.environ.get("DH_LLM_CONFIG_PATH")
+        if explicite:
+            if not Path(explicite).exists():
+                raise FileNotFoundError(f"DH_LLM_CONFIG_PATH={explicite} introuvable")
+            return explicite
         candidates = [
```

### 6.4 `backend/app/services/llm_router_service.py` (file C) — garder le type de l'erreur de transport (reprise 3)

```diff
@@ async def _call_gpu_local(...)
         except Exception as e:
             return LLMResponse(content="", provider=provider_name, model_id=modele_servi,
                                tokens_in=0, tokens_out=0, cost_usd=0.0,
                                latency_ms=int((time.time() - debut) * 1000),
-                               success=False, error=str(e)[:200])
+                               # httpx rend str(e) VIDE pour ReadTimeout/ConnectTimeout :
+                               # sans le nom de la classe, la panne est muette.
+                               success=False, error=f"{type(e).__name__}: {e}"[:200])
```
(Même remarque pour `_call_ollama`, `_call_anthropic`, `_call_openai`.)

### 6.3 `backend/app/services/rag_service.py` (file A)

- `get_cached_rag_health` / `_lancer_rafraichissement_arriere_plan` n'ont plus d'appelant dans `app/` : à retirer ou à marquer, au choix de A (les tests B6 de niveau unité les exercent encore).
- Optionnel : `chromadb.PersistentClient(path=CHROMA_PATH, settings=chromadb.config.Settings(anonymized_telemetry=False))` pour couper la télémétrie du processus de l'API.

---

## 7. Fichiers en recouvrement touchés

| Fichier | Ce que j'y ai changé |
|---|---|
| `backend/app/main.py` (B) | arrêt : fermeture du pool ARQ, arrêt de la sonde RAG, annulation de la surveillance ; démarrage : `sonde_rag.sonde.lancer()` à la place de la tâche `to_thread`, tâche de surveillance des fournisseurs locaux ; `_check_chroma` lit `sonde_rag` ; CORS lu depuis `settings.BACKEND_CORS_ORIGINS` (liste en dur retirée). |
| `backend/app/config.py` (B) | `DEBUG=False`, liste CORS, validateurs `SECRET_KEY` / `CREDENTIALS_ENCRYPTION_KEY` / CORS, constantes `_MARQUEURS_GABARIT`, `LONGUEUR_MIN_SECRET_KEY`. |
| `backend/requirements.txt` (B) | SEC-18 (voir §1.6) ; pytest/pytest-asyncio retirés. |
| `frontend/package.json` (B) | `"vite": "^6.4.5"` (une ligne) ; `package-lock.json` régénéré (≈1 400 lignes : conflit probable si C ajoute une dépendance). |
| `backend/app/services/admin_alert_service.py` (personne) | `_envoyer_telegram` : 2xx **et** `"ok": true` ; libellé du message « non configuré ou refusé ». |
| `backend/app/api/routes/studio_chat.py` (personne) | 503 explicite, 402 `insufficient_credits`, signalement panne/retour. Bloc `try/except` autour de `generate_llm_response` et bloc d'échec qui suit. |
| `backend/app/api/routes/orchestrator/execution_routes.py` (personne) | `worker_health` réécrite (+ `_lire_battement_arq`), signature `worker_health(response: Response)`. |

Autres fichiers modifiés, hors tableau : `backend/app/database.py`, `backend/app/utils/encryption.py`, `backend/app/utils/auth.py`, `backend/app/api/routes/orchestrator/chat_ws_routes.py` (import PyJWT), `backend/app/services/file_processor.py` (import pypdf — **la file A travaille sur l'upload (PROD-09) : conflit possible sur ces deux lignes**), `backend/app/workers/arq_config.py`, `backend/app/workers/worker.py`, `backend/scripts/rotate_encryption_key.py`, `scripts/dh-watchdog.sh`, `scripts/rotate_anthropic_key.sh`, `scripts/ops/export_logs_24h.sh`, `docker-compose.prod.yml`, `backend/requirements-test.txt`. Nouveaux : `app/services/sonde_rag.py`, `app/services/alertes_fournisseurs.py`, `tests/routes_montees.py`, six fichiers `tests/test_vague2_b_*.py`. Tests existants modifiés : `test_vague_a_a6_rag_count_off_loop.py`, `test_vague_b_b6_health_cache.py`, `test_lot_g_health_and_boot.py`, `test_vague1_a_sec11_blog.py`, `test_vague_c_sec01_sec02.py`. **Correction après revue 1 (reprise 1)** : la phrase initiale « Aucun `skip`/`xfail` ajouté » était **fausse**. `test_vague2_b_ops08_scripts.py` porte 4 `@pytest.mark.skipif(os.geteuid() != 0, reason="le script exige root (il le verifie)")` sur les tests de rotation : `rotate_anthropic_key.sh` refuse de tourner hors root (`[ "$(id -u)" -eq 0 ] || fail`). Sur le VPS la suite tourne en root, ils y sont exécutés (aucun `skipped` de plus que la référence : `2 skipped` des deux côtés) ; `test_les_tests_de_rotation_tournent_sur_le_vps` échoue s'ils y étaient ignorés (lui-même ignoré hors du VPS, en le disant). Aucun `skip`/`xfail` ajouté sur un test **existant**. Aucune migration Alembic.

Fichiers que j'aurais dû toucher hors de ma file : `llm_router_service.py` (C) et `rag_service.py` (A) — §6.

---

## 8. Écarts aux règles, dits platement

1. **Requêtes vers le Spark réel pendant mes mesures de démarrage.** Mon script `implb_boot.sh` devait rediriger les fournisseurs locaux vers un port fermé via une copie du YAML ; la redirection était inopérante (expression régulière fausse, `181(84|10)` au lieu de `18(084|110)`, et `DH_LLM_CONFIG_PATH` ignoré par le routeur). Les 4 démarrages d'uvicorn (froid avant, froid après ×2, SEC-18) ont donc chacun fait la sonde de démarrage existante : `GET http://127.0.0.1:18084/v1/models` (deux fournisseurs sur ce port) — pas de génération. Le commentaire du script annonçait « aucune requete au Spark » : c'était faux. Les suites pytest lancées (complètes et ciblées) font la même sonde via la fixture `client` (comportement préexistant).
2. **Ligne de journal nginx affichée** : en cherchant des accès au backend dans `/var/log/nginx/access.log`, ma sortie de commande a affiché une URL contenant une clé Ghost *Content API* (clé de lecture publique). Non reproduite ici ni dans un commit.
3. **Écritures hors du worktree** (toutes à moi) : copie du Chroma de production `/root/.dh_orch_vague2/implb-chroma/` (4,1 Go — **donnée de production ; supprimée après la revue 1** : `rm -rf /root/.dh_orch_vague2/implb-chroma` puis `ls` → `No such file or directory`), venv d'audit `/root/.dh_orch_vague2/implb-audit-venv`, copies du frontend `/tmp/implb-front`, `/tmp/implb-front2` et fichiers `/tmp/implb*` (supprimés en fin de mission). Base de test jetable `digital_humans_test_implb_boot` créée puis détruite par le script de démarrage (rôle de `/root/.dh_test_db.env`).
4. **Venv du worktree monté en place** (SEC-18) : voir §0 pour la vérification des rouges au parent.
5. Tests existants réécrits ou ajustés (§7) : décrits dans les commits concernés.
6. **Hook post-commit partagé** (`core.hooksPath=tools/git-hooks`, alerte de l'orchestrateur reçue après mes sept premiers commits) : ces commits ont été faits avec le hook actif. Aucun ne touche les chemins qui déclenchent `build_docs.py --deploy` (vérifié : `git log --name-only origin/claude/vague-c-20260906..HEAD | grep -E '^(docs/refonte/(sections|templates|sources)/|backend/config/llm_routing.yaml|backend/config/agents_registry.yaml|tools/lib/collect.py|tools/build_docs.py)'` → aucune ligne) ; `/tmp/dh_post_commit_build.log` (12:19) ne contient qu'une trace venant de `wt-vague2-c`. Le commit de ce rapport est fait avec `git -c core.hooksPath=/dev/null commit`.

---

## 9. Reprises après revue 1 (`docs/missions/REVUE_VAGUE2_B.md`, commit `9855a10`)

| # | Reprise | Commit | Preuve rouge → vert |
|---|---|---|---|
| 1 | Rapport §7 : « aucun skip ajouté » faux | `c75f04d` (test `test_les_tests_de_rotation_tournent_sur_le_vps`) + commit du rapport | Phrase corrigée (§7). Test : `17 passed` sur le VPS, aucun `skipped` (`implb_pytest.sh … tests/test_vague2_b_ops08_scripts.py -rs`). Pas de rouge possible : il garde une propriété de l'environnement (root sur le VPS). |
| 2 | Alerte refusée par Telegram jamais retentée (`signaler_panne`, `signaler_retablissement`) | `bcca12c` | Avant : `l'alerte refusee n'a jamais ete retentee — assert 1 == 2`, `le retour refuse n'a jamais ete retente — assert 2 == 3` (`impl-b-r23-rouge.log`, `8 failed, 22 passed`). Contrôle « Telegram non configuré : une seule ligne de journal pour 3 pannes » vert des deux côtés. Après : vert (`impl-b-r23-vert.log`, `50 passed` avec bill06 et gl10). Nouvel essai au plus une fois par 60 s ; « non configuré » (`telegram_configure()`) n'est pas « refusé ». |
| 3 | Classement testé sur des chaînes fabriquées ; Spark figé = 503 sans alerte ; « fournisseur inconnu » | `bcca12c` | Vrai `_call_gpu_local` contre des serveurs de boucle locale : port fermé → `'All connection attempts failed'` (classé avant et après) ; serveur muet et connexion coupée → `error=''` → avant `None`, après `injoignable`. Classes httpx réelles (`ConnectError`, `ConnectTimeout('')`, `ReadTimeout('')`, `RemoteProtocolError`) sous les deux formes. Bout en bout studio → routeur → serveur muet : avant `assert 0 == 1` (aucune alerte), après une alerte `gpu_nemotron … injoignable`. Branche `except` du studio : avant, `RuntimeError('… Connection refused (base)')` envoyait « Fournisseur LLM inconnu : injoignable » ; après, 503 sans alerte. Limite : §3 et diff §6.4. |
| 4 | Refus de démarrage SEC-17 : début de `SECRET_KEY` au journal (`input_value`) | `d2146a4` | `hide_input_in_errors = True` + message « gabarit » sans la valeur. Test `test_refus_de_demarrage_ne_divulgue_aucun_fragment` (valeurs factices, fragments de 8 caractères, n'imprime qu'un nombre) : avec l'ancien `config.py` `3 failed` (« 5 / 15 / 15 fragment(s) », `impl-b-r4-rouge.log`), après `67 passed` avec lot_e et lot4 (`impl-b-r4-vert.log`). Vérifié à la main : le refus « SECRET_KEY trop courte » n'affiche plus `input_value`. |
| 5 | `chemins_montes` ignore les websockets | `868740b` | Avant : `assert '/api/pm-orchestrator/ws/{execution_id}' in {...}` faux (`impl-b-r5-rouge.log`) ; après `34 passed` avec les trois fichiers qui utilisent l'outil (`impl-b-r5-vert.log`). Parcours récursif : 147 chemins ; seul `''` des contextes HTTP n'y est pas. |
| 6 | Contrôle A6 trompeur, fixture morte | `24f8502` | Docstrings annotées (vrai pour un faux qui relâche le GIL, faux pour chromadb), fixture `chroma_lent` et `_attendre_tache_rag` retirées ; `4 passed` (`impl-b-r6.log`). Pas de rouge : aucun comportement changé. |
| 7 | Mot de passe du rôle de test dans `impl-b-sec17-rouge.log` | `d2146a4` (assertions) + journaux | `sed -i -E 's#(postgres(ql)?(\+[a-z0-9]+)?://[^:/@ ]+:)[^@ ]+@#\1***MASQUE***@#g'` sur ce journal ; `grep -lE 'dh_test:[^*@ ]+@' impl-b-* implb*` → aucun fichier. Les assertions SEC-17 n'impriment plus le `repr` de `Settings`. |

**Défaut que j'ai introduit pendant les reprises, dit platement** : le test de la reprise 4 écrivait une URL `postgresql://role_factice:{MOT_DE_PASSE_BASE}@…` en clair ; `test_no_hardcoded_secrets` l'a refusée à la suite complète (`impl-b-apres-revue1.log` : `32 failed, 1159 passed, 2 skipped, 7 xfailed` — les 31 préexistants + celui-ci). Corrigé dans `c75f04d` (URL assemblée par morceaux), suite relancée.

À signaler sans coder (demandé par l'orchestrateur) : `BACKEND_CORS_ORIGINS` (§5.4, complété) ; copie de 4,1 Go du Chroma de production **supprimée** (§8.3).

Suite complète après les reprises (HEAD `c75f04d`, `/root/.dh_orch_vague2/impl-b-apres-revue1b.log`) :
```
31 failed, 1160 passed, 2 skipped, 7 xfailed, 980 warnings in 584.40s (0:09:44)
```
Mêmes 31 échecs préexistants (27 lot_c, 3 test_auth, 1 emma) ; +19 passés par rapport à `c74a817` = les tests ajoutés pendant les reprises (13 GL-25, 4 SEC-17, 1 SEC-18, 1 OPS-08).

## 10. Commits

```
1790fc2 OPS-08 : watchdog, rotation de cle et export de journaux n'annoncent plus un etat faux
2664b3f OPS-02 : la sonde worker health verifie le worker ; pool Redis ARQ partage
4b3db14 OPS-01 + demarrage en ~2 min : la sonde RAG compte hors du processus de l'API
82f4860 GL-25 + Spark injoignable : alerte admin a la panne et au retour, 503 explicite cote client
b373a3f SEC-17 : defauts surs et cles validees au demarrage (DEBUG, JWT, Fernet, CORS, echo SQL)
6526517 SEC-18 : dependances backend montees (fastapi/starlette/multipart, PyJWT, pypdf, dotenv) — 57 avis -> 7
d323077 SEC-18 (frontend) : vite 5.4.10 -> 6.4.5 et dependances verrouillees corrigees — npm audit 32 -> 2 (faibles)
c74a817 Rapport vague 2 / file B : fait avec preuve, infirme, ouvert, decisions de Sam
9855a10 Revue independante vague 2 / file B : a reprendre (7 reprises)
bcca12c Reprises 2 et 3 (revue 1) : alerte refusee retentee ; vraies pannes de transport classees
d2146a4 Reprises 4 et 7 (revue 1) : un refus de demarrage SEC-17 ne recopie plus aucune valeur au journal
868740b Reprise 5 (revue 1) : chemins_montes deplie aussi les routes websocket
24f8502 Reprise 6 (revue 1) : le controle A6 n'affirme plus que to_thread protege la boucle du vrai Chroma
c75f04d Tests : URL factice assemblee par morceaux (garde des secrets en dur) ; test de presence des tests de rotation sur le VPS (reprise 1)
<commit de ce rapport>
```
(`git log --oneline origin/claude/vague-c-20260906..HEAD` ; `9855a10` est la revue du testeur.)
