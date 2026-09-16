# Rapport — Vague 0 / AS-02 — Environnement de correction sûr (OPS-05)

**Date :** 16/09/2026. **Branche :** `claude/vague0-as02-env-test`, créée depuis
`claude/vague-c-20260906` à `abcc04f` (tête du VPS ce matin, 18 commits non
poussés inclus). **Environnement :** bac à sable Claude Code (Python 3.11,
PostgreSQL 16 et Redis locaux), pas le VPS. Rien n'a été fusionné : PR ouverte
vers `claude/vague-c-20260906`.

Mission : `docs/missions/VAGUE0_AS02_ENVIRONNEMENT_DE_CORRECTION_SUR.md`.
Critère de sortie d'Astra : *« Les suites et agents de développement ne
peuvent joindre aucune base, file, org ou clé de production. »*

Chaque « fait » ci-dessous est une commande jouée dont la sortie est collée.
Le reste est dit « lu, non exécuté ».

---

## 0. Mesure avant / après (règle 4)

Suite complète, `cd backend && ./venv/bin/python -m pytest tests/ -q`.

| État | Commande | Résultat |
|---|---|---|
| `abcc04f`, commande de la mission (`TEST_DATABASE_URL` seule) | run A | **rien n'est collecté** : `RuntimeError: DATABASE_URL manquant — aucun secret par defaut (purge du 16/09/2026, GL-11)` levée par `app/api/routes/blog.py:18` à l'import de conftest, `exit 4`, 3,6 s |
| `abcc04f`, `DATABASE_URL` aligné sur la base de test (comme les vagues A/B) | run B, **référence** | `31 failed, 671 passed, 2 skipped, 7 xfailed in 154s` |
| `4ec6098` (bootstrap, non encore suivi par git), `TEST_DATABASE_URL` seule | après | `31 failed, 695 passed, 2 skipped, 7 xfailed in 172s` |
| **tête de branche `5d35156`**, `TEST_DATABASE_URL` seule | **final** | `32 failed, 694 passed, 2 skipped, 7 xfailed in 170s` — le 32e est le test instable ci-dessous, seul écart avec la référence |

Les 31 rouges de référence sont **les mêmes** avant et après (`comm` sur les
listes `FAILED` : aucun nouveau hors le test instable, aucun disparu), et
antérieurs à la mission :

| Fichier | Rouges | Cause lue (non corrigée, OPS-06) |
|---|---|---|
| `tests/test_lot_c_injection_commandes.py` | 27 | `404` : le routeur `agent_tester` est commenté dans `app/main.py:147` (`# app.include_router(agent_tester.router, ...)`), les tests attendent encore ses routes |
| `tests/test_auth.py` | 3 | `assert 401 == 200`, `KeyError: 'access_token'`, `assert 401 == 403` — cités par OPS-06 (inscription sans consentement) |
| `tests/test_emma_phase3.py` | 1 | `FileNotFoundError: /root/workspace/digital-humans-production/backend/app/services/pm_orchestrator_service_v2.py` — chemin VPS en dur |

Les 24 nouveaux verts sont les tests de cette mission. Le chiffre de la
mission (« 63 fichiers `test_*.py` ») se mesure à 62 dans `backend/tests/`,
plus `tests/test_full_flow.py` à la racine du dépôt, hors collecte.

Un test est **instable indépendamment de cette mission** :
`test_lot_g_db_sessions.py::test_open_websockets_do_not_pin_connections`
(`assert 2 == 0` connexions immobilisées). Mesuré 3 fois sur la tête de
branche : 2 échecs / 3 ; 3 fois sur `abcc04f` dans un `git worktree`, sans le
bootstrap : 1 échec / 3. Il est passé dans la mesure de référence et dans la
mesure « après », a échoué dans la mesure finale. Non corrigé, signalé.

---

## 1. Fait, avec preuve

### 1.1 Test rouge d'abord (commit `7f308b9`)

