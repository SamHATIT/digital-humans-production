# Revue indépendante — Vague 2 / File B — Exploitation, sondes, dépendances

**Testeur :** testeur-B (Claude Code), worktree `/root/workspace/wt-vague2-b`, branche `claude/vague2-b`, HEAD revu `c74a817d54609ef2418bdc3f5e6ef5b585789bfd` (8 commits, 36 fichiers depuis `origin/claude/vague-c-20260906` = `388299a`).
**Date :** 24/10/2026. Je n'ai rien corrigé : je constate, je prouve, je liste les reprises.
Conventions : « vérifié » = exécuté par moi, sortie constatée ; « lu » = lu, non exécuté. Tous mes journaux sont sous `/root/.dh_orch_vague2/testeur-B-*`.

Venvs utilisés :
- **venv HEAD** = `/root/workspace/wt-vague2-b/backend/venv` (fastapi 0.162.0, starlette 1.9.0, PyJWT 2.15.1, pypdf 6.21.2, pydantic 2.14.1, httpx 0.28.1) ;
- **venv parent** = `/root/.dh_orch_vague2/venv-parent-388299a/venv` (`PIP_EXIT=0` constaté ; fastapi 0.104.1, starlette 0.27.0, pydantic 2.5.0, python-jose présent, **pypdf absent**).

---

## Verdict : **À REPRENDRE**

