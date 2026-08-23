# Audit technique indépendant — `digital-humans-production`

**Date** : 23 août 2026
**Tête auditée** : `9e3d6fa` (`fix: la documentation d API n est plus servie en production`), tête de `origin/correctifs/audit-croise-20260821`
**Cadre** : rejeu indépendant du prompt `docs/audit-20260821/prompt-audit.md`
**Périmètre de lecture** : tout le dépôt **sauf** `docs/audit-20260821/` (hors `prompt-audit.md`) et `docs/vague3/`, non ouverts.

---

## Verdict

**Non. Pas le 1er octobre dans cet état, et le blocage n'est pas une question de finition.**

Trois faits mesurés cette nuit suffisent : `pip install -r requirements.txt` produit un backend qui **ne démarre pas** (`arq` et `redis` ne sont déclarés nulle part) ; `alembic upgrade head` sur une base vierge **échoue et ne crée aucune table** (dix tables du modèle n'ont aucune migration) ; le mot de passe PostgreSQL de production est **en clair dans neuf fichiers du dépôt**, dont `docker-compose.prod.yml`. Aucun nouveau client ne peut donc être installé, et le secret est à faire tourner.

S'y ajoute un défaut commercial : le compteur de crédits **n'est jamais appelé** — mesuré, pas déduit. Le plafond conçu pour le palier Pro (2 000 crédits/mois, ~3 SDS) n'existe pas à l'exécution, et le plafond de débit qui sert de dernier rempart se contourne avec un en-tête HTTP.

Conditions d'ouverture : la vague 1 ci-dessous (≈ 40 h) est incompressible. Le reste peut suivre. Ce qui a été corrigé depuis l'audit d'origine tient globalement — le problème n'est pas là où la liste P0–P12 le disait.

---

## Méthode et niveau de preuve

Chaque constat porte une marque :

| Marque | Sens |
|---|---|
| **[EXÉCUTÉ]** | reproduit par une commande dont la sortie est citée |
| **[LU]** | établi par lecture du code, non exécuté — la commande de vérification est donnée |

Environnement monté pour l'audit : Python 3.11, PostgreSQL 16 local, Redis 7, ChromaDB 1.3.4, dépendances de `requirements.txt` + `requirements-test.txt`. Aucun appel LLM réel n'a été émis (fournisseur remplacé par un double). **Aucune écriture sur le VPS, aucune modification de code applicatif.**

Référence mesurée de la suite de tests, sur base PostgreSQL dédiée :

```
$ pytest tests/ -q --timeout=120
11 failed, 591 passed, 1 skipped, 7 xfailed, 226 warnings in 369.23s
```

---

# 1. Ce qui casse en production

---

### `DEP-01` — `arq` et `redis` ne sont déclarés dans aucun fichier de dépendances — **bloquant**

**Fichier** : `backend/requirements.txt` (absence) ; `backend/app/workers/arq_config.py:2` ; `backend/Dockerfile:52`

**[EXÉCUTÉ]** Résolution complète de la fermeture de dépendances, puis import :

```
$ pip install --dry-run --ignore-installed --report r.json -r requirements.txt
   162 paquets résolus.  arq : NON   redis : NON

$ PYTHONPATH=. python -c "import app.main"
  File "app/workers/arq_config.py", line 2, in <module>
    from arq import create_pool
ModuleNotFoundError: No module named 'arq'
```

**Ce qui se passe** : `app/main.py:16` importe les routes, qui importent `orchestrator/execution_routes.py:26`, qui importe `arq_config`. Le `Dockerfile:52` n'installe que `requirements.txt`. Donc `docker compose -f docker-compose.prod.yml build && up` construit une image dont le processus meurt à l'import, sur toute machine neuve. Le VPS actuel tourne parce que ces paquets y ont été installés à la main un jour, hors de toute trace. `requirements-test.txt` affirme en tête que « la suite s'installe avec `pip install -r requirements-test.txt` **et rien d'autre** » : c'est faux.

**Correctif** — dans `requirements.txt` :

```
arq==0.26.1
redis>=5.0,<6
```

**Effort** : 1 h (dont la vérification en conteneur neuf).

---

### `DEP-02` — l'authentification dépend de `PyJWT`, présent par accident — **bloquant**

**Fichier** : `backend/app/utils/email_token.py:28` (`import jwt`)

**[EXÉCUTÉ]** `requirements.txt` déclare `python-jose` (module `jose`), jamais `PyJWT` (module `jwt`). PyJWT arrive dans l'arbre par une seule arête :

```
$ python -c "…report…"
nomic 3.9.0 -> pyjwt
PyJWT resolved version: 2.13.0   requested_by_user: False
```

`nomic` est la bibliothèque d'embeddings du RAG. Le jour où elle est retirée, remplacée, ou change de dépendances, `app.main` ne s'importe plus : **toute l'API tombe**, à cause d'un module de jetons d'e-mail.

**Correctif** : ajouter `PyJWT>=2.8,<3` à `requirements.txt` ; ou mieux, réécrire `email_token.py` avec `jose`, déjà présent et déjà utilisé par `app/utils/auth.py:6` — deux bibliothèques JWT dans le même processus n'apportent rien.

**Effort** : 15 min (déclaration) ou 2 h (unification).

---

### `MIG-01` — `alembic upgrade head` échoue sur base vierge ; 10 tables sur 34 n'ont aucune migration — **bloquant**

**Fichier** : `backend/alembic/versions/007_backfill_project_conversations_agent_id.py:34`

**[EXÉCUTÉ]** Sur une base PostgreSQL fraîche :

```
$ alembic upgrade head
INFO  Running upgrade 006_validation_gates -> 007_conv_agent_id
sqlalchemy.exc.NoSuchTableError: project_conversations

$ psql -d dh_alembic -c "select tablename from pg_tables where schemaname='public'"
(0 ligne)          # DDL transactionnel : tout est annulé
```

**[EXÉCUTÉ]** Écart complet entre le modèle et les migrations :

```
tables déclarées par l'ORM         : 34
tables créées par alembic          : 22
tables créées par migrations/*.sql :  4

TABLES DE L'ORM QU'AUCUNE MIGRATION NE CRÉE : 10
  business_requirements   change_requests    chat_logs
  deliverable_items       llm_interactions   project_conversations
  project_documents       sds_versions       task_executions
  uc_requirement_sheets
```

**Ce qui se passe** : ces tables n'existent sur le VPS que parce que `Base.metadata.create_all()` y a tourné à une époque. Le correctif de la vague 2 (`AUTO_CREATE_SCHEMA` non posé par défaut, `app/main.py:51-58`) a coupé cette béquille sans jamais reconstituer les migrations qui la remplaçaient. Conséquence concrète : **une installation neuve est impossible** — nouveau client, déploiement on-premise, reprise après sinistre, environnement de recette. `task_executions` porte les tâches BUILD, `business_requirements` les BR, `sds_versions` les livrables : ce n'est pas de l'accessoire.

**Correctif** : générer une migration de rattrapage à partir du modèle, puis rendre 007 défensif.

```bash
alembic revision --autogenerate -m "rattrapage: 10 tables jamais migrees"
# puis, dans 007, avant get_columns :
insp = sa.inspect(op.get_bind())
if "project_conversations" not in insp.get_table_names():
    return
```

Critère de fin, à exécuter : `alembic upgrade head` sur base vide, puis `alembic check` sans écart.

**Effort** : 6 h (dont la relecture du diff autogénéré, qui n'est jamais bon du premier coup).

---

### `CRASH-01` — le chat projet plante en 500 dès que la description du projet est nulle — **majeur**

**Fichier** : `backend/app/services/sophie_chat_service.py:240`

```python
- Description: {project_info.get('description', 'Non disponible')[:500]}
```

**[EXÉCUTÉ]** Rencontré en montant le banc d'essai des paliers, sur un projet créé sans description :

```
File "app/services/sophie_chat_service.py", line 240, in _build_system_prompt
    - Description: {project_info.get('description', 'Non disponible')[:500]}
TypeError: 'NoneType' object is not subscriptable
```

**Ce qui se passe** : `dict.get(k, défaut)` ne rend le défaut que si la **clé** manque — pas si la valeur vaut `None`. `projects.description` est nullable. Un projet créé par l'API sans description, ou par le wizard avant l'étape correspondante, rend `POST /api/projects/{id}/chat` définitivement inutilisable : 500 à chaque message, pour ce projet, pour toujours.

**Correctif** :

```python
- Description: {(project_info.get('description') or 'Non disponible')[:500]}
```

Chercher le même motif ailleurs : `grep -rn "\.get(\s*['\"][a-z_]*['\"]\s*,\s*['\"][^'\"]*['\"]\s*)\[" backend/app`.

**Effort** : 30 min avec le test de non-régression.

---

### `TIME-01` — le délai de garde de 600 s sur un appel LLM ne borne rien — **majeur**

**Fichier** : `backend/app/services/llm_router_service.py:978-982`

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    future = pool.submit(asyncio.run, self.complete(request))
    return future.result(timeout=600)
```

**[EXÉCUTÉ]** Reproduction du motif exact :

```
TimeoutError levé, mais on sort du bloc `with` à t+5.0s
durée totale réellement subie par l'appelant : 5.0s (borne annoncée : 1,0 s)
```

**Ce qui se passe** : `future.result(timeout=…)` lève bien, mais la sortie du bloc `with` appelle `ThreadPoolExecutor.__exit__`, donc `shutdown(wait=True)`, qui **attend la fin du fil**. Un appel Anthropic qui ne répond pas bloque l'agent aussi longtemps qu'il dure, quel que soit le nombre écrit dans le code. Sur un worker à `max_jobs = 10`, dix appels pendus figent tout le pipeline sans qu'aucune alerte ne se déclenche : les exécutions restent `RUNNING`, l'interface affiche une progression qui n'avance plus.

**Correctif** : sortir du motif « exécuteur jetable ». Un exécuteur unique de module + `future.cancel()`, ou mieux, remonter `complete_sync` sur le client HTTP synchrone d'Anthropic avec son propre `timeout=` — le SDK le supporte, et un timeout socket, lui, coupe vraiment.

```python
_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=8)  # module-level
...
future = _POOL.submit(asyncio.run, self.complete(request))
try:
    return future.result(timeout=600)
except concurrent.futures.TimeoutError:
    future.cancel()
    raise
```

**Effort** : 3 h.

---

### `TIME-02` — le délai de garde par agent n'arrête pas l'agent — **majeur**

**Fichier** : `backend/app/services/pm_orchestrator_service_v2.py:2088-2091`

```python
output_data = await asyncio.wait_for(
    asyncio.to_thread(agent_instance.run, task_data),
    timeout=timeout_seconds        # 600 à 3600 s selon l'agent
)
```

**[EXÉCUTÉ]** :

```
timeout levé à 0,5 s (comme _run_agent le rattrape)
  fils actifs juste après le timeout : 2 (départ 1)
  le fil a-t-il été arrêté ?          : NON
  3,2 s plus tard, le fil a terminé son travail : True
```

**Ce qui se passe** : Python n'arrête pas un fil de l'extérieur. Emma dépassant ses 3 600 s est marquée `failed`, l'orchestrateur passe à la suite — et le fil d'Emma continue : il consomme des jetons facturés, écrit en base, et occupe définitivement une place du pool de fils par défaut (`min(32, cpu+4)`). Quelques agents ainsi « morts-vivants » et le worker cesse silencieusement de traiter quoi que ce soit. Cumulé avec `TIME-01`, c'est le scénario d'arrêt le plus probable en production sous charge.

**Correctif** : le délai doit vivre **dans** l'appel, pas autour. Passer un `timeout` au client HTTP du fournisseur (`llm_service` → SDK Anthropic) et supprimer le `wait_for` externe, ou le conserver uniquement comme filet en journalisant explicitement qu'un fil est abandonné (compteur de fils orphelins exposé).

**Effort** : 4 h.

---

### `PERF-01` — `subprocess.run` sur la boucle d'événements — **majeur**

**Fichier** : `backend/app/api/routes/agent_tester.py:142` (dans `async def query_org`, l. 124)

**[LU]** `subprocess.run([...], timeout=30)` est appelé directement dans une coroutine. Pendant l'appel au CLI `sf` — 5 à 30 s en pratique — **la boucle d'événements ne fait rien d'autre** : aucune autre requête HTTP n'est servie, aucun flux SSE ne progresse, aucun `to_thread` n'est ordonnancé. Un seul utilisateur sur cette route gèle l'API pour tous les autres.

Le reste du dépôt applique déjà la bonne forme : `pm_orchestrator_service_v2.py:1780` enveloppe le même appel dans `asyncio.to_thread`. Ce site a été oublié.

**Correctif** :

```python
result = await asyncio.to_thread(
    subprocess.run, [...], shell=False, capture_output=True, text=True, timeout=30
)
```

**Vérification** : `python scan_async.py app/api/routes` (script fourni en annexe) ne doit plus rendre de `subprocess.run()`.

**Effort** : 30 min.

---

### `PERF-02` — SQLAlchemy synchrone dans des routes `async` : P0 n'est pas terminé — **mineur à majeur selon la route**

**[EXÉCUTÉ]** Analyse de l'arbre syntaxique sur `app/api/routes/` — appels bloquants **hors** fonction imbriquée, dans le corps d'une `async def` :

| Fichier:ligne | Route | Appels |
|---|---|---|
| `auth.py:35` | `POST /api/auth/register` | `db.query`, `db.add`, `db.commit`, `db.refresh` |
| `auth.py:235` | `POST /api/auth/login` | `db.query` |
| `auth.py:160` | `POST /api/auth/signup-confirm` | `db.query`, `db.add`, `db.commit` |
| `project_chat.py:22/56/86` | chat projet | `db.query` ×5, `db.commit` |
| `retry_routes.py:27` | `POST …/retry` | `db.query`, `db.commit` |
| `build_routes.py:212` | `POST …/start-build` | `db.commit` |
| `validation_gate_routes.py:235` | reprise après porte | `db.query`, `db.commit` ×3 |
| `quality_dashboard.py:178` (route), `:68` (coroutine appelée par une route) | qualité | `session.execute` |
| `concierge_routes.py:89/110` | historique concierge | `db.query`, `db.commit` |

Le motif correct existe et est appliqué ailleurs (`execution_routes.py:57-90`, `_prepare_execution` + `asyncio.to_thread`). Le statut déclaré « P0 corrigé » est donc **partiellement tenu** : les routes chaudes de l'orchestrateur ont été traitées, l'authentification et le chat ne l'ont pas été.

**Gravité réelle** : `login`/`register` font un `bcrypt` (≈ 100 ms de CPU) **plus** une requête SQL synchrone sur la boucle. À 20 connexions simultanées, la latence de toutes les autres routes se dégrade visiblement. C'est mineur à 10 clients, majeur à 100.

**Correctif** : soit `def` au lieu de `async def` (FastAPI bascule alors seul dans le pool de fils — c'est la correction la moins risquée et elle tient en un mot-clé), soit extraction dans `asyncio.to_thread`.

**Effort** : 4 h pour les 12 routes.

---

### `RES-01` — un pool Redis neuf est créé à chaque mise en file, jamais fermé — **mineur**

**Fichier** : `backend/app/workers/arq_config.py:12` ; 8 sites d'appel (`execution_routes.py:94,154,218,570`, `retry_routes.py:113,263`, `validation_gate_routes.py:267`, `build_routes.py:237`)

**[EXÉCUTÉ]** Mesure honnête, qui **nuance** l'hypothèse de fuite :

```
connexions Redis au départ : 1
après 30 enqueue sans fermeture : 12
après gc.collect() : 2
```

Ce n'est donc **pas** une fuite non bornée : le ramasse-miettes finit par fermer. C'est du brassage de connexions — poignée de main TCP à chaque `POST /execute`, pic de connexions entre deux cycles de GC, et avertissements `Unclosed connection` dans les journaux. Négligeable à 10 clients, à corriger avant 100.

**Correctif** : un pool unique en cycle de vie applicatif.

```python
# app/workers/arq_config.py
_pool = None
async def get_redis_pool():
    global _pool
    if _pool is None:
        _pool = await create_pool(REDIS_SETTINGS)
    return _pool
```
et sa fermeture dans le `shutdown_event` de `main.py`.

**Effort** : 1 h.

---

### `RES-02` — tâche `asyncio` créée sans référence forte — **mineur**

**Fichier** : `backend/app/services/pm_orchestrator_service_v2.py:2193`

```python
loop.create_task(self._async_notify_progress(...))
```

**[EXÉCUTÉ]** Constaté dans la sortie de la suite de tests :

```
Message: "Task was destroyed but it is pending!
 task: <Task pending coro=<PMOrchestratorServiceV2._async_notify_progress()
 running at app/services/pm_orchestrator_service_v2.py:2200>"
```

La documentation de `asyncio` est explicite : sans référence conservée, le ramasse-miettes peut détruire la tâche en vol. Effet : des notifications de progression perdues au hasard — le flux SSE retombe sur son sondage et l'utilisateur voit une progression qui saute.

**Correctif** : `self._tasks = set()` ; `t = loop.create_task(...) ; self._tasks.add(t) ; t.add_done_callback(self._tasks.discard)`.

**Effort** : 30 min.

---

### `RACE-01` — course sur le total de coût d'une exécution (latente) — **mineur aujourd'hui, bloquant au premier passage en parallèle**

**Fichier** : `backend/app/services/budget_service.py:185-224` ; `pm_orchestrator_service_v2.py:3391`

**[LU]** `check_budget` lit `execution.total_cost`, `record_cost` le relit, additionne, valide — chacun dans **sa propre session** (`generate_llm_response` en ouvre une par appel, `llm_service.py:200-206`). Deux agents concurrents perdent une mise à jour. Aujourd'hui `PARALLEL_MODE = {"sds_experts": False, "build_agents": False}` (`pm_orchestrator_service_v2.py:335`) : le risque est dormant. Il s'active à la ligne où quelqu'un passera `sds_experts` à `True` pour accélérer la phase 4 — c'est-à-dire au premier travail de mise à l'échelle.

**Correctif** : incrément atomique côté base, pas côté Python.

```python
self.db.execute(
    update(Execution).where(Execution.id == execution_id).values(
        total_cost=Execution.total_cost + cost,
        total_tokens_used=Execution.total_tokens_used + input_tokens + output_tokens,
    )
)
```

**Effort** : 2 h.

---

# 2. Ce qui ne tient pas ensemble

---

### `ENV-01` — 22 variables d'environnement lues nulle part déclarées — **majeur**

**Fichier** : `backend/.env.example` (seul gabarit, qui s'annonce comme tel l. 4)

**[EXÉCUTÉ]** Recensement des `os.environ.get` / `os.getenv` du backend, croisé avec le gabarit :

```
ANTHROPIC_API_KEY   ANTHROPIC_BASE_URL   ANTHROPIC_FALLBACK_MODEL
STRIPE_SECRET_KEY   STRIPE_WEBHOOK_SECRET   STRIPE_PUBLISHABLE_KEY
STRIPE_PRICE_ID_PRO   STRIPE_PRICE_ID_TEAM
SMTP_HOST   SMTP_PORT   SMTP_USERNAME   SMTP_PASSWORD
SMTP_FROM_EMAIL   SMTP_FROM_NAME   EMAIL_BACKEND
CHAT_IP_SALT   JOURNAL_WEBHOOK_SECRET   FRONTEND_BASE_URL
STUDIO_PUBLIC_URL   AGENT_TEST_LOG_FILE   DH_LOG_LEVEL
```
plus `DH_DEPLOYMENT_PROFILE`, lu par interpolation YAML (`config/llm_routing.yaml:23`).

**Ce qui se passe** : la couche LLM entière (`ANTHROPIC_API_KEY`), la facturation entière (`STRIPE_*`), tous les e-mails transactionnels et deux secrets de sécurité ne figurent dans aucun gabarit. Un déploiement neuf monté à partir de `.env.example` démarre, répond `200` sur `/health` — et n'a ni LLM, ni paiement, ni e-mail. Deux se dégradent proprement (`CHAT_IP_SALT` refuse le tour, `STRIPE_WEBHOOK_SECRET` rend 503) ; les autres non.

**Correctif** : compléter `.env.example` (les 22, commentées, avec la conséquence de l'absence en une ligne chacune) et ajouter au démarrage un inventaire journalisé des variables attendues/absentes — dans la lignée de ce que fait déjà `encryption_posture` (`app/schema_bootstrap.py`), qui est le bon modèle.

**Effort** : 3 h.

---

### `CONF-01` — `docker-compose.prod.yml` décrit une production qui ne peut pas fonctionner — **bloquant**

**Fichier** : `docker-compose.prod.yml`

**[LU]**, quatre défauts sur 43 lignes :

| Ligne | Contenu | Conséquence |
|---|---|---|
| 27 | `uvicorn … --reload` | mode développement : un seul worker, surveillance de tout `/app` ; **toute écriture dans l'arbre monté redémarre l'API et tue les exécutions en cours** |
| 38 | `npm run dev -- --host …` | serveur de développement Vite en production : pas de build, pas de minification, cartes de source publiées |
| — | aucun service `redis`, aucun service worker ARQ | la file n'existe pas : `POST /execute` met en file dans le vide, **aucune exécution ne démarre** |
| 23 | volume `/opt/digital-humans/rag/chromadb_data` | monté à un chemin que la configuration ne lit pas — voir `CONF-02` |

Le fichier `docker-compose.yml` (développement) n'a pas non plus de Redis ni de worker.

**Correctif** : commande de production `uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 4` (après `SCALE-03` pour le plafond de débit) ; frontend en `build` + service statique ; ajout d'un service `redis:7-alpine` et d'un service `worker` (`python -m arq app.workers.worker.WorkerSettings`).

**Effort** : 4 h.

---

### `CONF-02` — le chemin ChromaDB monté n'est pas celui que le code lit — **majeur**

**Fichier** : `backend/app/config.py:107-110` ; `docker-compose.prod.yml:23`

**[LU]** `CHROMA_PATH` vaut par défaut `Path(__file__).resolve().parent.parent.parent / "rag" / "chromadb_data"`. Dans le conteneur, `__file__` est `/app/app/config.py`, donc la valeur est **`/rag/chromadb_data`**. Le volume est monté sur `/opt/digital-humans/rag/chromadb_data`, et ni le compose de production ni celui de développement ne pose `DH_CHROMA_PATH`.

Effet : les 70 000 chunks sont invisibles. Depuis la vague 2 la sonde `/health` le détecte (`main.py:314-334`, `0 chunks` → 503), donc la panne est **visible** — c'est un vrai progrès — mais la configuration reste fausse.

**Correctif** : `DH_CHROMA_PATH: /opt/digital-humans/rag/chromadb_data` dans les deux compose. Vérification : `curl -s localhost:8002/health | jq .checks.chroma`.

**Effort** : 15 min.

---

### `CONF-03` — second fichier de dépendances contradictoire — **mineur**

**Fichier** : `backend/agents/requirements.txt`

```
openai==1.3.7        # backend/requirements.txt dit : openai>=1.50.0
chromadb>=0.4.0      # backend/requirements.txt dit : chromadb==1.3.4
```

**[LU]** Quatre lignes, jamais installées par le `Dockerfile`, qui contredisent le fichier de référence. C'est exactement le motif « deux sources, aucune ne dit laquelle » que P12 avait retiré pour les `.env`. Il subsiste ici.

**Correctif** : supprimer le fichier ; `backend/requirements.txt` couvre déjà les quatre paquets.

**Effort** : 15 min (dont la vérification qu'aucun script ne l'installe : `grep -rn "agents/requirements" .`).

---

### `CONF-04` — `CLAUDE.md` contredit la configuration de routage — **mineur**

**Fichier** : `CLAUDE.md` (tableau « Les 11 agents ») vs `backend/config/llm_routing.yaml:31-66`

**[EXÉCUTÉ]** `CLAUDE.md` annonce Diego, Zara, Jordan, Aisha, Elena, Raj, Lucas en **Haiku**, Emma et Marcus en **Sonnet**. `llm_routing.yaml` classe Marcus, Sophie, Olivia et Emma en tier `orchestrator` (profil `cloud` → **Opus**) et les sept autres en `worker` (→ **Sonnet**). Aucun agent ne tourne en Haiku dans le profil de production.

Le document de référence du projet donne donc une image fausse de la structure de coût — celle-là même sur laquelle se décident les paliers.

**Correctif** : régénérer le tableau depuis `llm_routing.yaml`, ou le remplacer par un renvoi au fichier.

**Effort** : 30 min.

---

### Cherché et non trouvé (axe 2)

- **Appels frontend vers des routes inexistantes** : aucun. Les 74 chemins `/api/…` extraits de `frontend/src` ont été confrontés aux 167 routes réellement montées ; les 4 écarts apparents sont deux commentaires (`Dashboard.tsx:164`, `ProjectDetailPage.tsx:137` — qui documentent précisément la correction de ce défaut) et deux artefacts de mon extraction (`/api/wizard/{id}/step/{step}` existe sous forme de six routes littérales). **Le contrat frontend↔backend est cohérent.** [EXÉCUTÉ]
- **Imports circulaires au niveau module** : **zéro** sur `app/`, analyse de l'arbre syntaxique. [EXÉCUTÉ] À noter cependant 142 imports internes différés dans des corps de fonctions, répartis sur 33 fichiers : c'est le prix payé pour qu'il n'y en ait pas (voir `DETTE-02`).
- **Chemins absolus machine-spécifiques dans `app/`** : un seul (`FIX-P2` ci-dessous). P2 tient dans le code applicatif.

---

### `FIX-P2` — le motif des chemins absolus est réapparu — **mineur**

**Fichier** : `backend/app/api/routes/journal_webhook.py:24`

```python
BUILD_SCRIPT = Path("/root/workspace/digital-humans-production/scripts/journal/build.py")
```

**[EXÉCUTÉ]** C'est le **seul** chemin absolu machine-spécifique restant dans `backend/app/` — P2 est donc tenu à une occurrence près, apparue après. Ailleurs le motif persiste hors périmètre applicatif : 20 occurrences dans `backend/tests/` (`sys.path.insert('/root/workspace/…')`), plus `tools/`, `scripts/`, `n8n/`. Les tests concernés ne peuvent tourner que sur le VPS — c'est un des obstacles à une intégration continue (`OPS-02`).

**Correctif** : `BUILD_SCRIPT = settings.PROJECT_ROOT / "scripts" / "journal" / "build.py"`, à l'image de `blog.py:38` qui fait déjà exactement cela.

**Effort** : 15 min (+ 3 h pour les tests, à faire en même temps que la CI).

---

# 3. Sécurité

---

### `SEC-01` — mot de passe PostgreSQL de production en clair dans le dépôt — **bloquant**

**[EXÉCUTÉ]** `DH_SecurePass2025!` apparaît dans neuf fichiers versionnés :

```
docker-compose.prod.yml:13                        ← configuration de production
backend/app/api/routes/blog.py:16
backend/app/services/document_generator.py:40
backend/app/services/sds_template_generator.py:24
backend/tests/test_wizard_phase5.py:182
backend/tests/test_wbs_task_types.py:179
backend/tests/e2e/test_sds_workflow_e2e.py:438
tools/lib/collect_sds.py:97
SESSION_25NOV2025_SUMMARY.md:77
```

Dans les trois modules `app/`, c'est la valeur de repli de `os.getenv("DATABASE_URL", …)` — un module chargé sans `DATABASE_URL` se connecte donc à la base de production nommée en dur.

**Ce qui se passe** : toute personne ayant lu le dépôt une fois — développeur passé, agent de code, prestataire, sauvegarde — détient les identifiants de la base. Le retrait des lignes ne suffit pas : le secret est dans l'historique git.

**Correctif**, dans cet ordre :
1. **faire tourner le mot de passe PostgreSQL** (`ALTER ROLE digital_humans WITH PASSWORD …`), puis mettre à jour `backend/.env` sur le VPS ;
2. remplacer les trois replis par un échec net : `DATABASE_URL = os.environ["DATABASE_URL"]` — la clé absente doit lever, pas deviner ;
3. `docker-compose.prod.yml` : `DATABASE_URL: ${DATABASE_URL:?DATABASE_URL est requis}` ;
4. tests et outillage : lire `TEST_DATABASE_URL`.

**Effort** : 3 h.

---

### `SEC-02` — le plafond de débit se contourne avec un en-tête HTTP — **bloquant**

**Fichier** : `backend/app/rate_limiter.py:15-20` (`get_client_ip`, clé du limiteur l. 25)

```python
forwarded = request.headers.get("X-Forwarded-For")
if forwarded:
    return forwarded.split(",")[0].strip()      # première valeur = celle du client
```

**[EXÉCUTÉ]** Sur `POST /api/auth/login`, mot de passe faux :

```
A) 12 tentatives, même IP           : [401×5, 429×7]  -> 429 présent : True
B) 60 tentatives, X-Forwarded-For varié : 429 présent : False | {401: 60}
```

**Ce qui se passe** : `X-Forwarded-For` est un en-tête que le client choisit. Nginx **ajoute** sa valeur à la liste existante ; `split(",")[0]` reprend donc celle fournie par l'attaquant. Tous les plafonds tombent d'un coup :

- `AUTH_LOGIN 5/minute` → force brute sans limite sur les mots de passe ;
- `EXECUTE_SDS 10/hour` et `EXECUTE_BUILD 5/hour` → **le dernier garde-fou de coût disparaît** (voir `FIN-01`) ;
- concierge public `30/hour` → appels LLM anonymes sans plafond, seul le budget quotidien en base reste ;
- `audit_middleware.py:156` utilise la même fonction : **l'adresse IP du journal d'audit est falsifiable**.

**Correctif** : ne faire confiance à l'en-tête que s'il vient du proxy de confiance.

```python
TRUSTED_PROXIES = {"127.0.0.1", "172.17.0.1"}
def get_client_ip(request: Request) -> str:
    peer = get_remote_address(request)
    if peer in TRUSTED_PROXIES:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[-1].strip()   # dernier saut = posé par le proxy
    return peer