`backend/tests/test_vague0_as02_environnement_hermetique.py`, 23 tests
portant les cinq exigences, joué sur `abcc04f` avec deux bases de test
**différentes** pour `TEST_DATABASE_URL` et `DATABASE_URL` (le scénario
OPS-05, joué entre deux bases jetables) :

```
$ TEST_DATABASE_URL=.../digital_humans_test_red DATABASE_URL=.../digital_humans_test_red_autre \
  pytest tests/test_vague0_as02_environnement_hermetique.py -q
9 failed, 2 passed, 24 warnings, 12 errors in 4.54s
```

Les deux verts d'origine : `test_la_boucle_locale_reste_joignable` et
`test_controle_negatif_base_de_prod_sans_TEST_DATABASE_URL` — ce dernier
parce que la garde de la vague 2 refusait déjà `digital_humans_db` **quand**
elle voyait l'URL ; le défaut était qu'elle ne la voyait pas toujours.

### 1.2 Exigence 1 — une seule source pour la base, avant tout import

Commits `9614c50` (DH_ENV_FILE), `4ec6098` (bootstrap). `tests/hermetic.py`
est appelé en tête de `conftest.py`, avant `from app.…` (vérifié par
`test_conftest_appelle_le_bootstrap_avant_tout_import_applicatif`, qui compare
les positions dans la source). Il exige `TEST_DATABASE_URL`, en dérive une
base par exécution, et **remplace** `DATABASE_URL` et `TEST_DATABASE_URL`
dans l'environnement du processus. `pytest_configure` compare ensuite
`settings.DATABASE_URL`, `app.database.engine.url` et les trois lecteurs
directs (`blog.py`, `document_generator.py`, `sds_template_generator.py`,
ajoutés par `628cd24` le 16/09) à la base de session ; toute divergence
arrête la session (`pytest.UsageError`).

```
$ pytest tests/test_vague0_as02_environnement_hermetique.py
hermetic (vague 0 / AS-02) : run_id=481f46865 base=digital_humans_test_481f46865 (créée par la session, détruite à la fin ; gabarit digital_humans_test)
hermetic : DATABASE_URL posée par le bootstrap (absente avant) ; env=.env.test ; redis db=9 file=test-481f46865 ; tmp=/tmp/dh-test-481f46865-3ku0py47
hermetic : réseau sortant refusé sauf 127.0.0.1, ::1, localhost
======================= 24 passed, 24 warnings in 11.51s =======================
```

Refus sans `TEST_DATABASE_URL`, `DATABASE_URL` pointant `digital_humans_db`
sur un port où rien n'écoute (toute tentative de connexion aurait laissé
« Connection refused » dans la sortie ; le test l'affirme absent) :

```
$ env -i PATH=$PATH HOME=/tmp DATABASE_URL=postgresql://dh:x@127.0.0.1:1/digital_humans_db pytest -q tests/test_vague2_lot1_garde_database_url.py
E   tests.hermetic.HermeticEnvironmentError: Refus de lancer la suite de tests : TEST_DATABASE_URL est absente.
E   DATABASE_URL est posée (base 'digital_humans_db') mais la suite ne se replie JAMAIS dessus : c'est ce repli qui pointait la base réelle (OPS-05).
E   Posez un gabarit de base jetable (la session en dérive une base par exécution, la crée et la détruit) :
E       export TEST_DATABASE_URL=postgresql://dh_test:changeme@127.0.0.1:5432/digital_humans_test
E   Le rôle doit avoir CREATEDB. Voir backend/tests/README.md.
```

### 1.3 Exigence 2 — Redis, Chroma, fichiers séparés

Commits `2d355a2` (ARQ), `d5b3879` (sorties agents), `4ec6098`.