Le travail est solide sur l'essentiel : suite sans régression (mêmes 31 échecs que la référence, +89 passés), chaque correctif a au moins un test rouge au parent **pour la raison du constat**, les chiffres du rapport que j'ai remesurés sont exacts (57 → 7, 32 → 2, 22 fichiers, rouges avant/après), la cause du démarrage lent (`count()` de chromadb qui garde le GIL) est **confirmée** sur un Chroma fabriqué. Mais :
- une affirmation du rapport est fausse (« aucun `skip` ajouté ») ;
- le module d'alerte GL-25 reproduit le défaut qu'OPS-08 corrige dans le watchdog (état « alerté » enregistré même quand Telegram refuse l'envoi : aucune nouvelle tentative) ;
- le classement des pannes est testé sur des chaînes fabriquées qui ne sont pas celles que produit le code réel ; un Spark figé (ReadTimeout) n'alerte pas par le chemin d'appel ;
- un refus de démarrage SEC-17 écrit au journal les premiers caractères de `SECRET_KEY` (sortie pydantic).
Reprises détaillées en §6. Aucune n'invalide un correctif ; 1 à 4 sont à traiter avant PR « conforme ».

---

## 1. Suite backend mesurée par moi (venv HEAD)

Commande (depuis `backend/`) :
```
nohup bash -c 'set -a; . /root/.dh_test_db.env; set +a; export DH_ENV_FILE=$PWD/.env.test DH_TEST_RUN_ID=testeurB_head_$(date +%s); ./venv/bin/python -m pytest tests/ -q -p no:cacheprovider -rfE; echo "PYTEST_EXIT=$?"' > /root/.dh_orch_vague2/testeur-B-suite-head.log 2>&1 &
```
Sortie brute (`testeur-B-suite-head.log`) :
```
31 failed, 1141 passed, 2 skipped, 7 xfailed, 978 warnings in 792.99s (0:13:12)
PYTEST_EXIT=1
```
Comparaison des échecs avec la référence de l'orchestrateur (`reference_tests.log`, `31 failed, 1052 passed, 2 skipped, 7 xfailed`) :
```
$ diff testeur-B-reference-failed.txt testeur-B-suite-head-failed.txt && echo IDENTIQUES
IDENTIQUES
      3 FAILED tests/test_auth.py
      1 FAILED tests/test_emma_phase3.py
     27 FAILED tests/test_lot_c_injection_commandes.py
```
**Aucun nouvel échec.** +89 passés = exactement les tests ajoutés :
```
$ pytest tests/test_vague2_b_*.py --collect-only -q
89 tests collected in 0.23s
```
Requêtes vers le tunnel Spark pendant la suite : `grep -c 18084` → **59** dans mon journal HEAD, **59** dans la référence. Ce sont les `GET http://127.0.0.1:18084/v1/models` de la sonde de démarrage préexistante (fixture `client`) ; aucune génération. Pas d'augmentation due à B.

## 2. Tests ajoutés : assertion lue, rouge au parent

Méthode : pour un commit `X`, `git checkout X^ -- <fichiers de code de X>`, fichiers **nouveaux** de `X` retirés, tests de HEAD conservés, puis `git checkout HEAD -- …` (script `testeur-B-rouge.sh`, retour à HEAD dans un `trap`, `git status --short` vide et `git rev-parse HEAD` = `c74a817…` constatés en fin de chaque journal). Pour les commits antérieurs à SEC-18 avec le venv parent, `backend/app/services/file_processor.py` est remis à `388299a` pendant la mesure (le venv parent n'a pas `pypdf`) ; ce fichier n'est touché par aucun de ces commits.

| Groupe (commit) | Assertion lue : prouve ce qu'annonce la docstring ? | Rouge au parent | Commande / journal / venv |
|---|---|---|---|
| OPS-08 (`1790fc2`) 16 tests | Oui. Bouchons `curl`/`systemctl`/`journalctl`/`sleep` en tête de PATH ; assertions sur URL, `chat_id=4242`, texte, fichier d'état, code de sortie. 5 contrôles (envoi nominal, pas de doublon, rétabli unique, rollback backend mort, export nominal). | **Oui** : `11 failed, 5 passed` ; ex. `etat enregistre malgre l'echec d'envoi (http500) : 'backend /health = 503\n'`, `ROLLBACK … backend did not become healthy`, `assert 0 != 0` (sans identifiants) | `testeur-B-rouge.sh ops08 1790fc2 <venv parent> 'scripts/dh-watchdog.sh scripts/rotate_anthropic_key.sh scripts/ops/export_logs_24h.sh'` → `testeur-B-rouge-ops08.log` |
| OPS-02 (`2664b3f`) 8 tests | Oui. Redis de test (garde `database not in (0,1)`), clés ARQ réelles (`ZCARD <file>`, `<file>:health-check`). | **Oui** : `8 failed` ; `{'queued_jobs': 0, …} assert 0 == 2`, `assert 200 == 503`, `assert None == datetime.timezone.utc`, 2 × `close_redis_pool` absent | `… ops02 2664b3f <venv parent> 'execution_routes.py main.py arq_config.py worker.py'` → `testeur-B-rouge-ops02.log` |
| OPS-01 (`4b3db14`) 13 tests | Oui pour les 4 tests de constat (comptage dans le processus avec un faux qui **tient le GIL**, comptage synchrone dans `/health`, collection vide, vert périmé) ; le contrôle de sens (`re` catastrophique bloque la boucle via `to_thread`) est vert des deux côtés, voulu. Les 7 autres testent le nouveau mécanisme (délai, enfant tué, retour…). `test_l_enfant_n_envoie_pas_de_telemetrie` ne lit que le dictionnaire d'environnement ; j'ai vérifié à part que chromadb 1.3.4 honore la variable (`ANONYMIZED_TELEMETRY=False → False`, sans → `True`). | **Oui pour 4 / raison du constat** : `assert 5 == 0` (5 comptages Chroma dans le processus), `assert 1 == 0` (comptage synchrone), `300 chunks assert not True`, `500 chunks assert not True`. 7 rouges par module absent (`'NoneType' object has no attribute 'SondeRAG'`) : ne prouvent pas le correctif, ce sont des tests unitaires du nouveau module. | `… ops01 4b3db14 <venv parent> 'backend/app/main.py'` + `sonde_rag.py` retiré → `testeur-B-rouge-ops01.log` (`16 failed, 6 passed` avec A6/B6) |
| GL-25 (`82f4860`) 17 tests | Oui pour le 503/402, l'alerte unique, le rétabli unique, l'absence de repli, `ok:false`. **Non pour `test_classement_des_erreurs`** : ses entrées (`"ConnectError: [Errno 111] …"`, `"ConnectTimeout: timed out"`) ne sont pas ce que produit `_call_local` (`str(e)[:200]`, sans nom de classe) — voir reprise 3. | **Oui pour 7** : `assert 502 == 503` ×4 avec le message brut du fournisseur au client (`"L'agent n'a pas pu repondre : Error code: 400 - … credit balance is too low …"`), `assert 502 == 402`, `assert True is False` (`ok:false`), surveillance absente. 10 rouges par module absent (classement, sonde). | `… gl25 82f4860 <venv parent> 'studio_chat.py main.py admin_alert_service.py'` + `alertes_fournisseurs.py` retiré → `testeur-B-rouge-gl25.log` |
| SEC-17 (`b373a3f`) 23 tests | Oui. Configurations factices `Settings(..., _env_file=None)`. Le test CORS `"*"` discrimine bien (le validateur `assemble_cors_origins` découpe la chaîne : `DID NOT RAISE` au parent). | **Oui** : `21 failed, 2 passed` (les 2 verts = contrôles positifs) ; `DID NOT RAISE` ×15, `engine.echo True`, `'*' not in ['*']`, `--reload` présent | `… sec17 b373a3f <venv parent> 'config.py database.py main.py utils/encryption.py scripts/rotate_encryption_key.py docker-compose.prod.yml'` → `testeur-B-rouge-sec17.log` |
| SEC-18 (`6526517`) 12 tests | Oui (lecture de `requirements.txt` et des imports ; 4 tests de compatibilité des jetons python-jose → PyJWT verts des deux côtés, voulu ; contrôle de `chemins_montes`). | **Oui** : `7 failed` (`('python-multipart', ['==0.0.6'])`, `starlette absent`, `('fastapi', ['==0.104.1'])`, `python-jose`/`pypdf2` présents, 3 fichiers importent encore `jose`/`PyPDF2`) | `… sec18 6526517 <venv parent> 'chat_ws_routes.py file_processor.py auth.py requirements.txt requirements-test.txt'` → `testeur-B-rouge-sec18.log` (`7 failed, 26 passed` avec les 3 fichiers de routes) |

Contrôle négatif ajouté par moi pour « aucun repli silencieux vers un modèle payant » : mutant qui renvoie `gpu_nemotron → anthropic/claude-sonnet` dans `_fallback_for` (fichier de test temporaire, supprimé ensuite) :
```
E       AssertionError: repli vers un autre fournisseur : ['gpu_nemotron/nemotron', 'anthropic/claude-sonnet']
1 failed, 17 passed in 7.14s
```
(`testeur-B-mutant-repli.log`) — le test discrimine.

## 3. Tests existants réécrits

| Fichier / test | Verdict | Preuve |
|---|---|---|
| `test_lot_g_health_and_boot.py::test_download_route_is_gone`, `test_vague1_a_sec11_blog.py`, `test_vague_c_sec01_sec02.py` (via `tests/routes_montees.py`) | **Justifié.** Avec FastAPI 0.162, l'ancienne lecture `{r.path for r in app.routes}` rend les tests « routeur démonté » vrais sans rien vérifier. | Anciennes versions (`git show 388299a:…`) lancées avec le venv HEAD : `2 failed, 19 passed` — les deux contrôles négatifs tombent (`any(...) False`), les assertions « démonté » passent à vide. Réserve : reprise 5 (`chemins_montes` ignore les routes websocket). |
| A6 `test_health_repond_pendant_le_comptage_rag` | **Justifié** : même critère (startup < 1 s, `/health` < 1 s, comptage encore en cours constaté) sur le mécanisme réel. Seul, il ne discrimine plus le GIL (l'enfant dort dans un autre processus) ; c'est `test_le_demarrage_ne_compte_pas_chroma_dans_le_processus` (faux qui tient le GIL) qui porte la preuve. | Rouge au parent par `ImportError … sonde_rag` (raison sans rapport). |
| A6 `test_journal_rag_health_emis_a_la_fin_du_comptage_de_fond` | **Justifié.** | idem |
| A6 `test_exception_dans_le_comptage_journalisee_probe_crashed` | **Justifié** : attend `[RAG HEALTH] FAILED` portant la sortie d'erreur de l'enfant (`chroma injoignable (faux)`). | idem |
| B6 `test_deux_appels_http_health_consecutifs_ne_declenchent_pas_de_second_comptage` | **Justifié** (compte les lancements de sonde au lieu des comptages en processus). | idem |
| B6 `test_health_ne_bloque_pas_sur_le_rafraichissement_de_fond` | **Légèrement affaibli** : l'assertion finale « le rafraîchissement de fond se reflète dans l'état » (`total_chunks == 495`) a disparu. Couvert ailleurs par `test_echec_puis_retour_redevient_up` (OPS-01). Acceptable. | lu |
| A6 `test_controle_negatif_le_comptage_synchrone_bloque_bien_la_boucle` (non réécrit) | **Devenu trompeur** : il affirme toujours, avec un faux `time.sleep`, que `to_thread` ne bloque pas la boucle — prémisse que B a montrée fausse pour chromadb. Fixture `chroma_lent` désormais sans utilisateur. Reprise 6 (mineure). | lu |

## 4. Points d'attention de la mission

### (a) Alertes GL-25 / Spark injoignable
- **Aucun test ne peut envoyer de vraie alerte** (lu + vérifié) : `TELEGRAM_BOT_TOKEN` de `.env.test` est préfixé `dh-test-fake-` (refusé par `_envoyer_telegram`), la garde réseau de `tests/hermetic.py` refuse toute connexion sortante non locale, et les tests GL-25 remplacent `urllib.request.urlopen`. Mon mutant et mes scripts bouchonnent aussi `urlopen` et `_persister`.
- **Première panne / retour / sans doublon** : vérifié par la suite (tests verts à HEAD, rouges au parent). `admin_alert_service.alerter_admin` est appelé sans `cle_deduplication` : pas d'interférence de la fenêtre de 900 s (lu).
- **503 explicite au lieu du 502** : vérifié (rouge au parent : `assert 502 == 503` avec le message Anthropic dans la réponse).
- **« Repli silencieux vers un modèle payant : infirmé »** : confirmé. Profil de production lu dans le journal, filtré : `journalctl -u digital-humans-backend -o cat | grep -oE "profile=[A-Za-z_-]+" | sort | uniq -c` → `2 profile=cloud` ; YAML `cloud: fallback_chain: {}` ; mutant ci-dessus détecté.
- **Défaut trouvé** (reprise 2) : Telegram refuse → la panne est quand même marquée alertée, aucun nouvel envoi. Script `testeur-B-alerte-refusee.py` (urlopen et `_persister` bouchonnés) :
  ```
  essai 1: signaler_panne -> True ; tentatives d'envoi Telegram cumulees = 1
  essai 2: signaler_panne -> False ; tentatives d'envoi Telegram cumulees = 1
  essai 3: signaler_panne -> False ; tentatives d'envoi Telegram cumulees = 1
  ```
- **Défaut trouvé** (reprise 3) : erreurs httpx **réelles** (boucle locale uniquement, `testeur-B-classement.py`) passées au classement sous la forme de `_call_local` :
  ```
  port ferme (tunnel tombe): type=ConnectError str(e)='All connection attempts failed' -> classer_erreur='injoignable'
  serveur muet (Spark fige): type=ReadTimeout str(e)='' -> classer_erreur=None
  connexion coupee: type=RemoteProtocolError str(e)='Server disconnected without sending a response.' -> classer_erreur='injoignable'
  ```
  Un Spark figé derrière un tunnel ouvert donne `error=''` → `motif = "reponse vide"` → 503 **sans alerte** par le chemin d'appel (délai d'appel local : 600 s par défaut). Seule la sonde périodique (60 s, délai 5 s) le verrait. Par ailleurs, dans `studio_chat.py`, la branche `except Exception` signale avec `provider=None` → fournisseur `inconnu` : une exception dont le texte contient « connection refused » (par ex. base de données injoignable) serait annoncée « Fournisseur LLM inconnu : injoignable », sans « rétabli » possible (le succès signale le vrai nom de fournisseur) — lu, non exécuté.

### (b) Démarrage ~2 min
- Raisonnement **confirmé par mesure**, sur un Chroma **fabriqué par moi** (3 collections × 100 000 enregistrements, embeddings de dimension 8, 677 Mo, `/root/.dh_orch_vague2/testeur-B-chroma`, supprimé ensuite ; copie de production **non ouverte**), chromadb 1.3.4 (venv HEAD). `count()` lancé dans un fil ; le fil principal fait une boucle Python (`testeur-B-chroma-gil2.log`) :
  ```
  froid coll_0: count=100000 en 908 ms ; fil principal : 8592 tours, temps Python effectif 5 ms, plus long arret 903 ms
  froid coll_1: count=100000 en 641 ms ; fil principal : 8306 tours, temps Python effectif 5 ms, plus long arret 636 ms
  froid coll_2: count=100000 en 895 ms ; fil principal : 0 tours, temps Python effectif 0 ms, plus long arret 0 ms
  chaud coll_0: count=100000 en 22 ms ; fil principal : 9538 tours, temps Python effectif 6 ms, plus long arret 17 ms
  ```
  Le fil principal est arrêté pendant toute la durée de chaque `count()` (903 ms pour 908 ms ; 0 tour pendant 895 ms) : **`count()` garde le GIL**, `asyncio.to_thread` ne libère pas la boucle. L'ancien faux d'A6 (`time.sleep`, lu dans `388299a`, ligne 87) relâche le GIL : il ne pouvait pas voir le défaut. Le test de remplacement (faux à expression régulière catastrophique) est rouge au parent (`assert 5 == 0`) et son contrôle de sens est vert.
- **Non refait** : la mesure de démarrage uvicorn (ni sur la copie de production, ni sur mon Chroma) ; je n'ai lancé aucun uvicorn. L'écart 89–119 s en production contre 11–13 s sur la copie reste ouvert, comme le dit le rapport.

### (c) SEC-17
Import de `app.main` (ce que fait uvicorn avant le démarrage ; aucun événement de démarrage, donc aucune sonde) avec des configurations **factices** dans l'environnement (`testeur-B-sec17-demarrage.sh` / `.log`) :
```
--- controle valide : code=0          … DEMARRAGE_OK
--- fernet mal formee : code=1        Value error, CREDENTIALS_ENCRYPTION_KEY n'est pas une cle Fernet valide (…) les re-chiffrer d'abord : python scripts/rotate_encryption_key.py --old-key <ancienne> --new-key <nouvelle>
--- jwt gabarit .env.example : code=1 Value error, SECRET_KEY ressemble a une valeur de gabarit (« your-secret-… ») : refusee.
--- jwt 16 caracteres : code=1        Value error, SECRET_KEY trop courte (16 caracteres, 32 minimum hors DEBUG).
--- cors etoile hors debug : code=1   Value error, BACKEND_CORS_ORIGINS contient "*" hors DEBUG : refuse.
--- fernet absente hors debug : code=1 Value error, CREDENTIALS_ENCRYPTION_KEY is required in production mode (DEBUG=False).
```
Refus explicites, confirmés. **Mais** chaque erreur porte aussi `input_value={'SECRET_KEY': 'CHBxVHtLW...` (ici ma clé factice) : en production, un refus de démarrage écrirait les ~9 premiers caractères de la vraie `SECRET_KEY` dans le journal systemd (reprise 4).
**Risque de déploiement** (je n'ai pas lu `backend/.env`) : le backend **refusera de démarrer** si la `.env` de production a une `CREDENTIALS_ENCRYPTION_KEY` qui n'est pas une clé Fernet, une `SECRET_KEY` < 32 caractères ou de gabarit, ou un `BACKEND_CORS_ORIGINS` contenant `"*"` — ce dernier réglage n'était **lu par personne** avant B, une valeur ancienne et oubliée y devient bloquante. Le rapport le classe en « décision de Sam » (§5.4) : correct.

### (d) SEC-18 — audits et frontend
pip-audit 2.10.1 (`implb-audit-venv`, lecture seule) sur mes propres gels (`testeur-B-freeze-parent.txt`, `testeur-B-freeze-head.txt`, identiques à ceux de l'implémenteur) — `testeur-B-pip-audit.log` :
```
== parent (venv-parent-388299a)
Found 57 known vulnerabilities in 12 packages
== head (venv du worktree)
Found 7 known vulnerabilities in 2 packages
chromadb 1.3.4   PYSEC-2026-311 (×2) / PYSEC-2026-3814 / PYSEC-2026-3815 / PYSEC-2026-3813  (pas de version corrigee)
pytest   7.4.3   PYSEC-2026-1845 (×2)  9.0.3
No broken requirements found.   (pip check, venv HEAD)
```
**57 → 7 confirmé.** npm audit `--package-lock-only` sur les verrous de `388299a` et de HEAD (`testeur-B-npm-audit.log`) :
```
== parent  {'info': 0, 'low': 2, 'moderate': 12, 'high': 18, 'critical': 0, 'total': 32}
== head    {'info': 0, 'low': 2, 'moderate': 0, 'high': 0, 'critical': 0, 'total': 2}   [('katex', 'low'), ('mermaid', 'low')]
"node_modules/vite": { "version": "6.4.5", …
```
**32 → 2 confirmé.** Frontend après Vite 6, dans `frontend/` du worktree (`npm ci` : `node_modules` était absent) — `testeur-B-front.log` :
```
added 387 packages in 6s            NPM_CI_EXIT=0
vite/6.4.5 linux-x64 node-v22.21.0
node --experimental-strip-types --test tests/*.test.ts  →  # tests 61 / # pass 61 / # fail 0   FRONT_TESTS_EXIT=0
npm run build  →  ✓ built in 20.46s   BUILD_EXIT=0
```
`node_modules/` et `dist/` laissés dans le worktree (ignorés par git : `!! frontend/dist/`, `!! frontend/node_modules/`).
Observation : `requirements.txt` passe plusieurs paquets en plages (`starlette>=1.3.1,<2`, `pydantic>=2.9,<3`, `pydantic-settings>=2.6,<3`, `pypdf>=6,<7`, `cryptography` sans borne) ; une installation neuve peut résoudre autre chose que le venv mesuré. Non classé en reprise (choix défendable), à signaler au déploiement.
Compatibilité : la route websocket `/api/pm-orchestrator/ws/{execution_id}` répond toujours avec FastAPI 0.162 (`testeur-B-ws.py`) : `ferme code 1008 'Missing authentication token'` contre `ferme code 1000 ''` pour un chemin inexistant.

### (e) Tests réécrits : voir §3.

### (f) OPS-08 : rien de réel touché
Lu : PATH bouchonné, `DH_WATCHDOG_ENV`, `STATE`, `DH_ENV_FILE`, `DH_SERVICE_NAME=dh-test-faux-service`, `DH_LOG_EXPORT_DIR` tous sous `tmp_path` ; les scripts n'appellent `curl`/`systemctl`/`journalctl` que par le PATH (`grep` : aucun chemin absolu). Vérifié : état de `/usr/local/bin/dh-watchdog.sh`, `/var/run/dh-watchdog.state`, `/var/log/digital-humans/*-24h.log` (date, taille, empreinte) avant/après un passage des tests OPS-08 → `AUCUN_CHANGEMENT`. Le watchdog installé est identique à la copie de `388299a` (`DIFF_INSTALLE_VS_PARENT=0`, `DIFF_INSTALLE_VS_HEAD=1`) : il faudra le réinstaller après fusion, **après** le backend (rapport §3, exact).
Les 4 tests de rotation portent `@pytest.mark.skipif(os.geteuid() != 0, …)` (justifié : le script exige root ; ils tournent ici, 2 `skipped` comme la référence) — mais voir reprise 1.

### (g) Fichiers `*.pre-*` / `*.bak*`
```
$ find /root/workspace/digital-humans-production/backend/app \( -name '*.pre-*' -o -name '*.bak*' \) -printf '%TY-%Tm-%Td %s %P\n' | sort | wc -l
22
$ diff <liste find> <tableau du rapport §1.7 : date, taille, chemin>  → TABLEAU_IDENTIQUE (22 lignes, date+taille+chemin)
$ git cat-file -e 388299a:backend/app/<f>  (dans mon worktree, pour les 22) → suivis au commit 388299a : 0
```
Aucune commande git dans le répertoire de production.

## 5. Affirmations du rapport : contrôle

| Affirmation | Statut |
|---|---|
| Suite après : `31 failed, 1141 passed, 2 skipped, 7 xfailed`, mêmes 31 échecs | **Vérifié** (§1) |
| Rouges avant : OPS-08 11/5, OPS-02 7+1, OPS-01 11/2, GL-25 17, SEC-17 21/2, SEC-18 7 | **Vérifié** (§2) |
| pip-audit 57 → 7 ; npm audit 32 → 2 | **Vérifié** (§4d) |
| `count()` de chromadb garde le GIL ; A6 vert pour une mauvaise raison | **Vérifié** sur Chroma fabriqué (§4b) |
| Repli silencieux vers un modèle payant : infirmé | **Vérifié** (profil `cloud`, mutant détecté) |
| 22 fichiers `*.pre-*`/`*.bak*`, aucun suivi | **Vérifié** (§4g) |
| Watchdog installé = copie d'avant | **Vérifié** |
| Aucun commit ne touche les chemins du hook de déploiement | **Vérifié** : `git log --name-only … | grep -E '^(docs/refonte/(sections|templates|sources)/|backend/config/llm_routing.yaml|…)' | wc -l` → `0` |
| « Aucun `skip`/`xfail` ajouté » (§7) | **Faux** : 4 `skipif` (reprise 1) |
| Tests frontend non lancés | Exact ; lancés par moi : 61/61 |
| Mesures uvicorn de démarrage (10,0 s → 0,31 s) | **Non refait** par moi (lu dans les journaux de l'implémenteur) |

Fichiers modifiés hors zone de B : `execution_routes.py`, `studio_chat.py`, `admin_alert_service.py` (zones « personne »), `database.py`, `utils/encryption.py`, `utils/auth.py`, `chat_ws_routes.py`, `file_processor.py`, `docker-compose.prod.yml` — chacun justifié par un constat (OPS-02, GL-25, SEC-17, SEC-18). `llm_router_service.py` (C) et `rag_service.py` (A) **non modifiés**, diffs proposés au rapport §6 : règle respectée.

**Recouvrements avec les autres files** (calculés sur les branches locales, `comm -12` des `git diff --name-only` depuis `388299a`) :
```
== claude/vague2-a c9373fc   (aucun fichier commun)
== claude/vague2-c efb48e4
backend/app/api/routes/orchestrator/execution_routes.py
backend/app/api/routes/studio_chat.py
```
- `execution_routes.py` : B en `@@ -750` (`worker_health`), C en `@@ -55`, `-72`, `-98` → zones disjointes (lu).
- `studio_chat.py` : B en `@@ -138,6`, `-152,11`, `-164,11` ; C en `@@ -131,8` (consigne de langue, `_rendre_historique`) et `-176,6` (`avis_repli=` dans `StudioChatResponse`) → hunks **adjacents** : conflit de fusion probable, à résoudre à la main (lu, non exécuté : je n'ai pas lancé de `merge-tree` pour ne rien écrire dans le dépôt partagé). Après fusion, re-vérifier le 503/402 de B avec l'`avis_repli` de C.
- `main.py`, `config.py`, `requirements.txt`, `frontend/package.json`, `tests/conftest.py` : touchés par B seul à l'état actuel des branches.

## 6. Reprises (précises, actionnables)

1. **Rapport §7, affirmation fausse — « Aucun `skip`/`xfail` ajouté. »** `backend/tests/test_vague2_b_ops08_scripts.py` ajoute 4 `@pytest.mark.skipif(os.geteuid() != 0, reason="le script exige root (il le verifie)")` (les 4 tests de rotation). Preuve : `git diff origin/claude/vague-c-20260906...HEAD -- backend/tests | grep -nE "^\+.*(skip|xfail)"` → 4 lignes. Attendu : corriger la phrase du rapport (dire qu'ils existent, pourquoi, et qu'ils tournent en root sur le VPS) ; idéalement un test non conditionnel qui échoue s'ils sont ignorés sur le VPS.
2. **`backend/app/services/alertes_fournisseurs.py` — état « panne alertée » enregistré même si l'envoi échoue.** `signaler_panne` écrit `_pannes[fournisseur]` avant `_alerter` et ignore le retour d'`alerter_admin` : Telegram qui refuse (`ok:false`, HTTP 5xx, réseau) → plus aucune tentative tant que la panne dure. C'est le défaut corrigé par OPS-08 dans le watchdog. Preuve : `testeur-B-alerte-refusee.log` (1 seule tentative pour 3 pannes, la première refusée). Attendu : retenter l'envoi à l'occurrence suivante tant qu'aucun envoi n'a été accepté (sans spammer quand Telegram n'est pas configuré : distinguer « non configuré » de « refusé »), même chose pour `signaler_retablissement` ; test rouge d'abord.
3. **Classement des pannes (`alertes_fournisseurs.classer_erreur`, `studio_chat.py`) testé sur des chaînes fabriquées.** `test_classement_des_erreurs` utilise `"ConnectError: [Errno 111] …"` et `"ConnectTimeout: timed out"`, alors que `_call_local` produit `str(e)[:200]` sans nom de classe. Preuve : `testeur-B-classement.py` — `ReadTimeout str(e)='' -> classer_erreur=None` : un Spark figé derrière un tunnel ouvert donne un 503 **sans alerte** par le chemin d'appel. Et la branche `except Exception` de `studio_chat.py` signale sous le fournisseur `inconnu` (pas de « rétabli » possible ; risque d'annoncer une panne LLM pour une autre cause contenant « connection refused »). Attendu : tests alimentés par des exceptions httpx/anthropic réelles (comme mon script, boucle locale) ; une erreur vide ou un délai dépassé d'un fournisseur local classé « injoignable » ; pas d'alerte « fournisseur inconnu » (ou un fournisseur connu). À défaut, écrire ces limites dans le rapport.
4. **`backend/app/config.py` — un refus de démarrage SEC-17 écrit le début de `SECRET_KEY` au journal.** Les `ValueError` des validateurs `mode="after"` sont rendues par pydantic avec `input_value={'SECRET_KEY': '<9 premiers caractères>...', …}`. Preuve : `testeur-B-sec17-demarrage.log` (clé factice `CHBxVHtLW...` affichée dans les 4 refus). Préexistant pour le refus « CREDENTIALS_ENCRYPTION_KEY is required », mais SEC-17 multiplie les refus, précisément au déploiement. Attendu : `hide_input_in_errors=True` dans la configuration du modèle `Settings`, avec un test qui vérifie qu'aucun fragment de la clé n'apparaît dans le message d'erreur.
5. **`backend/tests/routes_montees.py` — `chemins_montes` ignore les routes websocket.** Comparaison même code, `fastapi 0.104` (liste plate, venv parent) contre `chemins_montes` (fastapi 0.162) : `seulement plat: ['/api/pm-orchestrator/ws/{execution_id}']`, `seulement deplie: ['']` (147 chemins de chaque côté, ensembles différents ; `testeur-B-routes-*.json`). Mineur (les tests « démonté » ne visent pas de websocket). Attendu : déplier aussi les websockets (ou documenter la limite dans la docstring) et l'ajouter au contrôle de `test_chemins_montes_voit_un_routeur_inclus`.
6. **`backend/tests/test_vague_a_a6_rag_count_off_loop.py` — contrôle devenu trompeur (mineur).** `test_controle_negatif_le_comptage_synchrone_bloque_bien_la_boucle` affirme encore, avec un faux `time.sleep`, que `to_thread` ne bloque pas la boucle ; fixture `chroma_lent` sans utilisateur. Attendu : l'annoter (vrai pour `time.sleep`, faux pour chromadb, renvoi vers OPS-01) ou le retirer avec la fixture.
7. **Hygiène des journaux (mineur).** Quand `test_debug_est_faux_par_defaut` échoue, `assert cfg.DEBUG is False` imprime le `repr` de `Settings`, dont `DATABASE_URL` avec le mot de passe du rôle de test. Le journal de l'implémenteur `impl-b-sec17-rouge.log` le contient (constaté par `grep -lE "postgresql://[^:]+:[0-9a-f]{8,}@"`) ; j'ai masqué le même motif dans mes propres journaux. Pas un secret de production. Attendu : message d'assertion sans le `repr` de `Settings` ; purger ce journal.

## 7. Ce que je n'ai pas fait
- Pas de mesure de démarrage uvicorn (ni copie de production, ni Chroma fabriqué) ; pas d'ouverture de `/root/.dh_orch_vague2/implb-chroma/`.
- Pas de `git merge-tree` pour mesurer les conflits avec C (aurait écrit des objets dans le dépôt partagé) : recouvrements « lus ».
- Pas d'installation neuve depuis `requirements.txt` (j'ai audité les gels des venvs).
- Pas de lecture de `backend/.env` de production.

## 8. État du worktree à la fin
Constaté après chaque retour au parent et avant le commit de cette revue :
```
$ git status --short        (vide)
$ git rev-parse HEAD
c74a817d54609ef2418bdc3f5e6ef5b585789bfd
```