```
Et côté nginx, écraser plutôt qu'ajouter : `proxy_set_header X-Forwarded-For $remote_addr;`.

**Effort** : 3 h (dont la relecture de la configuration nginx, qui ne figure pas dans le dépôt — voir `OPS-04`).

---

### `SEC-03` — le budget d'une exécution est lisible sans authentification — **majeur**

**Fichier** : `backend/app/api/routes/orchestrator/execution_routes.py:547-563`

```python
@router.get("/execute/{execution_id}/budget")
def get_execution_budget(execution_id: int, db: Session = Depends(get_db)):
```
Ni `current_user`, ni contrôle de propriété.

**[EXÉCUTÉ]** Exécution n° 1 appartenant à `victime@example.com` :

```
ANONYME    GET /api/pm-orchestrator/execute/1/budget -> 200
  {"allowed":true,"execution_cost":12.34,"project_cost":12.34,
   "remaining_execution":17.66,"remaining_project":187.66}
ATTAQUANT  GET /api/pm-orchestrator/execute/1/budget -> 200   (mêmes données)
ATTAQUANT  GET /api/pm-orchestrator/execute/1/progress -> 404  ← cloisonnement correct
ATTAQUANT  GET /api/pm-orchestrator/execute/1/result   -> 404  ← cloisonnement correct
```

**Ce qui se passe** : les identifiants d'exécution sont séquentiels. En itérant de 1 à N sans compte, on obtient le coût de chaque exécution de chaque client — donc le volume d'activité de la plateforme, le rythme de chaque compte, et l'échelle de l'affaire. C'est une fuite de renseignement commercial, pas de donnée personnelle, mais elle est intégrale.

**Correctif** : la route est appelée par le frontend (`ExecutionPage`), elle ne peut pas être démontée. Aligner sur ses voisines :

```python
def get_execution_budget(execution_id: int, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    verify_execution_access(execution_id, current_user.id, db)
```

**Effort** : 30 min.

---

### `SEC-04` — `POST /api/blog/generate-batch` : sans authentification, coût illimité, publication publique — **majeur**

**Fichier** : `backend/app/api/routes/blog.py:116-139`

**[EXÉCUTÉ]** La route figure parmi les 23 sans dépendance d'authentification (analyse de l'arbre de dépendances FastAPI sur les 171 routes montées).

**[LU]** Ce qu'elle fait : pour chaque élément de la liste `topics` fournie par l'appelant, elle lance `scripts/blog_generator.py <titre>` (`blog.py:42-55`), attend jusqu'à 300 s, puis publie le résultat sur Ghost. La liste n'est pas bornée. Aucun plafond de débit n'est posé sur ce routeur.

**Ce qui se passe** : un inconnu envoie 500 sujets, obtient 500 générations d'articles LLM facturées, publiées sur le blog public de l'entreprise avec les titres de son choix. Il n'y a ni jeton, ni quota, ni file : la requête tient la connexion pendant des heures. `GET /blog/pending-topics` et `/approved-topics` exposent en prime le calendrier éditorial.

**Correctif** : le routeur `blog` n'est appelé par aucun code du frontend (vérifié). Le plus sûr est de commenter son `include_router` (`main.py:190`) — c'est ce qui a été fait pour `deployment.py`, et c'est la bonne réponse pour une surface sans appelant. S'il est utilisé par n8n, alors : `dependencies=[Depends(get_current_user)]` au niveau du routeur, plafond `2/hour`, et `len(topics) <= 5`.

**Effort** : 1 h (démontage) — 4 h (mise sous authentification).

---

### `SEC-05` — 29 vulnérabilités connues côté Python, dont la bibliothèque qui vérifie les jetons — **majeur**

**[EXÉCUTÉ]** `pip-audit -r backend/requirements.txt` :

```
Found 29 known vulnerabilities in 9 packages
```

Les quatre qui comptent :

| Paquet | Version | Avis | Nature | Correctif |
|---|---|---|---|---|
| `python-jose` | 3.3.0 | PYSEC-2024-232 | **confusion d'algorithme** avec clés ECDSA OpenSSH — famille CVE-2022-29217 | 3.4.0 |
| `python-jose` | 3.3.0 | PYSEC-2024-233, PYSEC-2025-185 | « bombe JWT » : déni de service à la décompression | 3.4.0 / aucun |
| `starlette` | 0.27.0 | PYSEC-2026-161, -248, -249, -1941, -1943 (9 avis) | `Host`/chemin non validés avant reconstruction d'URL ; champs de formulaire sans borne mémoire | ≥ 0.47.2 puis 1.3.1 |
| `python-multipart` | 0.0.6 | 9 avis, dont PYSEC-2026-3040 | `Content-Length` négatif → lecture jusqu'à EOF ; DoS par expression régulière sur `Content-Type` | 0.0.31 |

`python-jose` est la bibliothèque qui **valide les JWT de la plateforme** (`app/utils/auth.py:6`). `python-multipart` sert la route d'envoi de documents. `starlette` sert tout.

**Correctif** : `python-jose[cryptography]==3.4.0` et `python-multipart==0.0.31` sont des montées mineures, sans rupture d'API attendue. `starlette` est contraint par `fastapi==0.104.1` : monter FastAPI à ≥ 0.115 (ce qui lève aussi le plafond `httpx<0.28` de `requirements-test.txt`, posé pour le `TestClient` de starlette 0.27) est un chantier de 1 à 2 jours, à programmer en vague 2.

**Effort** : 2 h (jose + multipart) ; 12 h (FastAPI/starlette + reprise du `TestClient`).

---

### `SEC-06` — 26 vulnérabilités côté frontend, dont XSS, avec le jeton en `localStorage` — **majeur**

**[EXÉCUTÉ]** `npm audit --package-lock-only` : `{low: 1, moderate: 11, high: 14, total: 26}`. Notamment `react-router` — *XSS via Open Redirects* — et `postcss` — *XSS via Unescaped `</style>`*.

**[EXÉCUTÉ]** `frontend/src/components/ProtectedRoute.tsx:8` : `localStorage.getItem('token')`.

**Ce qui se passe** : un XSS donne accès au `localStorage`, donc au jeton. Ce jeton vaut **24 h** (`config.py:26`, `ACCESS_TOKEN_EXPIRE_MINUTES = 1440` — le gabarit `.env.example:20` dit 30, autre incohérence) et **ne peut pas être révoqué** : aucune liste noire, aucun `jti` vérifié, aucune route de déconnexion côté serveur (recherche `logout|revoke|blacklist|jti` : seuls une constante de journal d'audit et un commentaire « if we add a blocklist later »). Le vol d'un jeton est donc définitif jusqu'à expiration.

Même canal : le flux SSE accepte le jeton en paramètre d'URL (`execution_routes.py:304-310`, le commentaire le reconnaît explicitement) — il atterrit dans les journaux d'accès nginx.

**Correctif** : `npm audit fix` d'abord (la majorité se règle sans rupture) ; puis, par ordre de gain, ramener `ACCESS_TOKEN_EXPIRE_MINUTES` à 60 avec un jeton de rafraîchissement, ou à défaut poser une liste de révocation en Redis indexée par `jti`.

**Effort** : 3 h (`npm audit fix` + non-régression) ; 12 h (cycle de vie des jetons).

---

### `SEC-07` — l'audit attribue les lignes au mauvais appelant sous concurrence — **majeur**

**Fichier** : `backend/app/services/audit_service.py:62-82` et `543` ; `backend/app/middleware/audit_middleware.py:115-148`

```python
class AuditService:
    """… Thread-safe design for synchronous operations."""      # l. 56-59
    def __init__(self):
        self._request_context: Dict[str, Any] = {}              # état partagé
...
audit_service = AuditService()                                   # singleton de module
```

**[EXÉCUTÉ]** 40 requêtes concurrentes, chacune avec un `User-Agent` qui la nomme :

```
lignes d'audit écrites : 40
user-agents distincts  : 13   (attendu : 40)
user-agents attribués à plusieurs lignes : {'AGENT-20': 17, None: 10, 'AGENT-34': 3}
```

**Ce qui se passe** : le middleware appelle `set_request_context(...)` puis `await asyncio.to_thread(audit_service.log, ...)`. Le `await` rend la main ; une autre requête écrase le contexte du singleton avant que le fil de la première ne le lise. **17 lignes sur 40 portent l'identité d'une requête qui n'est pas la leur.** Un journal d'audit qui ment est pire qu'un journal absent : il fait conclure à tort. Et `audit_logs` est un argument de vente du palier Enterprise (`models/subscription.py`, `"audit_logs"`).

La correction de la vague 2 qui a sorti l'écriture de la boucle d'événements (commentaire l. 121-129, correcte et utile) a rendu cette course **plus** probable, pas moins.

**Correctif** : le mécanisme existe déjà dans le dépôt — `app/middleware/execution_context.py` utilise des `contextvars`, qui sont précisément conçues pour cela.

```python
from contextvars import ContextVar
_request_context: ContextVar[dict] = ContextVar("audit_request_context", default={})

class AuditService:
    def set_request_context(self, **kw): _request_context.set({...})
    def _ctx(self): return _request_context.get()
```
Une `contextvar` est copiée dans le contexte du fil par `asyncio.to_thread` : la valeur suit la requête.

**Test rouge d'abord** : le script d'annexe rend 13 user-agents distincts ; il doit en rendre 40.

**Effort** : 3 h.

---

### `SEC-08` — deux routes authentifiées sans contrôle de propriété — **mineur**

**[EXÉCUTÉ]** `GET /api/pm-orchestrator/executions/{execution_id}/agents` (`hitl_routes.py:627`) rend `200` à un utilisateur qui n'est pas propriétaire de l'exécution : il apprend qu'elle existe et quels agents y ont produit des livrables.

**[EXÉCUTÉ]** `GET /api/pm-orchestrator/workers/health` (`execution_routes.py:566`) rend `200` en anonyme : `{"redis":"connected","redis_version":"7.0.15","queued_jobs":0}` — version d'un composant d'infrastructure et profondeur de file.

**Correctif** : `verify_execution_access(execution_id, current_user.id, db)` sur la première ; `Depends(get_current_user)` sur la seconde.

**Effort** : 30 min.

---

### `SEC-09` — le webhook Journal : secret en paramètre d'URL, comparaison non constante, environnement complet transmis — **mineur**

**Fichier** : `backend/app/api/routes/journal_webhook.py:44-50` et `33-40`

**[LU]** `secret != WEBHOOK_SECRET` : comparaison non constante en temps (attaque temporelle, difficile à exploiter sur HTTP mais gratuite à corriger). Le secret circule en `?secret=` : il finit dans les journaux d'accès nginx et dans le `Referer`. Enfin `env={**os.environ}` (l. 37) transmet **toutes** les clés API du processus au sous-processus de construction.

**Correctif** : `hmac.compare_digest(secret, WEBHOOK_SECRET)` ; accepter le secret en en-tête (`X-Journal-Secret`) ; restreindre l'environnement transmis à ce dont `build.py` a besoin.

**Effort** : 1 h.

---

### Cherché et non trouvé (axe 3) — ce qui tient

Ces classes de défaut ont été cherchées méthodiquement et **n'existent pas** dans le code applicatif. C'est du travail déjà fait, à ne pas refaire.

- **Injection SQL** : aucune. Un seul SQL construit par f-string (`phased_build_executor.py:805`) ; la partie interpolée ne contient que des **noms de paramètres liés** générés à partir d'une liste statique (`PHASE_TASK_KEYWORDS`), jamais de donnée utilisateur. [EXÉCUTÉ — `grep -rnE "text\(\s*f[\"']|execute\(\s*f[\"']"`]
- **Injection de commande** : aucun `shell=True` dans `backend/app` ni `backend/agents`. Tous les sous-processus passent une liste d'arguments. `os.system` et `os.popen` : zéro occurrence. La route `GET /agent-tester/org/query`, décrite comme la faille la plus grave de l'audit d'origine, porte aujourd'hui trois verrous indépendants (authentification au niveau du routeur `agent_tester.py:41-45`, `shell=False`, validation SOQL en lecture seule `_validate_soql`) — chacun suffirait seul. [EXÉCUTÉ]
- **Désérialisation non sûre** : aucun `eval`, `exec`, `pickle.load`, ni `yaml.load` non sûr. Tous les YAML passent par `yaml.safe_load`. [EXÉCUTÉ]
- **Traversée de répertoire** : les trois sites historiques sont fermés — `_safe_log_id` (`agent_tester.py:219-232`), `Path(...).name` sur les envois de fichiers (`documents.py:133`), et la route `GET /download/{filename}` supprimée (`main.py:396-401`). Le test `test_directory_traversal_is_not_served` échoue dans mon environnement pour une raison indépendante (la route n'existe plus, le test attend un code précis) ; le code, lui, est sain.
- **Secrets dans le frontend** : aucun. Recherche de motifs `sk-`, `pk_live`, `api_key = "…"` sur `frontend/src` : rien.
- **Cloisonnement des routes principales** : correct. `verify_execution_access` (`_helpers.py:37-57`), `_load_artifact_for_user` (`hitl_routes.py:398-420`) et `_get_project_or_404` (`documents.py`) vérifient tous la chaîne `ressource → exécution → projet → utilisateur`. Vérifié en croisé : `progress` et `result` rendent bien 404 à un tiers. [EXÉCUTÉ]
- **Webhook Stripe** : correctement fait. Refus net en 503 si `STRIPE_WEBHOOK_SECRET` manque, vérification de signature, 500 délibéré pour déclencher la reprise Stripe (`billing.py`). [LU]
- **Concierge public** : correctement fait. Budget quotidien en base (`sophie_concierge_service.py:133-146`) vérifié hors boucle d'événements, et refus **net** du tour si `CHAT_IP_SALT` est absent plutôt qu'un hachage à sel vide (l. 76-82). C'est le contre-exemple à imiter.

---

# 4. Cohérence des paliers

Testé en exécutant de vraies requêtes HTTP, avec trois comptes de paliers différents.

### Ce qui tient — **la frontière payante est appliquée côté serveur**

**[EXÉCUTÉ]**

```
== lancement SDS (payant à partir de Pro) ==
   free  POST /api/pm-orchestrator/execute -> 403 {"feature":"sds_document","required_tier":"pro"}
   pro   POST /api/pm-orchestrator/execute -> 202
   team  POST /api/pm-orchestrator/execute -> 202

== lancement BUILD (réservé Team) ==
   free  POST /projects/{id}/start-build -> 403 {"feature":"build_phase","required_tier":"team"}
   pro   POST /projects/{id}/start-build -> 403 {"feature":"build_phase","required_tier":"team"}
   team  POST /projects/{id}/start-build -> 400 "Project must be in SDS_APPROVED status"
```

Le palier Pro **ne peut pas** déclencher la construction ; le palier gratuit **ne peut pas** produire de SDS. Le décorateur `require_feature` (`app/utils/feature_access.py:100-131`) échoue fermé si `current_user` manque, et `resolve_tier` traite une valeur inconnue comme `free` — la bonne polarité. Les deux exigences explicites du cahier des charges sont donc satisfaites, et vérifiées.

Une réserve de forme : `retry_routes.py:55` applique `ensure_feature(current_user, "build_phase")` **conditionnellement**, seulement s'il existe des `TaskExecution` en échec. Le raisonnement est écrit et correct (ne pas priver un compte rétrogradé Team→Pro de son retry SDS), mais il repose sur la propriété « les `TaskExecution` ne sont créées que par le BUILD » : à documenter comme invariant, sinon la garde se dissout au premier autre producteur de lignes.

---

### `TIER-01` — le palier gratuit crée des projets alors que son quota est zéro — **majeur**

**Fichier** : `backend/app/api/routes/orchestrator/project_routes.py` (`create_project`) ; `backend/app/models/subscription.py:79` (`"max_projects": 0` pour FREE)

**[EXÉCUTÉ]**

```
   free  POST /api/pm-orchestrator/projects -> 201 {"name":"nouveau-free",…}
   pro   POST /api/pm-orchestrator/projects -> 201
   team  POST /api/pm-orchestrator/projects -> 201
```

**[EXÉCUTÉ]** La fonction qui appliquerait la limite existe (`feature_access.py:157-199`, `check_project_limits`) et n'est appelée que par deux routes **de consultation** (`subscription.py:63` et `96`) — jamais par la route qui crée. Idem pour `check_br_limit` et `check_uc_limit` : zéro appelant.

**Ce qui se passe** : un compte gratuit crée autant de projets qu'il veut, puis dialogue avec Sophie sur chacun (`POST /projects/{id}/chat` → 200, vérifié). Chaque tour est un appel LLM facturé, sans débit de crédits (`FIN-01`) et sans plafond quotidien — alors que le concierge **anonyme**, lui, en a un. L'utilisateur identifié est moins encadré que le visiteur anonyme.

`check_project_limits` est par ailleurs faux tel qu'écrit : il compte `len(user.projects)` (l. 183) au lieu d'une requête `COUNT`, ce qui charge toute la collection.

**Correctif** :

```python
# project_routes.py, en tête de create_project
n = db.query(func.count(Project.id)).filter(Project.user_id == current_user.id).scalar()
limit = get_limit(resolve_tier(current_user), "max_projects")
if limit is not None and n >= limit:
    raise LimitExceededError("max_projects", n, limit, resolve_tier(current_user))
```

**Effort** : 3 h (les trois limites + tests rouges d'abord).

---

### `FIN-01` — le compteur de crédits n'est jamais appelé — **bloquant**

**Fichier** : `backend/app/services/llm_router_service.py:826-827` et `871-872` ; `backend/app/services/llm_service.py:248` et `317`

```python
def _credit_preflight(self, request, provider_str):
    if request.user_id is None:
        return None                 # ← pas de contrôle
def _credit_post_charge(self, request, response):
    if request.user_id is None:
        return                      # ← pas de débit
```

**[EXÉCUTÉ]** Appel LLM émis exactement comme le fait `salesforce_business_analyst.py:450` (avec `execution_id`, sans `user_id`), fournisseur remplacé par un double, `CreditService` instrumenté :

```
user_id=1 tier=free project_id=1 execution_id=1
réponse success = True
LLMRequest.user_id vu par le provider : None
CreditService.preflight appelé : 0 fois
CreditService.charge    appelé : 0 fois
ligne CreditBalance en base : None
```

**[EXÉCUTÉ]** Cause : `grep` sur `app/` et `agents/` — **aucun appelant ne passe `user_id=`** à la couche LLM. `llm_service` résout automatiquement `subscription_tier` depuis `execution_id` (l. 224-228), mais pas `user_id` : le champ existe, il est transporté (`llm_router_service.py:1004` et `1030`), et personne ne le remplit.

**Ce qui se passe** : tout le dispositif de crédits est inerte. Concrètement :
- aucun contrôle d'autorisation de modèle avant appel ;
- aucun débit après appel : `GET /api/billing/balance` et `/usage` affichent des chiffres qui ne bougent jamais ;
- **le plafond commercial du palier Pro n'existe pas**. Il est pourtant défini, chiffré et migré : `tier_config` seed 2 000 crédits/mois pour Pro (`alembic/versions/008:229`).

**[EXÉCUTÉ]** Ce que ce plafond vaut, avec les tarifs de crédits réellement seedés :

```
coût d'un appel Sonnet type (4 900 entrée / 2 100 sortie) : 15,4 crédits
un SDS de 43 appels                                        : 662 crédits
quota mensuel Pro = 2 000 crédits                          : 3,02 SDS par mois
```

Le modèle économique prévoit **3 SDS par mois** pour 49 €. À l'exécution, le seul plafond restant est `DEFAULT_EXECUTION_LIMIT_USD = 30.0` par exécution (`budget_service.py:108`) et le plafond de débit `10/hour`, lui-même contournable (`SEC-02`). L'écart entre le plafond conçu et le plafond appliqué est de trois ordres de grandeur.

**Attention — le correctif n'est pas « passer `user_id` ».** [EXÉCUTÉ] Si le pré-vol était simplement branché, il refuserait les appels Opus que `llm_routing.yaml` prescrit délibérément pour Marcus en palier Pro :

```
preflight(pro, 'claude-opus-4-6')     -> REFUS : Model 'claude-opus-4-7' not allowed for tier 'pro'
preflight(pro, 'anthropic/claude-opus') -> REFUS : idem
preflight(pro, 'claude-sonnet-4-5-…') -> AUTORISÉ
```

`model_pricing.allowed_tiers` (migration 008) dit `opus → team` uniquement ; `llm_routing.yaml:tier_overrides.pro.agents_keep_orchestrator` garde Marcus en Opus pour Pro, avec une justification commerciale écrite (« 56 % du coût SDS, le SaaS Pro 49 € doit garder Opus ici »). Les deux tables se contredisent. Brancher le pré-vol sans les réconcilier **casserait le palier Pro sur chaque SDS**, à la phase Marcus.

**Correctif**, dans cet ordre strict :
1. réconcilier `model_pricing.allowed_tiers` et `llm_routing.yaml` — décision commerciale, pas technique : soit Opus passe `allowed_tiers="pro,team"`, soit Marcus repasse en Sonnet pour Pro ;
2. propager `user_id` : dans `llm_service.generate_llm_response`, le résoudre depuis `execution_id` **comme le tier l'est déjà** — la requête existe (`_resolve_tier_for_execution`, l. 31-64), il suffit de rendre aussi `project.user_id` ;
3. **puis seulement** activer, avec un test rouge d'abord : un compte Pro à 2 000 crédits consommés doit recevoir `insufficient_credits`.

Et corriger le repli silencieux de `_credit_post_charge` (l. 892-897) : un débit qui échoue est aujourd'hui journalisé et oublié. Il doit alimenter une file de reprise, sinon toute indisponibilité de la base est du chiffre d'affaires perdu sans trace.

**Effort** : 2 h (arbitrage tarifaire) + 6 h (propagation et tests) + 4 h (file de reprise du débit).

---

### `FIN-02` — les plafonds budgétaires sont globaux, pas indexés sur le palier — **majeur**

**Fichier** : `backend/app/services/budget_service.py:108-110`

```python
DEFAULT_EXECUTION_LIMIT_USD = 30.0    # « mod37 : abaissé pour le test 4-projets »
DEFAULT_PROJECT_LIMIT_USD  = 200.0
DEFAULT_MONTHLY_LIMIT_USD  = 500.0    # ← une seule occurrence dans tout le dépôt : constante morte
```

**[EXÉCUTÉ]** `grep -rn DEFAULT_MONTHLY_LIMIT_USD app/` : une occurrence, sa définition. Le plafond mensuel n'est appliqué nulle part.

**[LU]** `check_budget` (l. 171-206) applique les deux autres **à tous les paliers indistinctement**, et le commentaire de la première dit qu'elle a été baissée pour un essai — une valeur d'essai figée dans le code de production.

**Ce qui se passe** : un compte Pro à 49 €/mois dispose de 200 $ d'inférence par projet, et le modèle prévoit 20 projets (`subscription.py:130`). Le plafond structurel est donc de **4 000 $ par mois pour 49 €**. En restant même dans le débit autorisé de 10 SDS/heure, un seul compte Pro peut consommer, sur un mois, plusieurs milliers de dollars.

**Correctif** : lire les plafonds depuis `tier_config` comme le fait `CreditService`, et arrêter d'avoir deux systèmes de plafonnement (voir `DETTE-03`).

```python
def _limits_for(self, execution_id):
    tier = resolve_credit_tier(self._user_of(execution_id))
    return TIER_BUDGETS[tier]      # {"execution": …, "project": …, "monthly": …}
```
Passer aussi `estimated_cost` réel à `check_budget` : appelé avec le défaut `0.0` (`llm_service.py:233`), il contrôle « déjà dépassé » et non « sur le point de dépasser », donc un appel peut franchir le plafond avant d'être vu.

**Effort** : 6 h.

---

### `FIN-03` — pas d'idempotence sur les webhooks Stripe — **majeur (conditionnel)**

**Fichier** : `backend/app/services/stripe_service.py:212-235` et `302-356`

**[LU]** `handle_webhook_event` n'enregistre pas `event["id"]` et ne vérifie aucun traitement antérieur. Stripe **re-livre** les événements (reprise sur 5xx, doublons réseau). `_handle_invoice_paid` appelle `reset_monthly` (`credit_service.py:314-345`), qui remet `used_credits` à 0 et recharge le quota.

**Ce qui se passe** : aujourd'hui, rien — puisque rien n'est débité (`FIN-01`). **Le jour où `FIN-01` est corrigé**, chaque re-livraison d'un `invoice.payment_succeeded` offre un quota mensuel supplémentaire. Le défaut est donc dormant et se réveille exactement au moment du correctif : à traiter dans le même lot.

**Correctif** : table `stripe_events(event_id primary key, processed_at)`, insertion en tête de `handle_webhook_event`, sortie immédiate sur conflit.

**Effort** : 3 h.

---

### `TIER-02` — le tarif du palier professionnel diffère de l'énoncé — **à arbitrer**

**[EXÉCUTÉ]** Le code et les migrations disent **49 €** : `models/subscription.py:99-100` (`"price": 49`), `alembic/versions/008:231` (`price_eur_monthly: 49.00`), `alembic/versions/009:14`. L'énoncé de la mission d'audit annonce **79 €/mois**.

Je ne peux pas trancher : c'est un arbitrage commercial, pas un défaut. Mais un chiffre est faux quelque part, et si c'est 79 € qui doit s'appliquer, il faut une migration `tier_config` **et** un recalcul de `monthly_credits`. Signalé pour que la décision soit prise, pas devinée.

---

# 5. Passage à l'échelle

## Le code peut-il monter en charge ? Non — pas au-delà d'une seule machine, et pour une raison structurelle.

Le blocage n'est pas la performance. C'est que **le système est conçu pour tourner en un seul exemplaire de chaque processus**, et que trois mécanismes le verrouillent dans cet état.

---

### `SCALE-01` — le worker ARQ tue les exécutions en cours au démarrage : impossible d'en lancer deux — **bloquant pour toute montée en charge**

**Fichier** : `backend/app/workers/worker.py:13-48`

```python
async def startup(ctx):
    queued = await redis.queued_jobs()
    for job in queued:
        await job.abort()                                    # l. 22-23 : purge la file
    stuck = db.query(Execution).filter(
        Execution.status == ExecutionStatus.RUNNING).all()
    for exec in stuck:
        exec.status = ExecutionStatus.FAILED                 # l. 37-40 : tue les exécutions
    db.commit()
```

**[LU]** Le raisonnement est juste pour un worker unique qui redémarre après plantage. Il est catastrophique dès qu'il y en a deux : **le démarrage du worker n° 2 annule toute la file et marque `FAILED` toutes les exécutions que le worker n° 1 est en train de mener.** Un client verrait son SDS mourir à mi-course parce qu'on a ajouté de la capacité.

C'est le plafond dur de la plateforme aujourd'hui : `max_jobs = 10` (l. 62), un processus, `job_timeout = 3600`. Soit **10 exécutions simultanées, point final**, et aucun moyen d'en ajouter sans réécrire ce démarrage.

**Correctif** : n'annuler que ce qui appartient à l'instance disparue.
1. poser un bail : chaque exécution `RUNNING` porte `worker_id` + `heartbeat_at`, rafraîchi toutes les 30 s par le worker qui la tient ;
2. au démarrage, ne marquer `FAILED` que les exécutions dont le battement a plus de 3 minutes ;
3. supprimer la purge de file (`job.abort()` sur la file entière) : la garde anti-fantôme existe déjà à l'entrée de chaque tâche (`tasks.py:19-22`) et elle est, elle, correcte.

**Effort** : 12 h (dont une migration pour les deux colonnes).

---

### `SCALE-02` — Redis est câblé sur `localhost` sans possibilité de configuration — **bloquant pour toute montée en charge**

**Fichier** : `backend/app/workers/arq_config.py:5-9`

```python
REDIS_SETTINGS = RedisSettings(host='localhost', port=6379, database=1)
```

**[EXÉCUTÉ]** Aucune variable d'environnement n'est lue pour Redis dans tout `app/` (`grep -rn "REDIS" app/ | grep -v REDIS_SETTINGS` : vide). Ni hôte, ni port, ni mot de passe, ni TLS.

**Ce qui se passe** : la file ne peut pas quitter la machine. Donc l'API ne peut pas quitter la machine du worker. Donc il n'y a qu'une machine. C'est une ligne de code, mais c'est ce qui fait qu'il n'y a pas d'architecture à deux nœuds.

**Correctif** :

```python
REDIS_SETTINGS = RedisSettings(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    database=int(os.environ.get("REDIS_DB", 1)),
    password=os.environ.get("REDIS_PASSWORD") or None,
)
```
et les quatre variables dans `.env.example`.

**Effort** : 1 h.

---

### `SCALE-03` — le plafond de débit est en mémoire de processus — **majeur**

**Fichier** : `backend/app/rate_limiter.py:24-29`

**[EXÉCUTÉ]** Aucun `storage_uri` n'est passé au `Limiter` de slowapi : le stockage par défaut est un dictionnaire en mémoire. Conséquences : les compteurs sont **multipliés par le nombre de workers uvicorn**, et remis à zéro à chaque redémarrage. Comme la production tourne aujourd'hui en `--reload` (donc un seul worker), le défaut est masqué — il apparaît au premier `--workers 4`, c'est-à-dire au premier geste de mise à l'échelle.

**Correctif** : `Limiter(..., storage_uri=f"redis://{REDIS_HOST}:{REDIS_PORT}/2")`. À faire dans le même lot que `SEC-02`, sans quoi le plafond reste contournable de toute façon.

**Effort** : 2 h.

---

### `SCALE-04` — livrables et espace de travail SFDX sur système de fichiers local — **majeur**

**Fichier** : `backend/app/config.py:105-134` ; `docker-compose.prod.yml:20-26`

**[LU]** `OUTPUT_DIR`, `DELIVERABLES_DIR`, `SFDX_PROJECT_PATH`, `FORCE_APP_PATH` sont des chemins locaux. Les SDS générés (`pm_orchestrator_service_v2.py:2594`, `document_generator.py:434`) et les archives (`sf_admin_service.py:190`) y sont écrits, et servis depuis là.

**Ce qui se passe** : deux instances d'API ne voient pas les mêmes fichiers. Le téléchargement d'un SDS échoue une fois sur deux dès qu'il y a deux nœuds. Il n'y a pas de contournement par équilibrage de charge : il faut un stockage objet.

Plus grave, la production monte `/root/.sf` et `/root/.sfdx` **partagés** (`docker-compose.prod.yml:24-25`) : le magasin d'authentification Salesforce est un répertoire unique pour tous les clients, écrit par le CLI `sf` sans verrou. Deux déploiements concurrents vers deux orgs clientes différentes écrivent dans le même magasin.

**Correctif** : livrables et SDS en stockage objet compatible S3 (`boto3`, URL signée pour le téléchargement) ; espace SFDX **par exécution**, dans un répertoire temporaire dédié, avec `SF_DATA_DIR` positionné par appel plutôt qu'un `/root/.sf` global.

**Effort** : 24 h (stockage objet) + 12 h (isolation SFDX). À faire avant 100 clients, pas avant 10.

---

### `SCALE-05` — ChromaDB en client intégré, dans le processus — **majeur au-delà de 100**

**Fichier** : `backend/app/services/rag_service.py:84-101` (`_client` singleton, `PersistentClient`)

**[LU]** ChromaDB est utilisé en mode intégré, adossé à un SQLite sur disque. Un seul écrivain, aucun partage réseau, aucun réplica. Les agents l'interrogent depuis des fils (`asyncio.to_thread`), donc en concurrence, sur le même handle. À un nœud c'est tenable ; à deux, le store doit être soit dupliqué (et il faut alors gérer la cohérence des envois clients), soit servi.

Voir aussi `RAG-01` : le mécanisme d'isolation par métadonnée ne passera pas non plus à l'échelle multi-tenant.

**Correctif** : Chroma en mode serveur (`chromadb.HttpClient`) dès le passage à deux nœuds ; envisager `pgvector` à 1 000 clients, ce qui supprimerait un composant d'infrastructure entier et mettrait le vecteur dans la transaction qui porte déjà le document.

**Effort** : 8 h (mode serveur) ; 40 h (migration pgvector).

---

### `SCALE-06` — une écriture d'audit et une transaction supplémentaires sur chaque requête — **mineur**

**Fichier** : `backend/app/middleware/audit_middleware.py:130-148`

**[LU]** Chaque requête non exclue déclenche un `INSERT` + `COMMIT` dans `audit_logs`, exécuté dans un fil (bonne chose, `PERF-01` réglé ici) mais **attendu avant que la réponse ne parte** — l'`await` est dans le `finally`, donc après le `return`. Chaque requête paie donc un aller-retour PostgreSQL supplémentaire et occupe une place du pool de fils (`min(32, cpu+4)` par défaut).

À cela s'ajoute le flux SSE : un instantané par client toutes les 2 à 3 s (`execution_routes.py:357`), chacun un `to_thread` + une requête. 100 clients en supervision = ~40 requêtes/s et 40 fils réclamés en permanence, pour de la lecture d'état.

**Correctif** : mettre l'écriture d'audit en file (Redis + consommateur), ou l'écrire en lot toutes les N lignes ; pour le SSE, cesser de sonder — la voie `NOTIFY` existe déjà (`notification_service`), il suffit de ne plus recharger l'instantané en base à chaque battement, seulement à chaque notification. Sans oublier de relever `anyio.to_thread` au-delà de 40 places.

**Effort** : 8 h.

---

## Dimensionnement par palier

Hypothèse d'usage retenue : un client Pro produit ~4 SDS/mois, un client Team ~4 SDS + 4 BUILD/mois. Une exécution SDS dure 20 à 60 min de temps mural, dominée par l'attente des réponses LLM.

### 10 clients — **la machine actuelle suffit**

| Élément | Dimensionnement |
|---|---|
| Machines | 1 VPS, 4 vCPU / 8 Go (l'actuel) |
| Processus | API `uvicorn --workers 2`, **1** worker ARQ (`max_jobs=10`), PostgreSQL, Redis, Chroma intégré |
| Charge | ~40 SDS/mois = 1 à 2/jour. Le worker est inoccupé 95 % du temps. |

**À refaire avant** : `DEP-01`, `DEP-02`, `MIG-01`, `SEC-01`, `SEC-02`, `FIN-01`, `CONF-01`, `CONF-02`, `RAG-01`. Ce sont des correctifs de justesse, pas de dimensionnement — mais sans eux on ne peut installer aucun client.
**Peut attendre** : tout le reste de cette section.

### 100 clients — **séparer les rôles, sortir Redis et PostgreSQL**

| Élément | Dimensionnement |
|---|---|
| Machines | 3 : API (4 vCPU/8 Go), worker (8 vCPU/16 Go), données (PostgreSQL managé, 4 vCPU/16 Go) |
| Processus | API `--workers 4` derrière nginx ; **2 workers ARQ** à `max_jobs=8` ; Redis managé ; Chroma en mode serveur sur la machine worker |
| Charge | ~400 SDS/mois ≈ 20/jour, pointe à 5 simultanées. 16 places de worker : confortable. |
| PostgreSQL | `max_connections ≥ 200` — chaque processus ouvre son propre pool de 20+20 (`database.py:11-19`) : 4 API + 2 workers = **240 connexions potentielles**. À poser explicitement, c'est le premier mur qu'on rencontre. |

**À refaire avant** : `SCALE-01` (obligatoire : sans lui, le 2ᵉ worker est destructeur), `SCALE-02`, `SCALE-03`, `SCALE-04` (stockage objet — sans lui l'API à 2 nœuds ne sert pas les livrables), `SCALE-05` (Chroma serveur), `PERF-02`, `SEC-07`.
**Peut attendre** : `SCALE-06`, `DETTE-01`.

### 1 000 clients — **découpler la voie de lecture de la voie d'exécution**

| Élément | Dimensionnement |
|---|---|
| Machines | API : 3 × (4 vCPU/8 Go) derrière un répartiteur ; workers : 6 × (8 vCPU/16 Go) ; PostgreSQL managé 8 vCPU/32 Go + 1 réplica de lecture ; Redis managé en cluster ; Chroma/pgvector 8 vCPU/32 Go |
| Charge | ~4 000 SDS + 1 000 BUILD/mois ≈ 170/jour, pointes à 40 simultanées → 48 places de worker |
| Stockage | S3 pour livrables, SDS, journaux d'agents. `audit_logs` **partitionné par mois** avec purge à 12 mois, sinon la table dépasse la centaine de millions de lignes en un an au rythme d'une écriture par requête. |
| SSE | plus de sondage : diffusion par Redis pub/sub, l'API ne touche plus la base pour la progression |

**À refaire avant** : `SCALE-06`, la partition d'`audit_logs`, la lecture d'état sur réplica, et la limitation de débit **par client** (aujourd'hui par IP — un client derrière un NAT d'entreprise partage son quota avec ses collègues, un attaquant en change à volonté).
**Peut attendre** : la refonte de `execute_workflow` — pénible, pas bloquante à ce palier.

### 10 000 clients — ce que les machines ne règlent pas

À ce volume, cinq limites sont **architecturales** et ne cèdent à aucun redimensionnement.

1. **L'exécution d'un SDS est un état en mémoire d'un processus.** `execute_workflow` fait 1 270 lignes (`pm_orchestrator_service_v2.py:488-1757`, mesuré : 61 `if`, 26 `try`, 409 appels) et porte la progression du pipeline dans ses variables locales, avec **une session SQLAlchemy ouverte pendant toute la durée du travail** (`tasks.py:15-51`, jusqu'à 3 600 s). Une exécution ne peut ni être reprise par un autre worker, ni être répartie entre plusieurs. À 10 000 clients il faut un pipeline dont chaque phase est un travail indépendant reprenant son état en base — c'est une réécriture de l'orchestrateur, 6 à 10 semaines, pas un correctif.

2. **Le RAG n'a pas de modèle multi-tenant.** Cinq collections globales, isolation par une métadonnée `project_id` sur les chunks (`rag_service.py:213`). Aucun partitionnement, aucune possibilité d'effacement ciblé par client au sens du RGPD sans balayer les collections, aucun moyen d'héberger un client dans une autre région. À ce volume il faut une collection (ou un espace de noms) par client, et un socle documentaire partagé **séparé** — ce qui règle du même coup `RAG-01`.

3. **SFDX est un processus par déploiement.** Chaque appel lance le CLI Node `sf` (30 à 60 s, ~300 Mo de mémoire résidente) et écrit dans un magasin d'authentification partagé. À 10 000 clients, c'est un service à part entière — pool de conteneurs éphémères, un magasin par exécution — ou un remplacement par l'API REST Metadata en direct.

4. **Le journal d'audit vit dans la base transactionnelle.** Une écriture par requête HTTP, sans rétention. À ce volume l'audit doit partir vers un stockage en colonnes ou en séries temporelles ; le garder dans PostgreSQL fait grossir sauvegardes et restaurations jusqu'à rendre la reprise après sinistre impraticable.

5. **Aucun cloisonnement au-delà de `user_id`.** Il n'y a pas de notion d'organisation, pas de rôles, pas de sécurité au niveau des lignes. 10 000 clients signifie des équipes, des droits, des invitations, une administration déléguée. C'est un modèle de données à ajouter, pas une option à activer.

---

## Coût d'inférence à 10 000 clients

**Point de mesure réel disponible** : un appel Olivia archivé dans le dépôt, `backend/debug_exec_87/output_ba_default_87.json` → `tokens_used = 6687`, modèle `claude-sonnet-4-5-20250929`. [EXÉCUTÉ]

**Hypothèses, explicitées pour être contestables** : ~43 appels LLM par SDS (chiffre du code lui-même, `budget_service.py:248` : « ~43 est normal pour un SDS ») ; 7 000 jetons par appel ; répartition 70 % entrée / 30 % sortie (celle que `_calculate_cost` retient, `pm_orchestrator_service_v2.py:2230`) ; tarifs de `config/llm_routing.yaml:358` (Opus 5/25 $, Sonnet 3/15 $ par million).

| | coût unitaire | composition | **coût par livrable** |
|---|---|---|---|
| appel Opus | 0,077 $ | 4 900 entrée + 2 100 sortie | |
| appel Sonnet | 0,046 $ | idem | |
| **SDS palier Pro** | | 8 Opus (Marcus) + 35 Sonnet | **≈ 2,2 $** |
| **SDS palier Team** | | 26 Opus + 17 Sonnet | **≈ 2,8 $** |
| **BUILD palier Team** | | ~120 appels Sonnet, sorties longues (`max_tokens` 32 k–64 k) | **≈ 9,5 $** — estimation la plus fragile de ce tableau |

**Projection à 10 000 clients** (8 000 Pro à 4 SDS/mois, 2 000 Team à 4 SDS + 4 BUILD/mois) :

| | volume mensuel | coût d'inférence | chiffre d'affaires | part |
|---|---|---|---|---|
| Pro | 32 000 SDS | ≈ 70 000 $ | 8 000 × 49 € ≈ 392 000 € | ~18 % |
| Team | 8 000 SDS + 8 000 BUILD | ≈ 98 000 $ | 2 000 × 1 490 € ≈ 2 980 000 € | ~3 % |
| **Total** | | **≈ 168 000 $/mois** | ≈ 3 372 000 € | **~5 %** |

**Lecture.** À l'usage nominal, l'inférence n'est **pas** le poste qui décide de la viabilité : 5 % du chiffre d'affaires, très confortable. Le palier Pro est le plus tendu (18 %) et il n'a pas de marge pour absorber un doublement du nombre d'appels par SDS.

**Ce qui décide de la viabilité, c'est l'absence de plafond, pas le coût nominal.** Avec `FIN-01` non corrigé et `SEC-02` ouvert, un seul compte Pro à 49 € peut, en respectant le débit autorisé de 10 SDS/heure, produire 7 200 SDS par mois — **≈ 16 000 $ d'inférence pour 49 € encaissés**. Trente comptes de ce type suffisent à effacer la marge de la totalité du palier Pro. C'est la raison pour laquelle `FIN-01` est classé bloquant et non majeur : ce n'est pas une question d'hygiène comptable, c'est le seul point du système où une seule personne mal intentionnée peut coûter plus cher que tous les clients ne rapportent.

**Deux réserves d'honnêteté.** Le chiffre de 43 appels vient d'un commentaire, pas d'une mesure ; le coût du BUILD est une extrapolation que rien dans le dépôt ne corrobore ; et `CLAUDE.md` annonce « 0,11 $/exécution », soit vingt fois moins que mon estimation. **Aucun de ces trois chiffres n'est vérifiable en l'état** — il n'existe dans le dépôt aucune mesure de coût réel par exécution. C'est en soi un constat : la donnée qui décide du modèle économique n'est pas instrumentée. Une requête `SELECT avg(total_cost), count(*) FROM executions WHERE status='COMPLETED'` sur la base de production trancherait en dix secondes, et devrait devenir une métrique permanente.

---

# 6. Ce qui manque pour être exploitable

---

### `OPS-01` — le test de fumée obligatoire échoue par construction sur une production correcte — **majeur**

**Fichier** : `scripts/smoke_test.sh` (26 lignes) ; `.claude/CLAUDE.md` règle 4 : « Smoke test après chaque merge »

**[EXÉCUTÉ]** Ce que le script attend, confronté à une configuration de production (`DEBUG=False`) :

```
FAIL  Health     /health                              attendu 200, obtenu 503
FAIL  API Docs   /docs                                attendu 200, obtenu 404
FAIL  Projects   /api/pm-orchestrator/projects        attendu 200, obtenu 401
FAIL  Dashboard  /api/pm-orchestrator/dashboard/stats attendu 200, obtenu 401
```

**Ce qui se passe** : trois de ces quatre échecs sont **structurels**.
- `/docs` attendu à 200 : la correction du 23/08 (`main.py:89-91`) ferme la documentation d'API en production. **Le test de fumée récompense donc la configuration non sécurisée** et échoue sur la configuration sûre.
- `/projects` et `/dashboard/stats` sont des routes authentifiées, appelées sans jeton : 401 est le comportement correct.
- (`/health` à 503 est légitime ici : mon ChromaDB local est vide.)

Un garde-fou qui affiche « ❌ FAIL » quand tout va bien est un garde-fou qu'on cesse de lire au bout d'une semaine. C'est le pire état possible : il donne l'illusion d'un contrôle.

**Correctif** : attendre 404 sur `/docs` (et vérifier que ce **n'est pas** 200 — c'est le test de sécurité qui manque), attendre 401 sur les routes authentifiées, et ajouter un parcours authentifié réel : créer un compte de service, se connecter, lister ses projets, vérifier 200.

**Effort** : 3 h.

---

### `OPS-02` — aucune intégration continue, 11 tests en échec — **majeur**

**[EXÉCUTÉ]** `ls .github/workflows` → inexistant. Ni `.gitlab-ci.yml`, ni `Jenkinsfile`, ni `.circleci`. Aucun hook git installé.

**[EXÉCUTÉ]** Référence mesurée : `11 failed, 591 passed, 1 skipped, 7 xfailed` en 369 s.

Analyse des 11, faite une par une :

| Test | Cause | Verdict |
|---|---|---|
| `test_credit_service` ×4 | attendent `premium → pro` ; `_TIER_ALIAS` dit `premium → team` (`credit_service.py:94`, avec justification écrite) | **tests périmés**, code délibéré |
| `test_auth::test_get_current_user_no_token` | attend 403, obtient 401 | **test périmé** |
| `test_auth::test_login_success`, `test_get_current_user_success` | 401 après inscription | à instruire — possible changement de parcours d'inscription non répercuté |
| `test_lot_g::test_directory_traversal_is_not_served` | la route auditée a été supprimée | **test périmé** |
| `test_vague2_lot3_observabilite` ×3 | attendent l'ancienne forme de l'audit SSE | à instruire |
| `test_wbs_task_types`, `test_wizard_phase5::test_database_*` | dépassement de délai : chemins `/root/workspace/...` en dur | **environnement** |
| `test_vague2_lot1::test_dependances_lourdes` | `chromadb`/`docx` absents de mon environnement | **environnement** |

**Ce qui se passe** : la majorité de ces échecs sont des tests devenus faux après un correctif — c'est normal. Ce qui ne l'est pas, c'est que **personne ne le sait**, faute de mécanisme qui le dise. Une suite rouge en permanence ne distingue plus une régression d'un bruit connu. C'est exactement le motif « déclaré fait sans l'être » que les trois vagues cherchaient à éliminer : tant que rien ne contredit automatiquement un « c'est corrigé », la charge de la preuve reste humaine.

**Correctif** : un `.github/workflows/ci.yml` minimal — services PostgreSQL et Redis, `pip install -r requirements-test.txt` (après `DEP-01`), `pytest`, `pip-audit`, `ruff` (la configuration existe déjà : `ruff.toml`). Puis, dans le même lot, remettre les 11 tests au vert ou les supprimer explicitement. Une suite verte est la condition pour que tout le reste de ce rapport soit vérifiable.

**Effort** : 8 h (chaîne) + 8 h (remise au vert).

---

### `OPS-03` — 36 transitions d'état avalées : la machine à états est indicative — **majeur**

**Fichier** : `backend/app/services/pm_orchestrator_service_v2.py` — 35 occurrences du motif, dont `762-767`, `803-810`

```python
try:
    sm.transition_to("sds_phase3_running")
except Exception:
    pass
try:
    sm.transition_to("sds_phase3_complete")
except Exception:
    pass
```

**[EXÉCUTÉ]** 36 blocs `except` couvrant un `transition_to` dans `app/`.

**Ce qui se passe** : la machine à 24 états, présentée comme l'acquis de l'horizon 2, **n'a aucune autorité**. Une transition illégale ne signale rien et le pipeline continue. Donc l'état enregistré peut diverger de l'état réel, et c'est précisément sur cet état que reposent la reprise, l'affichage de progression et le diagnostic. Une exécution bloquée ne se distingue pas d'une exécution qui progresse.

C'est le même motif que celui documenté dans la discipline de preuve : *un dispositif déclaré mais inopérant doit s'arrêter et le dire*.

**Correctif** : distinguer les deux cas. Une transition idempotente attendue (rejouer `phase2_running` lors d'une reprise) mérite une méthode explicite `transition_to_or_stay(...)` qui journalise en `DEBUG`. Une transition inattendue doit journaliser en `WARNING` avec l'état de départ, l'état visé et l'`execution_id`, et incrémenter un compteur. Aucune ne doit rester un `pass` muet.

**Effort** : 6 h.

---

### `OPS-04` — la configuration nginx n'est pas dans le dépôt — **majeur**

**[EXÉCUTÉ]** `find . -name "*.conf" -o -name "nginx*"` : aucun résultat.

**Ce qui se passe** : nginx sert de frontal (les commentaires du code s'y réfèrent : « la règle nginx qui bloque cette route en 403 sur le VPS reste en place », `agent_tester.py:25-26`). Il porte donc des règles de sécurité **actives** qui n'existent nulle part ailleurs. Elles ne sont ni versionnées, ni relues, ni reproductibles : une réinstallation du serveur les perd silencieusement, et un audit ne peut pas les vérifier — je n'ai pas pu.

C'est aussi ce qui empêche de conclure sur `SEC-02` : la correction complète dépend de la directive `proxy_set_header X-Forwarded-For` en vigueur, que je n'ai pas pu lire.

**Correctif** : verser la configuration nginx dans `deploy/nginx/` et la déployer depuis là.

**Effort** : 3 h.

---

### `OBS-01` — aucune métrique, aucune sonde d'exécution — **majeur**

**[LU]** Ce qui existe et qui est bon : journalisation JSON structurée avec `execution_id`/`agent_id`/`request_id` par variables de contexte (`app/logging_config.py`, P5 tenu) ; sonde `/health` qui interroge réellement PostgreSQL, Redis et ChromaDB et rend 503 si l'un tombe (`main.py:337-385`) ; sonde RAG au démarrage (`main.py:244-249`, P11 tenu).

Ce qui manque, et qui rend une panne invisible :
- **aucune métrique exportée** — pas de `/metrics`, pas de compteur Prometheus. Impossible de savoir combien d'exécutions sont en cours, depuis combien de temps, ni combien ont échoué la dernière heure ;
- **aucune sonde de fraîcheur des exécutions** : une exécution figée par `TIME-01`/`TIME-02` reste `RUNNING` indéfiniment sans alerte ;
- **aucune sonde du worker** : `/api/pm-orchestrator/workers/health` (l. 566) regarde Redis, pas le worker. Un worker mort avec un Redis vivant rend `200`.

**Correctif** : `prometheus-fastapi-instrumentator` pour la base, puis quatre jauges qui valent tout le reste — exécutions par état, âge de la plus ancienne exécution `RUNNING`, profondeur de la file ARQ, coût cumulé du jour. Et une alerte sur « âge de la plus ancienne `RUNNING` > 2 h ».

**Effort** : 8 h.

---

### `OBS-02` — `echo=settings.DEBUG` : tout le SQL, avec ses paramètres, dans les journaux — **majeur**

**Fichier** : `backend/app/database.py:18`

```python
engine = create_engine(settings.DATABASE_URL, ..., echo=settings.DEBUG)
```

**[EXÉCUTÉ]** `DEBUG` vaut `True` par défaut (`config.py:31`) et `.env.example:57` propose `DEBUG=True`. En exécutant mes bancs d'essai sans `DEBUG=False`, j'ai obtenu dans la sortie standard, entre autres :

```
INSERT INTO users (email, hashed_password, name, ...) VALUES (...)
[parameters: {'email': 'proof@example.test',
              'hashed_password': '$2b$12$5v6Pt4N2NA0pMJzlRzCZhOCd6EnCda...', ...}]
```

**Ce qui se passe** : sur un déploiement où `DEBUG` n'est pas explicitement posé à `False`, **chaque requête SQL et chacun de ses paramètres partent dans les journaux** : adresses e-mail, empreintes de mots de passe, valeurs chiffrées de credentials, contenus de briefs clients. Volume ingérable, et fuite de données par les journaux.

Ce n'est qu'une des conséquences de `DEBUG=True` par défaut. Les autres sont déjà signalées par le code lui-même : `/docs` ouvert (`main.py:89-91`), garde-fou de chiffrement inerte (`main.py:68-76`, qui crie correctement en `CRITICAL`), `SECRET_KEY` régénérée à chaque redémarrage si absente (`config.py:161-169`, qui invalide tous les jetons).

**Correctif** : découpler l'écho de `DEBUG`, comme `AUTO_CREATE_SCHEMA` l'a été de `DEBUG` en vague 2 — c'est le même défaut, sur un autre drapeau.

```python
SQL_ECHO: bool = False          # config.py
engine = create_engine(settings.DATABASE_URL, ..., echo=settings.SQL_ECHO)
```
Et basculer `DEBUG=False` en production, en suivant la séquence de sortie déjà écrite dans le message `CRITICAL` de démarrage.

**Effort** : 1 h (l'écho) ; la bascule `DEBUG=False` est une décision d'exploitation, pas un correctif.

---

### `OBS-03` — les migrations sont réversibles, sauf une — **mineur**

**[EXÉCUTÉ]** Analyse des 13 fichiers Alembic : `downgrade()` est non vide partout, sauf `b959e26248d5_merge_multiple_migration_heads.py` (fusion, légitimement vide). C'est un point sain, à signaler comme tel. La réserve est ailleurs : ces `downgrade` n'ont jamais été exercés, et 10 tables leur échappent entièrement (`MIG-01`).

**Correctif** : ajouter à la CI un travail `alembic upgrade head && alembic downgrade base && alembic upgrade head` sur base jetable. C'est le seul moyen de savoir qu'une réversibilité écrite est une réversibilité réelle.

**Effort** : 2 h (dans le lot `OPS-02`).

---

# 7. Dette technique qui coûtera cher

---

### `DETTE-01` — `execute_workflow` : 1 270 lignes dans une seule méthode — **majeur**

**Fichier** : `backend/app/services/pm_orchestrator_service_v2.py:488-1757`

**[EXÉCUTÉ]** Mesures sur l'arbre syntaxique :

```
fichier                             : 4 398 lignes
classe PMOrchestratorServiceV2      : 3 640 lignes
  .execute_workflow                 : 1 270 lignes | 61 if | 26 try | 409 appels
  ._execute_from_phase4             :   435 lignes
  .resume_from_architecture_validation : 359 lignes
blocs de 10 lignes identiques entre execute_workflow et resume_from_architecture_validation : 31
```

**Le statut déclaré de P4 mérite d'être corrigé.** L'énoncé dit « contrôleur surdimensionné : `pm_orchestrator`, 2 637 lignes ». Deux choses distinctes portent ce nom :
- le **contrôleur** `app/api/routes/pm_orchestrator.py` a bien été éclaté : il fait 18 lignes et ne réexporte qu'un routeur (l. 1-18). **P4 est tenu de ce côté.**
- le **service** `pm_orchestrator_service_v2.py` est passé à 4 398 lignes. Le problème n'a pas été résolu, il a changé d'étage.

**Ce qui se passe** : les 31 blocs dupliqués entre `execute_workflow` et `resume_from_architecture_validation` sont la logique de pipeline recopiée. Toute correction de phase doit être appliquée à deux endroits ; un oubli produit un comportement différent selon qu'on démarre ou qu'on reprend — c'est-à-dire le chemin le plus difficile à reproduire et le plus coûteux en jetons. C'est aussi ce qui rend `SCALE-06` (pipeline reprenable) hors d'atteinte.

**Correctif** — sans réécriture d'architecture, en trois gestes mécaniques et vérifiables :
1. extraire chaque phase en méthode : `_phase1_pm`, `_phase2_ba`, `_phase2_5_digest`, `_phase3_architect`, `_phase4_experts`, `_phase5_sds`, `_phase6_export` ;
2. `execute_workflow` devient une table de phases plus une boucle, et `resume_from_architecture_validation` entre dans la même boucle à un index différent — la duplication disparaît d'elle-même ;
3. `SDS_RESUME_POINTS` (déjà défini, l. 80-88) devient l'index de cette table : le point de reprise cesse d'être une convention et devient une donnée.

Aucune de ces trois étapes ne change un comportement ; chacune est vérifiable par la suite existante.

**Effort** : 24 h. Non bloquant pour le 1er octobre, à faire dans les 90 jours — c'est le préalable à toute reprise du pipeline.

---

### `DETTE-02` — P10 : la classe commune existe, la duplication qu'elle devait retirer aussi — **mineur**

**Fichier** : `backend/agents/base.py` (189 lignes) ; `backend/agents/roles/*.py` (8 443 lignes)

**[EXÉCUTÉ]** Les 11 agents héritent bien de `BaseAgent`. Mais :

```
agents redéfinissant _call_llm : 9 sur 11
agents utilisant super()._call_llm ou BaseAgent._call_llm : 0
```
`BaseAgent._call_llm` (l. 99-142) est donc **du code mort**.

**[EXÉCUTÉ]** Duplication résiduelle entre agents, blocs de 10 lignes identiques :

```
88 blocs  salesforce_data_migration.py    <-> salesforce_developer_lwc.py
60 blocs  salesforce_data_migration.py    <-> salesforce_qa_tester.py
58 blocs  salesforce_research_analyst.py  <-> salesforce_solution_architect.py
52 blocs  salesforce_business_analyst.py  <-> salesforce_pm.py
```

Le statut « P10 partiel » est donc **exact** : l'héritage est en place, la mutualisation ne l'est pas. Ce n'est pas un défaut de style — chacun de ces `_call_llm` recopiés est un endroit où `user_id` aurait dû être propagé (`FIN-01`), et neuf endroits à corriger au lieu d'un.

**Correctif** : faire converger les neuf `_call_llm` vers celui de la base, un agent à la fois, en commençant par Olivia (le plus simple, `salesforce_business_analyst.py:441-475`) et en gardant le contrat de retour à l'identique.

**Effort** : 16 h.

---

### `DETTE-03` — trois sources de vérité pour le coût d'un appel — **majeur**

**[EXÉCUTÉ]** Trois barèmes coexistent, avec des unités et des valeurs différentes :

| Source | Emplacement | Unité | Opus |
|---|---|---|---|
| Routage/budget | `config/llm_routing.yaml:358` → `budget_service.py:97` | $ par million | 5 / 25 |
| Crédits | table `model_pricing`, seed `alembic/versions/008:159-210` | crédits par millier | 5,0 / 25,0 |
| Estimation orchestrateur | `pm_orchestrator_service_v2.py:2212-2233` | $ par million, **codé en dur** | 5,0 / 25,0 |

Les valeurs concordent aujourd'hui. Elles divergeront au premier changement de tarif, parce qu'elles se mettent à jour par trois chemins différents (fichier YAML, migration de base, littéral Python). Et la troisième contient un repli silencieux :

```python
else:
    pricing = MODEL_PRICING["default"]  # Sonnet-level     # l. 2229
```

Un modèle inconnu est **facturé au tarif Sonnet**, sans avertissement. Sur un modèle Opus non reconnu, l'erreur est d'un facteur cinq, dans le sens qui coûte de l'argent.

**Correctif** : `budget_service` lit déjà le YAML — en faire la seule source. Supprimer `_calculate_cost` au profit de `BudgetService.estimate_cost` ; dériver la table `model_pricing` du YAML par un script de seed plutôt que par une migration figée. Et remplacer le repli par un refus explicite : un modèle inconnu doit lever, pas être deviné.

**Effort** : 8 h.

---

### `DETTE-04` — 142 imports différés dans des corps de fonctions — **mineur**

**[EXÉCUTÉ]** 142 imports internes (`from app...`) placés dans des corps de fonctions, répartis sur 33 fichiers. C'est ce qui explique le zéro cycle d'import au niveau module — le cycle est réel, il est simplement déplacé à l'exécution.

Deux raisons distinctes se mélangent, et elles ne se traitent pas pareil :
- **délibéré et bon** : `retry_routes.py:77-81` documente pourquoi `pm_orchestrator_service_v2` est importé tardivement (il tire `python-docx` et `chromadb` ; le monter au niveau module ferait dépendre le démarrage de l'API de ces deux paquets). Un test verrouille cette propriété. À conserver.
- **subi** : les imports croisés `services ↔ models ↔ routes` déplacés faute de frontières. À traiter.

Coût réel : une erreur d'import ne se manifeste qu'à l'appel de la fonction, souvent en production, jamais au démarrage.

**Correctif** : documenter les délibérés (une ligne chacun, comme `retry_routes` le fait déjà) ; remonter les autres au niveau module et laisser l'échec d'import apparaître au démarrage, là où il est bon marché.

**Effort** : 12 h.

---

### `DETTE-05` — surface d'API sans appelant — **mineur**

**[EXÉCUTÉ]** 89 des 167 couples méthode+chemin exposés n'ont aucun appelant dans `frontend/src`. La mesure surestime (le concierge est appelé par le site vitrine, hors de ce dépôt ; les six routes `wizard/step/N` le sont par une variable). Mais un bloc est net : **les 19 routes `/api/v2/*`** (artifacts, gates, questions, context, graph) n'ont aucun appelant, ni frontend, ni backend.

Chaque route non appelée est une surface d'attaque à maintenir, à auditer et à faire migrer pour rien.

**Correctif** : appliquer la méthode déjà retenue pour `deployment.py` (`main.py:164-172`) — commenter l'`include_router`, garder le fichier, écrire pourquoi et à quelle condition le remonter. C'est le bon geste, il a été fait une fois, il suffit de le refaire.

**Effort** : 4 h.

---

### `DETTE-06` — `resolve_resume_point` lève, personne ne rattrape — **mineur**

**Fichier** : `backend/app/services/pm_orchestrator_service_v2.py:231-272` ; appelé sans `try` par `retry_routes.py:83`, `execution_routes.py:192`, `validation_gate_routes.py:364`

**[LU]** La fonction est un très bon travail : table de correspondance explicite, refus motivé pour les reprises BUILD et export, et refus net pour toute valeur hors table — « la table ne doit pas devenir un nouveau repli silencieux » (l. 241). C'est exactement la bonne polarité.

Le seul défaut est de forme : aucun des trois appelants ne rattrape le `ValueError`, qui remonte donc en **500** au lieu d'un 400 explicite. L'utilisateur voit une erreur serveur là où le serveur a raison de refuser.

**Correctif** : `except ValueError as e: raise HTTPException(400, str(e))` aux trois sites.

**Effort** : 1 h.

---

# Vérification des correctifs P0–P12

Statut mesuré ce jour, indépendamment du statut déclaré.

| Réf | Déclaré | Constaté | Preuve |
|---|---|---|---|
| **P0** async/sync | corrigé | **partiel** — routes de l'orchestrateur traitées, `auth`, `project_chat`, `quality_dashboard`, `concierge` non ; plus un `subprocess.run` sur la boucle | `PERF-01`, `PERF-02` [EXÉCUTÉ] |
| **P1** split brain `pm.py` | corrigé | **tenu** — `pm.py` n'existe plus, `pm_orchestrator.py` fait 18 lignes | [EXÉCUTÉ] |
| **P2** 52 chemins absolus | corrigé | **tenu dans `app/` à une occurrence près** — `journal_webhook.py:24` ; persiste hors périmètre applicatif (20 dans `tests/`) | `FIX-P2` [EXÉCUTÉ] |
| **P3** `subprocess.run` des agents | corrigé | **tenu** — `_run_agent` importe directement et exécute en fil (`pm_orchestrator_service_v2.py:2069-2091`) | [EXÉCUTÉ] |
| **P4** contrôleur surdimensionné | partiel | **contrôleur : tenu. Service : aggravé** — 2 637 → 4 398 lignes, une méthode de 1 270 | `DETTE-01` [EXÉCUTÉ] |
| **P5** journaux fragmentés | corrigé | **tenu** — JSON structuré, contexte par `contextvars` | [EXÉCUTÉ] |
| **P6** 13 modèles codés en dur | corrigé | **tenu pour le routage** — `llm_routing.yaml` fait autorité ; réserve : trois barèmes de coût coexistent | `DETTE-03` [EXÉCUTÉ] |
| **P7** 24 `db.commit()` épars | corrigé | **partiel** — `get_db` annule proprement, les blocs critiques sont atomiques ; mais une session par exécution longue et un incrément de coût non atomique | `RACE-01` [LU] |
| **P8** rotation de secrets | corrigé | **contourné** — le script existe, et le mot de passe de production est en clair dans 9 fichiers versionnés | `SEC-01` [EXÉCUTÉ] |
| **P9** `safe_content()` tronquait | corrigé | **tenu** — la fonction n'existe plus dans le dépôt | [EXÉCUTÉ] |
| **P10** pas de `BaseAgent` | partiel | **exact** — la classe existe, 9 agents sur 11 redéfinissent `_call_llm`, la méthode de base est morte | `DETTE-02` [EXÉCUTÉ] |
| **P11** santé du RAG | corrigé | **tenu** — sonde au démarrage et dans `/health`, 503 sur 0 chunk. Mais le chemin monté n'est pas celui lu, et le filtre d'isolation vide le socle | `CONF-02`, `RAG-01` [EXÉCUTÉ] |
| **P12** deux `.env` | corrigé | **tenu pour `.env`** — un seul `load_dotenv()`. Le motif a reparu ailleurs : `agents/requirements.txt` contredit `requirements.txt` | `CONF-03` [EXÉCUTÉ] |

**Deux correctifs déclarés faits qui ne le sont pas** : P8 (contourné : le secret est dans le dépôt) et P4 côté service (aggravé). **Un correctif dont la réussite a créé le blocage suivant** : la suppression de `create_all` au démarrage, sans reconstitution des migrations — `MIG-01`, le plus grave constat de ce rapport.

---

# Le constat que personne n'avait sous les yeux

### `RAG-01` — le filtre d'isolation par projet supprime le socle documentaire ; sans lui, il mélange les clients — **bloquant**

**Fichier** : `backend/app/services/rag_service.py:213`

```python
where_filter = {"project_id": str(project_id)} if project_id else None
```

**[EXÉCUTÉ]** Reproduction sur ChromaDB 1.3.4, avec une collection contenant deux chunks du socle Salesforce (sans métadonnée `project_id`, comme les produit toute ingestion hors projet) et un document téléversé par chacun de deux clients :

```
A) where=None  (project_id absent ou nul) :
     {'source': 'sf-docs'}    Apex governor limits: 100 SOQL
     {'project_id': '7'}      Spécification interne du client A
     {'project_id': '8'}      Spécification interne du client B      ← fuite entre clients
     {'source': 'sf-docs'}    Master-Detail vs Lookup

B) where={'project_id':'7'}  (comportement de query_collection) :
     {'project_id': '7'}      Spécification interne du client A
   -> chunks du socle Salesforce renvoyés : 0                        ← socle perdu
```

**Ce qui se passe** — deux défauts qui s'excluent l'un l'autre, et aucune valeur de `project_id` n'échappe aux deux :

- **Avec** `project_id` (cas nominal du pipeline : `_run_agent` transmet le vrai identifiant, `pm_orchestrator_service_v2.py:2080`) : le filtre ne retient que les chunks portant cette métadonnée, c'est-à-dire **les seuls documents que le client a lui-même téléversés**. Les 70 000 chunks du socle Salesforce, ingérés hors projet, n'en portent pas : ils sont exclus. **Le RAG — l'atout différenciant de la plateforme — est neutralisé sur chaque exécution.** Un client qui n'a rien téléversé fait tourner ses onze agents sans aucun contexte, et obtient des livrables plausibles et pauvres : exactement la panne que la sonde P11 a été écrite pour détecter, sauf qu'ici la sonde compte 70 000 chunks et rend vert.

- **Sans** `project_id` (`0`, `None`, ou tout appelant qui l'oublie) : aucun filtre, et la recherche rend **les documents de tous les clients**. Le brief confidentiel du client A entre dans le prompt de l'agent du client B.

**Réserve d'honnêteté** : la sémantique du filtre est prouvée par exécution ci-dessus, mais je n'ai **pas** pu vérifier les métadonnées du socle réel — il vit sur le VPS (`/opt/digital-humans/rag/chromadb_data`) et aucun script d'ingestion n'est versionné. La conclusion repose sur le seul code d'ingestion présent dans le dépôt, `ingest_document` (`rag_service.py:420-425`), qui ne pose `project_id` **que** lorsqu'un projet téléverse. Commande qui tranche, à passer sur le VPS :

```bash
sqlite3 /opt/digital-humans/rag/chromadb_data/chroma.sqlite3 \
  "SELECT COUNT(*) FROM embedding_metadata WHERE key='project_id';"
# proche de 0 → le socle ne porte pas la métadonnée : le constat tient.
```

**Correctif** : les deux défauts viennent de la même cause — socle partagé et documents clients dans les mêmes collections. Il faut les séparer.

1. Court terme, sans migration de données — le filtre devient une disjonction explicite :

```python
if project_id:
    where_filter = {"$or": [{"project_id": str(project_id)}, {"scope": "shared"}]}
else:
    where_filter = {"scope": "shared"}      # jamais « tout » : c'est le défaut permissif à supprimer
```
et poser `scope="shared"` sur le socle par une passe de mise à jour des métadonnées.

2. Moyen terme : collections distinctes — `sf_kb_*` pour le socle, `proj_{id}_*` par client. C'est aussi ce que le palier 10 000 exige (voir la limite n° 2 de la section 5).

**Test rouge d'abord** : une requête sur un projet sans document téléversé doit rendre des chunks du socle ; une requête sur le projet 7 ne doit jamais rendre un chunk du projet 8. Les deux assertions échouent aujourd'hui.

**Effort** : 8 h (correctif court terme + reprise des métadonnées) ; 24 h (séparation des collections).

---

# Feuille de route

Ordonnée par rapport entre le risque évité et l'effort consenti.

## Vague 1 — avant le 1er octobre (≈ 40 h)

Sans ces points, aucun client ne peut être installé, et le premier compte malveillant coûte plus cher que le chiffre d'affaires du palier.

| Ordre | Réf | Objet | Effort |
|---|---|---|---|
| 1 | `DEP-01` `DEP-02` | déclarer `arq`, `redis`, `PyJWT` — l'installation documentée doit démarrer | 1 h 15 |
| 2 | `SEC-01` | **faire tourner** le mot de passe PostgreSQL, retirer les 3 replis en dur | 3 h |
| 3 | `MIG-01` | migration de rattrapage des 10 tables + 007 défensif ; `alembic upgrade head` vert sur base vide | 6 h |
| 4 | `SEC-02` + `SCALE-03` | `X-Forwarded-For` de confiance uniquement + stockage Redis du plafond | 5 h |
| 5 | `FIN-01` | arbitrer Opus/Pro, propager `user_id`, activer le pré-vol et le débit | 8 h |
| 6 | `RAG-01` | disjonction socle/projet + reprise des métadonnées | 8 h |
| 7 | `CONF-01` `CONF-02` | compose de production : `--reload`, Vite dev, Redis, worker, `DH_CHROMA_PATH` | 4 h 15 |
| 8 | `SEC-03` `SEC-04` `SEC-08` | fermer budget, blog, agents, workers/health | 2 h |
| 9 | `CRASH-01` | description nulle → 500 sur le chat | 30 min |
| 10 | `OBS-02` | découpler `echo` de `DEBUG` | 1 h |
| 11 | `SEC-05` (partie basse) | `python-jose` 3.4.0, `python-multipart` 0.0.31 | 2 h |

**Critère de sortie, à exécuter et à publier** : sur une machine neuve, `pip install -r requirements-test.txt && alembic upgrade head && uvicorn app.main:app` démarre ; `pytest` ne régresse pas par rapport à la référence 591/11 ; le banc de cloisonnement et le banc de paliers de ce rapport passent au vert.

## Vague 2 — dans les trente jours (≈ 70 h)

| Réf | Objet | Effort |
|---|---|---|
| `OPS-02` | intégration continue (PostgreSQL + Redis + pytest + pip-audit + ruff) et remise au vert des 11 tests | 16 h |
| `SEC-07` | course du contexte d'audit → `contextvars` | 3 h |
| `SCALE-01` | bail et battement par worker : rendre possible le deuxième worker | 12 h |
| `SCALE-02` | Redis configurable | 1 h |
| `TIME-01` `TIME-02` | délais de garde qui bornent réellement | 7 h |
| `TIER-01` `FIN-02` `FIN-03` | quotas de projets, plafonds par palier, idempotence Stripe | 12 h |
| `PERF-01` `PERF-02` | fin de P0 : 12 routes + `query_org` | 4 h 30 |
| `ENV-01` | 22 variables déclarées + inventaire au démarrage | 3 h |
| `OPS-01` `OPS-04` | test de fumée qui dit la vérité, nginx versionné | 6 h |
| `OPS-03` | transitions d'état : plus de `pass` muet | 6 h |
| `SEC-06` | `npm audit fix` et non-régression frontend | 3 h |

## Vague 3 — plus tard (≈ 180 h)

| Réf | Objet | Effort | Déclencheur |
|---|---|---|---|
| `SCALE-04` | livrables en stockage objet, espace SFDX par exécution | 36 h | avant le 2ᵉ nœud d'API |
| `SCALE-05` | ChromaDB en mode serveur | 8 h | avant le 2ᵉ nœud |
| `DETTE-01` | éclatement de `execute_workflow` en phases | 24 h | avant toute reprise de pipeline |
| `SEC-05` (partie haute) | FastAPI ≥ 0.115 / starlette ≥ 1.3 et reprise du `TestClient` | 12 h | avant l'audit de sécurité client |
| `DETTE-03` | source unique du barème de coût | 8 h | au 1er changement de tarif |
| `DETTE-02` | convergence des 9 `_call_llm` | 16 h | continu |
| `OBS-01` | métriques et alertes | 8 h | avant 100 clients |
| `SCALE-06` | audit en file, SSE sans sondage, partition d'`audit_logs` | 8 h | avant 100 clients |
| `DETTE-04` `DETTE-05` `DETTE-06` | imports différés, surface morte, codes HTTP | 17 h | continu |
| `SEC-06` (haut) | cycle de vie des jetons, révocation | 12 h | avant 1 000 clients |
| Multi-tenant | organisations, rôles, collections RAG par client | 40 h+ | avant 1 000 clients |

---

# Ce qui tient — à ne pas retoucher

Relevé explicitement, pour éviter du travail inutile.

- **Le cloisonnement des routes principales.** `verify_execution_access`, `_load_artifact_for_user`, `_get_project_or_404` remontent tous la chaîne jusqu'à `Project.user_id`. Vérifié en croisé : `progress` et `result` rendent 404 à un tiers. Trois exceptions seulement, listées en `SEC-03` et `SEC-08`.
- **La frontière commerciale SDS/BUILD**, appliquée côté serveur, échouant fermé, vérifiée sur trois paliers.
- **Les protections contre l'injection.** Aucun `shell=True`, aucun SQL construit par concaténation, aucune désérialisation non sûre, traversées de répertoire fermées sur les trois sites historiques. `agent_tester` porte trois verrous indépendants là où l'audit d'origine signalait la faille la plus grave.
- **`resolve_resume_point`** (`pm_orchestrator_service_v2.py:231-272`) : refus explicite et motivé de toute valeur hors table, avec la raison écrite. Le modèle à suivre partout ailleurs.
- **Le flux SSE** : session de base rendue avant le flux (`execution_routes.py:326-327`), instantanés hors boucle d'événements, chaque commentaire explique le défaut qu'il corrige.
- **La sonde `/health`** : trois dépendances réellement interrogées, 503 si une seule tombe, sondes exécutées en fils. Rare et bien fait.
- **Le webhook Stripe** : refus net sans secret, signature vérifiée, 500 délibéré pour la reprise.
- **Le concierge public** : budget quotidien, sel d'anonymisation obligatoire sous peine de refus du tour.
- **Le garde-fou de chiffrement** (`main.py:68-76`) : il crie en `CRITICAL` à chaque démarrage qu'il est inerte, avec la séquence de sortie numérotée. C'est le contre-exemple à imiter — un dispositif qui ne se tait pas.
- **La garde de base de test** (`tests/db_guard.py`) : refuse par défaut tout ce qu'elle ne peut pas prouver jetable. La bonne polarité.
- **La journalisation structurée** et la propagation de contexte par `contextvars` (`logging_config.py`, `middleware/execution_context.py`).

Une remarque de forme, et c'est un compliment : les commentaires de ce dépôt expliquent *le défaut corrigé et pourquoi il coûtait cher*, pas *ce que fait la ligne*. C'est ce qui a rendu cet audit rapide, et c'est ce qui rendra les correctifs ci-dessus vérifiables.

---

# Annexe — reproduire les mesures

Environnement :

```bash
python3 -m venv /tmp/audit && /tmp/audit/bin/pip install -r backend/requirements.txt \
    arq redis PyJWT "httpx>=0.27,<0.28" pytest-timeout pip-audit
initdb -D /var/lib/postgresql/auditpg -U postgres -A trust && pg_ctl -D … start
redis-server --daemonize yes --port 6379
createdb -h 127.0.0.1 -U postgres digital_humans_test
```

| Constat | Commande |
|---|---|
| `DEP-01` | `pip install --dry-run --ignore-installed --report r.json -r backend/requirements.txt` puis chercher `arq`/`redis` dans `r.json` |
| `DEP-02` | même rapport : `pyjwt`, `requested: false`, tiré par `nomic` |
| `MIG-01` | `createdb dh_alembic && DATABASE_URL=…/dh_alembic alembic upgrade head` |
| `SEC-01` | `grep -rn "DH_SecurePass2025" . --exclude-dir=.git --exclude-dir=docs` |
| `SEC-02` | script `proof_ratelimit.py` (60 `POST /api/auth/login` à `X-Forwarded-For` variable) |
| `SEC-03` | script `proof_idor.py` (anonyme et tiers sur `/execute/{id}/budget`) |
| `SEC-07` | script `proof_audit_race.py` (40 requêtes concurrentes, comptage des `user_agent` distincts) |
| `FIN-01` | script `proof_credit.py` (appel LLM à la manière d'un agent, `CreditService` instrumenté) |
| `FIN-01` bis | script `proof_credit2.py` (pré-vol Opus sur compte Pro) |
| `RAG-01` | script `proof_rag.py` (ChromaDB local, socle sans `project_id` + deux clients) |
| `TIME-01` / `TIME-02` | scripts `proof_timeout.py` et `proof_thread.py` |
| `TIER-01` | script `proof_tiers.py` (trois comptes, six familles de routes) |
| `PERF-02` | script `scan_async.py` (arbre syntaxique, appels bloquants hors fonction imbriquée) |
| `OPS-01` | les quatre appels de `scripts/smoke_test.sh` contre `DEBUG=False` |
| `SEC-05` / `SEC-06` | `pip-audit -r backend/requirements.txt` ; `npm audit --package-lock-only` (dans `frontend/`) |
| référence des tests | `TEST_DATABASE_URL=…/digital_humans_test pytest tests/ -q --timeout=120` |

Les scripts d'épreuve ont été écrits hors du dépôt (répertoire de travail temporaire) et ne sont pas versionnés : cette mission était un audit, pas une vague de correctifs. Chacun tient en 20 à 40 lignes et se reconstruit à partir de la description du constat.

---

*Audit réalisé le 23 août 2026 sur `9e3d6fa`. Aucune modification de code applicatif, aucun redémarrage de service, aucune écriture sur le VPS. `docs/audit-20260821/` (hors `prompt-audit.md`) et `docs/vague3/` n'ont pas été ouverts.*
