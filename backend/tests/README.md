# Suite de tests backend — comment la lancer sans risque

Vague 0 / AS-02 (OPS-05, audit Astra du 06/09/2026). Depuis le 16/09, une
session pytest est **hermétique** : elle ne peut joindre aucune base, file,
répertoire ou clé de production. Le mécanisme vit dans `tests/hermetic.py`,
appelé par `tests/conftest.py` avant tout import de `app`.

## Lancer la suite

```bash
cd backend
export TEST_DATABASE_URL=postgresql://dh_test:changeme@127.0.0.1:5432/digital_humans_test
./venv/bin/python -m pytest tests/ -q
```

C'est la **seule** variable à poser. Elle désigne un *gabarit* : un serveur
PostgreSQL et des identifiants dont le rôle a le droit `CREATEDB`. La base
nommée (`digital_humans_test`) n'est jamais touchée ; la session en dérive une
base **par exécution**, la crée au démarrage et la détruit à la fin :

```
hermetic (vague 0 / AS-02) : run_id=481f46865 base=digital_humans_test_481f46865 (créée par la session, détruite à la fin ; gabarit digital_humans_test)
hermetic : DATABASE_URL posée par le bootstrap (absente avant) ; env=.env.test ; redis db=9 file=test-481f46865 ; tmp=/tmp/dh-test-481f46865-3ku0py47
hermetic : réseau sortant refusé sauf 127.0.0.1, ::1, localhost
```

Ces trois lignes sont l'en-tête de chaque session (masquées en `-q`).

Préparer le rôle, une fois par machine :

```sql
CREATE ROLE dh_test WITH LOGIN PASSWORD 'changeme' CREATEDB;
```

Le mot de passe est local à la machine de test ; il ne va nulle part ailleurs.

## Ce que la session impose, dans l'ordre

1. **Aucun secret réel dans l'environnement.** Les variables listées dans
   `hermetic.SECRET_VARS` (clés Anthropic, OpenAI, Stripe, Ghost, Git,
   Salesforce, SMTP, Telegram, `SECRET_KEY`, …) prennent la valeur de
   `backend/.env.test` : vide ou préfixée `dh-test-fake-`. Si le shell en
   porte une autre valeur, la session **refuse de démarrer** et dit laquelle :
   `env -u ANTHROPIC_API_KEY python -m pytest`.
2. **`TEST_DATABASE_URL` obligatoire.** Aucun repli sur `DATABASE_URL` : c'est
   ce repli qui pointait la base réelle sur le VPS. Sans la variable, refus
   à la collecte, avant toute connexion, avec la commande à exporter.
3. **Une seule source pour la base.** `DATABASE_URL` et `TEST_DATABASE_URL`
   de l'environnement sont remplacées par la base de session. `settings`,
   `app.database.engine`, les modules qui lisent `os.getenv("DATABASE_URL")`
   et ce conftest voient donc la même chose ; `pytest_configure` le vérifie
   et arrête la session en cas de divergence.
4. **`backend/.env.test` seul fichier d'environnement.** `DH_ENV_FILE` le
   désigne ; `app.main` (`load_dotenv`) et `app.config` (`Settings`) le
   respectent. `backend/.env` n'est jamais lu par un test.
5. **Redis, Chroma, fichiers séparés.** Redis DB 9 (0 et 1 sont refusées),
   file ARQ `test-<run_id>` (lue par le worker et par toutes les routes qui
   enfilent, via `arq_config.ARQ_QUEUE_NAME`), et un répertoire temporaire de
   session pour `DH_OUTPUT_DIR`, `DH_METADATA_DIR`, `DH_CHROMA_PATH`,
   `DH_DELIVERABLES_DIR`, `UPLOAD_DIR`, `DH_SFDX_PROJECT_PATH`,
   `DH_FORCE_APP_PATH`. Rien ne s'écrit sous `/opt/digital-humans` ni sous
   `/root/workspace/*/outputs`.
6. **Réseau sortant refusé.** `socket.connect` hors boucle locale lève
   `OutboundNetworkBlocked`, et la tentative est comptée : le test qui l'a
   provoquée **échoue au démontage même si le code a avalé l'exception**.
   `psycopg2.connect` (libpq, en C, hors `socket.socket`) est gardé à part :
   une base connue comme réelle ou un hôte distant sont refusés avant la
   connexion.

## Plusieurs agents en parallèle

Rien à configurer : chaque `pytest` dérive son identifiant de run (pid +
aléa), donc sa base, sa file ARQ et son répertoire temporaire. Deux sessions
simultanées ne se voient pas.

Pour nommer une exécution (journaux, débogage) :

```bash
DH_TEST_RUN_ID=agent_securite pytest tests/ -q     # base digital_humans_test_agent_securite
```

Un identifiant explicite doit être unique entre sessions simultanées : une
base homonyme laissée par un run interrompu est détruite au démarrage suivant.

## Variables optionnelles

| Variable | Effet |
|---|---|
| `DH_TEST_RUN_ID` | Identifiant de run explicite (`[a-z0-9]`, le reste devient `_`). |
| `DH_TEST_KEEP=1` | Conserve la base et le répertoire temporaire à la fin, en le journalisant. |
| `DH_TEST_ALLOW_HOSTS=h1,h2` | Dérogation réseau explicite, journalisée en WARNING. Ne l'utilisez pas pour joindre un service de production. |
| `DH_REDIS_HOST`, `DH_REDIS_PORT` | Adresse du Redis de test (défaut localhost:6379). La DB reste celle de `.env.test`. |
| `DH_TEST_TMP_ROOT` | Répertoire parent du répertoire temporaire de session. |

## Ce qui reste hors périmètre

- Les tests qui échouent pour d'autres raisons (OPS-06) ne sont pas réparés
  ici, seulement comptés : voir `docs/missions/RAPPORT_VAGUE0_AS02.md`.
- `tests/test_wbs_task_types.py`, `tests/test_wizard_phase5.py` et
  `tests/e2e/test_sds_workflow_e2e.py` portent encore une connexion
  `psycopg2` en dur vers `172.17.0.1/digital_humans_db`, ignorée sans
  `DH_TEST_DB_PASSWORD`. Si la variable est posée, la garde `psycopg2` refuse
  la base ; ces tests sont à réécrire (OPS-06).
- `../tests/test_full_flow.py` (racine du dépôt) n'est pas collecté par
  `cd backend && pytest tests/` et n'est pas couvert par ce bootstrap.