- `grep` des appelants avant correctif : la file `"digital-humans"` en dur à
  **7 endroits** (`execution_routes.py` ×4 dont le `llen` de
  `/workers/health`, `retry_routes.py` ×3, `worker.py`). `arq_config` lit
  désormais `DH_REDIS_HOST/PORT/DB` et `DH_ARQ_QUEUE_NAME` ; `ARQ_QUEUE_NAME`
  est importé par les sept sites. Après : `grep -n '"digital-humans"'` sur
  ces trois fichiers → aucune occurrence hors commentaire (assertion de
  `test_aucun_nom_de_file_arq_en_dur`, ×3).
- La session pose `DH_REDIS_DB=9` (`.env.test` ; 0 et 1 sont refusées) et
  la file `test-<run_id>`. `WorkerSettings.queue_name is ARQ_QUEUE_NAME` est
  testé sur l'objet, pas sur la source.
- `DH_OUTPUT_DIR`, `DH_METADATA_DIR`, `DH_CHROMA_PATH`, `DH_DELIVERABLES_DIR`,
  `UPLOAD_DIR`, `DH_SFDX_PROJECT_PATH`, `DH_FORCE_APP_PATH` pointent un
  `mkdtemp` de session, détruit à la fin. `AgentIntegrationService.output_dir`
  (`backend/outputs` en dur, un seul appelant : `execution_routes.py:551`)
  lit `settings.OUTPUT_DIR`.

### 1.4 Exigence 3 — aucune clé réelle, aucun réseau sortant

Commit `4ec6098`. Dix-neuf variables (`hermetic.SECRET_VARS`, issues de
`grep -rhoE "(KEY|TOKEN|SECRET|PASSWORD)"` sur `app/`, `agents/`, `tools/`,
`scripts/`) prennent la valeur de `backend/.env.test` : vide ou préfixée
`dh-test-fake-`. Une valeur réelle dans l'environnement fait refuser la
session, en nommant la variable et jamais sa valeur (asserté). Ce refus a
joué **en vrai** pendant la mission : le bac à sable porte un `GITHUB_TOKEN`
réel :

```
E   tests.hermetic.HermeticEnvironmentError: Refus de lancer la suite de tests : l'environnement porte une valeur réelle pour GITHUB_TOKEN.
E   Relancez sans ces variables, par exemple :
E       env -u GITHUB_TOKEN python -m pytest -q
```

Toutes les mesures « après » ont donc été lancées avec `env -u GITHUB_TOKEN`.

Contrôle négatif, clé Anthropic de forme réelle (`sk-ant-api03-` + 40
caractères, construite à l'exécution pour ne pas déclencher
`test_no_hardcoded_secrets`) :

```
E   tests.hermetic.HermeticEnvironmentError: Refus de lancer la suite de tests : l'environnement porte une valeur réelle pour ANTHROPIC_API_KEY.
E   La suite n'accepte aucune clé venant de l'extérieur : les valeurs factices viennent de backend/.env.test.
```

Même contrôle pour `STRIPE_SECRET_KEY=sk_live_…` (test dédié, vert).

Garde réseau (maison, pas de dépendance) : `socket.socket.connect` et
`connect_ex` refusent toute adresse hors boucle locale, hôte de
`TEST_DATABASE_URL` et `DH_REDIS_HOST`, lèvent `OutboundNetworkBlocked` et
**comptent** la tentative ; une fixture autouse fait échouer au démontage le
test qui en a provoqué une, même si le code l'a avalée
(`test_un_appel_sortant_avale_par_le_code_fait_quand_meme_echouer_le_test`,
joué dans un pytest enfant avec un `except Exception: pass`). Testé sur
`socket.create_connection` et sur `httpx.get` vers `192.0.2.1` (TEST-NET-1,
jamais routé : sans la garde, l'appel tomberait en timeout, pas en refus).

`psycopg2` (libpq, en C) ne passe pas par `socket.socket` : l'appel Python
`psycopg2.connect` est gardé à part et refuse une base connue comme réelle ou
un hôte distant. Ce test a été écrit **avec** sa garde, pas avant ; contrôle
inverse exécuté pour prouver qu'il mord — garde désactivée temporairement :

```
E   psycopg2.OperationalError: connection to server at "127.0.0.1", port 5432 failed: FATAL:  database "digital_humans_db" does not exist
1 failed
```

La connexion partait vraiment. Garde restaurée, test vert.

### 1.5 Exigence 4 — parallélisme

`run_id` = pid + 6 hex (ou `DH_TEST_RUN_ID`), base
`digital_humans_test_<run_id>` créée dans `pytest_configure` par une
connexion de maintenance à `postgres`, détruite dans `pytest_unconfigure`
(`pg_terminate_backend` puis `DROP DATABASE`), repli `atexit` si un import
échoue entre les deux. Le gabarit nommé dans `TEST_DATABASE_URL` n'est jamais
touché — il n'a même pas besoin d'exister (il n'existe pas dans le bac à
sable). `drop_all` ne s'exécute donc plus jamais sur une base partagée.

Preuve : `test_une_execution_enfant_a_sa_propre_base_et_la_detruit_en_sortant`
lance un pytest enfant avec `DH_TEST_RUN_ID=enfant<pid>`, vérifie que son
en-tête nomme `digital_humans_test_enfant<pid>`, puis interroge
`pg_database` : la base du parent existe encore, celle de l'enfant a disparu.
Après les mesures complètes :

```
$ psql ... -c "select datname from pg_database where datname like 'digital_humans_test%'"
 digital_humans_test_red / _red_autre / _ref_a / _ref_b      <- créées à la main pour les mesures, rien d'autre
```

### 1.6 Exigence 5 — contrôles négatifs

Quatre tests par pytest enfant, environnement construit de zéro
(`env` minimal, rien d'hérité) : base de prod sans `TEST_DATABASE_URL` ;
aucune URL ; clé Anthropic réelle ; clé Stripe réelle. Chacun affirme :
`returncode != 0`, la variable nommée, `" passed"` et `"collected"` absents
(rien n'est collecté), et aucune trace de connexion (`OperationalError`,
`Connection refused`, `could not connect`, `psycopg2`). Un contrôle positif
prouve le pendant : `TEST_DATABASE_URL` seule suffit, `15 passed`.

### 1.7 Correctif induit — `config.py` (commit `b0f7993`)

Le premier passage complet sous le bootstrap donnait `41 failed` : 8 tests de
`test_lot_e_secrets_and_paths.py` (« le *défaut* de chaque chemin est sous le
checkout ») construisent `Settings(_env_file=None)` après `delenv("DH_X")`.
Or les dix chemins étaient calculés **à la définition de la classe** : une
instance fraîche héritait de la valeur lue à l'import. Verts par hasard dans
un bac à sable sans `DH_*`, rouges sur le VPS (la vague B le notait), rouges
dès que la suite pose ses répertoires temporaires. `Field(default_factory=…)`
sur les dix chemins ; `test_paths_are_rooted_in_the_checkout` lisait le
`settings` global (l'environnement de l'opérateur), il lit désormais une
instance sans sa variable, comme ses voisins — même prédicat, sur le bon
objet, aucune assertion affaiblie. Après : `27 passed` sur le fichier.

Le dixième rouge de ce passage était `test_no_hardcoded_secrets` sur mon
propre fichier : un f-string `postgresql://{url.username}:{url.password}@…`
ressemble à un secret pour le motif. Reformulé via `make_url(...).set(...)`.

---

## 2. Non confirmé

- **Le VPS.** Rien n'a été exécuté sur le VPS après le clone de la branche
  (règle : ne pas toucher `.env`, systemd, services). La suite y a une base
  Redis réelle sur `localhost:6379` : la session y écrira dans la **DB 9**
  du même serveur, et sur une file `test-<run_id>`, jamais DB 0/1 ni
  `digital-humans`. Reste à jouer une fois sur le VPS avec un rôle `CREATEDB`
  (commande dans `backend/tests/README.md`).
- **Chroma.** `DH_CHROMA_PATH` est posé sur le répertoire temporaire ; aucun
  test de la mission n'ouvre réellement un `PersistentClient` pour vérifier
  qu'il y écrit (lu, non exécuté : `rag_service` lit `settings.CHROMA_PATH`).
- **Le `.env` du VPS n'est jamais lu** : prouvé par `settings.LOG_FORMAT ==
  "plain"` (`.env.test` pose `plain`, `.env.example` et le VPS `json`) et par
  les secrets factices, dans un bac à sable **sans** `backend/.env`. Le cas
  « `.env` présent avec des clés réelles » n'a pas été joué avec un vrai
  fichier ; le mécanisme (`DH_ENV_FILE` lu par `load_dotenv` et
  `Settings(_env_file=…)`) est le même.

## 3. Reste ouvert

- 31 rouges antérieurs (tableau §0), dont 27 sur un routeur commenté :
  OPS-06.
- `test_open_websockets_do_not_pin_connections` instable (§0).
- Trois tests connectent encore `psycopg2` en dur vers
  `172.17.0.1/digital_humans_db` (`test_wbs_task_types.py`,
  `test_wizard_phase5.py`, `e2e/test_sds_workflow_e2e.py`), ignorés sans
  `DH_TEST_DB_PASSWORD`. Avec la variable, la garde `psycopg2` les refuse
  désormais ; ils sont à réécrire (OPS-06).
- `tests/test_full_flow.py` à la racine du dépôt n'est pas couvert.
- La garde réseau ne voit pas une bibliothèque en C qui ouvre elle-même ses
  sockets (libpq est traitée ; d'autres pourraient exister).
- Le garde-fou de chiffrement crie toujours `CRITICAL` à chaque session
  (`CREDENTIALS_ENCRYPTION_KEY` vide, `DEBUG=True`) : c'est voulu (vague 2),
  et bruyant.

## 4. Non fait, et pourquoi

- **Pas de `pytest-socket`** : garde maison, pour ne pas ajouter une
  dépendance et pour compter les tentatives avalées (le plugin ne le fait
  pas).
- **Pas de PostgreSQL à la place de SQLite** dans `test_state_machine.py`
  (`sqlite:///./test_state_machine.db`, écrit dans le cwd) ni dans
  `test_credit_service.py` (`sqlite:///:memory:`) : locaux, hors périmètre.
- **Pas de fusion dans `vague-c`** (interdit §6) : PR ouverte.
- **Pas d'exécution de la suite depuis le VPS** (§2).

---

## Commits de la branche

| Commit | Objet |
|---|---|
| `7f308b9` | test rouge : 23 tests, `9 failed, 2 passed, 12 errors` sur `abcc04f` |
| `9614c50` | `DH_ENV_FILE` lu par `main.py` et `config.py` |
| `2d355a2` | Redis et file ARQ depuis l'environnement, une seule source, 7 sites |
| `d5b3879` | `AgentIntegrationService.output_dir = settings.OUTPUT_DIR` |
| `b0f7993` | défauts de chemins évalués à l'instanciation ; test lot E sur le bon objet |
| `4ec6098` | bootstrap hermétique, `.env.test`, garde réseau, test psycopg2 |
| `5d35156` | l'exemple d'URL du message de refus sans mot de passe littéral (`test_no_hardcoded_secrets` le signalait une fois `hermetic.py` suivi) |
| (docs) | `backend/tests/README.md`, ce rapport |

**Écart avec le prompt de mission :** la consigne de session demandait de développer sur
`claude/vague-c-20260906` ; la mission (§ en-tête et §6) impose une branche dédiée et
interdit la fusion dans `vague-c`. La mission a primé : branche
`claude/vague0-as02-env-test`, PR vers `vague-c`. Les 18 commits du VPS non poussés
(`51f0572..abcc04f`) ont été poussés **sur cette branche seulement**, pas sur
`origin/claude/vague-c-20260906`, qui reste à `cc89ca8`.
