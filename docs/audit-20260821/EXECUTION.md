# Exécution de la vague 1 — audit croisé du 21/08/2026

Branche `correctifs/audit-croise-20260821` · 16 commits · 69 fichiers · +5828 / −1827

Les sept lots du `PLAN.md` sont appliqués. Chaque lot a été confié à un agent
disposant d'un périmètre de fichiers exclusif, et **aucun critère de fin n'a été
accepté sans une commande dont la sortie est jointe** — c'est la leçon centrale
de cet audit, où quatre correctifs déclarés faits ne l'étaient pas.

Neuf lots supplémentaires (`bis`, `ter`, `quater`) ont été nécessaires : le
découpage du plan comportait des lacunes, et deux lots backend ont cassé des
appels frontend en fermant des routes. Le détail est en §3.

**Suite de tests — avant / après la vague :**

| | échecs | passés | erreurs |
|---|---|---|---|
| Avant (code non modifié) | 11 | 208 | 8 |
| Après | **14** | **389** | **0** |

Les 8 erreurs et les 14 échecs sont **les mêmes défauts** : la réparation de
`conftest.py` (§2.0) a transformé 8 erreurs d'outillage en 3 échecs réels dans
`test_auth.py`. Aucune régression n'a été introduite : la liste nominative des
échecs est identique d'un bout à l'autre — `test_sf_admin_service.py` (6),
`test_credit_service.py` (4), `test_auth.py` (3), `test_emma_phase3.py` (1).
Tous préexistent à la vague 1 et sont hors des périmètres traités.

---

## 1. Vérification indépendante des critères de fin

Rejoués par l'orchestrateur sur le dépôt final, hors des rapports d'agents.

| Lot | Critère | Commande | Résultat |
|---|---|---|---|
| A | Free → 403 sur SDS, Pro → 403 sur BUILD | `pytest tests/test_lot_a_tier_boundary.py` | 19 passed |
| A bis | retry_routes gardé, SSE en-tête + query | `pytest tests/test_lot_a_bis_*.py` | 19 passed |
| A ter | SSE n'immobilise plus de connexion | `pytest tests/test_lot_a_ter_sse_pool.py` | 5 passed |
| B | A → 403/404 sur ressource de B, par routeur | `pytest tests/test_lot_b_cloisonnement.py` | 10 passed |
| C | plus aucun `shell=True` | `grep -rn "shell=True" backend/app --include='*.py'` | **aucun** |
| C | agent-tester → 401 sans jeton | `pytest tests/test_lot_c_injection_commandes.py` | 49 passed |
| D | un SDS à 3 BR produit 3 UC | `pytest tests/test_lot_d_*.py` | 18 passed |
| E | un seul `.env` fait autorité | `grep -rnE "open\([^)]*\.env\|RAG_ENV_PATH"` | **aucun** |
| E | rotation de clé exécutable | `scripts/rotate_encryption_key.py --help` | s'exécute |
| F | aucun XSS sur contenu d'agent | `grep -rn dangerouslySetInnerHTML frontend/src` | SVG mermaid seul |
| F | aucun appel frontend non authentifié | `grep` liens nus + `fetch` nus | **aucun** |
| G | `/health` échoue base arrêtée | `pg_ctl stop` puis `GET /health` | **503** |
| G | aucune session pendante / 100 exécutions | `engine.pool.checkedout()` | **0** |

---

## 2. Ce qui a été corrigé, lot par lot

### 2.0 Préalable — l'outillage de test était cassé

`backend/tests/conftest.py` forçait `sqlite:///./test.db` alors que les modèles
utilisent des colonnes `JSONB`, que SQLite ne sait pas compiler. **Toute fixture
créant les tables échouait en `CompileError`** : les 8 tests de `test_auth.py`
ne pouvaient structurellement pas s'exécuter, et aucun test de route ne pouvait
être écrit. C'est le défaut que Kimi désigne quand il écrit « PROD-01 serait
resté invisible exactement pour cette raison ».

Réparé (`d0f33c0`) : `TEST_DATABASE_URL`, puis `DATABASE_URL`, puis un défaut
PostgreSQL. Avant : 8 erreurs. Après : 5 passés, 3 échecs réels.
**Hors des sept lots** — sans cette réparation, aucun critère de fin des lots A,
B, C ou G n'était démontrable.

### 2.1 LOT-D — plantages fonctionnels *(commit `e316391`)*

Le correctif au meilleur rapport risque/effort de toute la vague.

**`kim:PROD-01`** — `salesforce_business_analyst.py:337`, deux lignes. Un `if
batch_mode:` sans `else` laissait `prompt` non affecté. L'orchestrateur envoyant
les BR par lots de 2 (`BATCH_SIZE = 2`, confirmé à
`pm_orchestrator_service_v2.py:523`), **tout projet à nombre impair de BR
perdait son dernier cas d'usage**, après avoir payé les appels précédents.

Preuve — le test rejoue la boucle réelle de l'orchestrateur sur 3 BR :

```
AVANT  lot [BR-001, BR-002] → OK
       lot [BR-003]         → UnboundLocalError: cannot access local
                              variable 'prompt' where it is not associated
                              with a value   (salesforce_business_analyst.py:339)
APRÈS  18 passed — sorted(ucs_par_br) == ['BR-001','BR-002','BR-003']
```

**Second tueur silencieux sur le même chemin**, non signalé par les rapports :
`_parse_response:463` laissait `uc_count` non affecté pour **toute** réponse
mono-BR. Corriger PROD-01 seul n'aurait pas suffi.

**`kim:PROD-03` / `cla:CRASH-02`** — 4 agents (`ba`, `pm`, `devops`, `trainer`)
retournaient `None` au lieu d'un tuple quand `llm_service` est indisponible →
`TypeError` à l'unpacking chez l'appelant. Échec net et nommé désormais.

### 2.2 LOT-A — frontière payante *(commits `179e1fd`, `f66d644`, `33559ad`)*

Le décorateur `require_feature` existait depuis toujours et **n'était appliqué
nulle part** : ses deux seules occurrences étaient sa propre définition et son
exemple de docstring. Posé sur `/execute`, `/execute/{id}/resume` et
`start-build`. Free → 403 sur SDS ; Free et Pro → 403 sur BUILD.

**Trouvé en vérifiant, non signalé par les rapports :**

- **`BuildEnabledMiddleware` était totalement inerte.** Ses regex s'écrivaient
  `^/api/projects/\d+/start-build/?$` alors que le routeur est monté sous
  `/api/pm-orchestrator`. Aucune route réelle ne matchait : le profil `freemium`
  n'a jamais rien bloqué.
- **Le flux SSE de progression était mort en production.** Il faisait
  `from app.services.auth_service import verify_token` — **ce module n'existe
  pas dans le dépôt**, et cette ligne en était l'unique occurrence. Le
  `except Exception` convertissait le `ModuleNotFoundError` en 401 :
  `{"detail":"Authentication failed: No module named 'app.services.auth_service'"}`.
  Le suivi en direct renvoyait 401 à tout le monde, jeton valide compris.
- **Un `UnboundLocalError` dans le générateur SSE**, révélé une fois
  l'authentification réparée, sur une ligne portant `# noqa: F823 — ruff false
  positive on closure`. **L'alerte ruff était fondée**, le commentaire l'écartait
  à tort.
- **`pause_build` / `resume_build` ne vérifiaient pas la propriété.** Le
  commentaire du code affirmait « `verify_execution_access` not needed here —
  `BuildPhaseService` handles it ». Faux : le service filtre sur `Execution.id`
  seul. N'importe quel compte Team pouvait mettre en pause le BUILD d'un autre
  client.
- **La session SSE immobilisait une connexion PostgreSQL pendant 600 s.** Le
  `db.refresh()` synchrone signalé par Kimi n'était que le symptôme ; la cause
  était la session de `Depends(get_db)` tenue sur toute la durée du flux.

Mesure sur 30 flux SSE simultanés :

```
AVANT  checkedout PENDANT = 30   (pool size=20, overflow=11, plafond=40)
       checkedout APRÈS   = 1    (une connexion jamais rendue)
APRÈS  checkedout PENDANT = 0
       checkedout APRÈS   = 0
```

**Le 34e client du monitoring rendait la base inaccessible à toute la
plateforme.**

`/retry` a reçu un gate `sds_document` — la route reprend la séquence SDS, pas
le BUILD — plus un gate `build_phase` **conditionnel** quand des tâches BUILD
sont présentes, pour ne pas priver un compte Pro du retry SDS qui lui est dû.

### 2.3 LOT-B — authentification et cloisonnement *(commits `466a0d4`, `90a5694`)*

Neuf routeurs traités. Preuve rejouée sur le code d'origine :

```
GET  /deliverables/{id}   anonyme → 200
     {"deliverable_type":"sds","content":"<html><body>SDS confidentiel</body>...
GET  /api/v2/artifacts    anonyme → 200
POST /deployment/promote  anonyme → 200
     {"success":false,"error":"Cannot connect to: production"}   ← tentative réelle
PUT  /api/projects/2/change-requests/2  par A → 200  {"title":"pirate",...}
upload ../../evasion.txt  → écrit hors du répertoire projet
GET  /api/audit/logs      anonyme → 200
     comptes exposés = ['alice@example.test', 'bob@example.test']
GET  /api/audit/tasks/TASK-001/history  par A → executions vues = [1, 2]   ← la 2 est celle de B
```

**`app/api/audit.py` n'était dans la liste de fichiers d'aucun des sept lots.**
Monté sur `/api/audit` (`main.py:101`), cinq routes, aucune authentification :
`GET /api/audit/logs` exposait l'historique d'actions, les IP et les user-agents
de tous les clients. Sans la remontée de l'agent, il passait le 1er octobre
intact.

Quatre routes étaient **inexécutables** avant d'être cloisonnables : un
`get_db_session` qui n'existe pas dans `database.py` (ImportError sur 4 routes),
un `.distinct()` sur colonnes JSON (`500` pour tout utilisateur), un membre
d'enum absent. Elles étaient mortes en production sans que personne ne le sache.

Modèle retenu pour `/logs` : **journal par client**, tranché sur un fait
vérifiable — `grep` sur `is_admin|is_superuser|role` dans `models/user.py` et
`utils/dependencies.py` ne renvoie rien. Un journal global admin supposerait une
colonne de rôle et une migration : c'est une fonctionnalité, pas un correctif.

### 2.4 LOT-C — injections et exécution de commandes *(commit `2cdf280`)*

`GET /api/agent-tester/org/query?soql=...` injectait son paramètre d'URL dans
`subprocess.run(f'sf data query --query "{soql}"...', shell=True)`, **sans
authentification, joignable depuis Internet**. Les quatre `shell=True` sont
passés en liste d'arguments ; le routeur entier est authentifié.

Preuve d'injection, avec contre-épreuve :

```
charge : 'SELECT Id FROM Account" ; rm -rf <témoin> ; echo "'
témoin présent après → True
argv[4] = 'SELECT Id FROM Account" ; rm -rf <témoin> ; echo "'   ← UNE case, verbatim

contre-épreuve, même charge, construction d'avant correctif :
témoin présent après → False    ← la charge est réelle
```

Sans la contre-épreuve, « le témoin survit » ne prouverait rien. L'agent note
honnêtement que **ce n'est pas son filtre SOQL qui bloque l'injection** — la
charge commence par `SELECT Id FROM Account` et franchit le filtre — mais
`shell=False`.

Un troisième site de traversée de répertoire, non cité par les rapports, a été
trouvé : `/logs/{test_id}` passait le paramètre d'URL à
`LOGS_DIR / filename` sans contrôle.

### 2.5 LOT-E — secrets et configuration *(commits `dc859ab`, `766a89e`)*

**P12 — le second `.env` est supprimé.** `rag_service.py` relisait
`/opt/digital-humans/rag/.env` ligne par ligne quand `OPENAI_API_KEY` manquait :
deux clés OpenAI pouvaient coexister sans qu'on sache laquelle servait. C'est le
défaut qui a coûté du temps le 21/08.

**P8 — le script de ré-encryption existe.** `encryption.py` admettait dans sa
propre docstring qu'il n'existait pas. Preuve, sur base dédiée :

```
[ROTATE ] id=1..5 — verified round trip
[ENCRYPT] id=6 — verified round trip (40 chars)
COMMITTED — all rows re-encrypted with the new key
VERIFY OK — every non-empty row decrypts with the current key
6/6 credentials relus par decrypt_credential (chemin applicatif)
avec l'ANCIENNE clé : Failed to decrypt credential: Invalid token or key
```

La dernière ligne distingue une vraie rotation d'un no-op.

**`gem:CONF-01`** — l'identité d'org Salesforce n'était pas seulement en dur :
`from_project()` remplissait champ par champ depuis `cls.*`, si bien qu'**un
projet à moitié configuré empruntait silencieusement l'identité de l'org par
défaut**. L'échec a été porté au point d'usage (`require()`) et non à la
construction, parce que trois modules construisent `SalesforceConfig()` **à
l'import** : lever au constructeur aurait empêché le backend de démarrer.

**`cla:SEC-03`** — le repli acceptant les jetons Git en clair est retiré. Sans
cela, de nouveaux jetons en clair seraient réapparus et la migration aurait été
à refaire.

### 2.6 LOT-F — frontend *(commits `c568523`, `2c679d4`, `4e9ba34`, `d3371fd`)*

XSS sur contenu d'agent supprimé, JWT retiré des URL, services morts supprimés.
Trouvé en vérifiant, non signalé par les quatre modèles : un `href="$2"`
interpolant une URL brute dans `SDSPreview`, et deux routes mortes masquées par
des `catch` silencieux.

**Le périmètre du plan était incomplet** : `dangerouslySetInnerHTML` existait
dans 4 fichiers, dont `ChatSidebarStudio.tsx:327` qui rend `msg.content` —
exactement la même faille que `ChatSidebar.tsx`, hors de la liste.

**Parcours d'inscription cassé** (hors audit, corrigé sur arbitrage) :
`VerifySignupPage.tsx` écrivait `localStorage['access_token']` là où les
6 lectures du frontend lisent `localStorage['token']`. L'utilisateur qui
confirmait son inscription n'était pas authentifié et repartait vers `/login`.
Il pouvait se connecter à la main — d'où un défaut invisible qui coûtait une
part des inscriptions.

### 2.7 LOT-G — sessions, async, démarrage *(commit `7367c09`)*

**`create_all` tournait à l'import.** Deux conséquences : il crée les tables sans
estampiller `alembic_version` (dérive de schéma au premier `upgrade head`), et
il rendait le processus **incapable de démarrer** base absente — une panne de
base devenait « l'API ne boote pas » au lieu de « l'API se déclare malade ».

**`/health` renvoyait `{"status": "healthy"}` inconditionnellement.** Une base
morte répondait 200 au répartiteur de charge pendant que toutes les requêtes
tombaient en 500. PostgreSQL réellement arrêté, aucun mock :

```
base démarrée  → 200 {"status":"healthy","checks":{"database":{"status":"up"}}}
base arrêtée   → 503 {"status":"unhealthy", ... "OperationalError: connection refused"}
ancien main.py → OperationalError au boot (il ne pouvait même pas rapporter son état)
base relancée  → 200
```

**Sessions du WebSocket** : 100 connexions → 16 sessions pendantes avant,
0 après. 30 onglets simultanés → 30 connexions immobilisées avant, 0 après.

**`GET /download/{filename}`** résolvait `OUTPUT_DIR / filename` sans
authentification ni résolution de chemin :
`GET /download/..%2F..%2F..%2Fetc%2Fpasswd` lisait des fichiers arbitraires.
**Route supprimée** après vérification qu'aucun appelant n'existe.

---

## 3. Ce que le plan n'avait pas prévu

Trois catégories de lacunes, toutes traitées.

**Fichiers absents de tous les lots.** `app/api/audit.py` (routeur monté, sans
authentification), `app/salesforce_config.py` et
`app/services/jordan_deploy_service.py` (constats `gem:CONF-01` et `cla:SEC-03`
pourtant **assignés** au LOT-E — c'est la liste de *fichiers* qui était
incomplète, pas le périmètre), `retry_routes.py` (contournement direct de la
frontière payante), et trois fichiers frontend portant la même faille XSS que
celui listé.

**Régressions croisées entre lots.** Deux fois, un lot backend a fermé un
routeur que le frontend appelait sans jeton :

- LOT-B ferme `deliverables.py` → le bouton « Ouvrir le SDS » (`href` nu) casse.
  **Correctif écarté** : LOT-B proposait d'ajouter `?token=` en URL, ce qui
  réintroduisait le JWT que LOT-F venait d'en retirer. Résolu par l'en-tête
  `Authorization` via un helper existant.
- LOT-C ferme `agent-tester` → trois `fetch` nus de `AgentTesterPage` cassent.
  L'un des trois est un **flux SSE** : le faire passer par `apiCall` l'aurait
  cassé silencieusement (`apiCall` finit par `return response.json()`, ce qui
  consomme le corps d'un bloc).

Les deux formes d'appel non authentifié (`href=`/`action=` et `fetch`) sont
désormais balayées et à zéro. **Si un lot futur pose des `Depends`, rejouer ces
deux `grep` avant de clore.**

**Constats mal localisés.** Corrigés en vérifiant, jamais appliqués au hasard :
`cla:CRASH-05` visait `generate_build_v2` (où le coût est correctement tracé) au
lieu de `generate_build` ; `cla:CRASH-03` pointait des lignes de prompt ;
`cla:CRASH-02` annonçait 5 agents, il y en a 4 ; `agent_tester.py:63` était
annoncé `:45` par Gemini et `:≈88` par Claude ; `salesforce_business_analyst.py:337`
était annoncé `:≈348`.

---

## 4. Ce qui ne s'est pas confirmé dans le code

| Réf | Cible | Verdict | Preuve |
|---|---|---|---|
| `cla:CRASH-01` | `budget_service.py:175` | **Non confirmé.** Ligne de docstring. `BudgetService` ne crée ni ne ferme jamais de session : `__init__` la reçoit, les deux constructeurs la possèdent. Cycle de vie entièrement chez l'appelant. | Fichier laissé intact |
| `cla:CRASH-01` | mécanisme décrit | **Non confirmé tel qu'écrit.** Le rapport affirme qu'`auto_created_db` n'est vrai qu'après la ligne 119 et qu'un `raise` dans `check_budget` laisse la session pendante. Le drapeau était posé **avant** le `try`. | **100 appels budget dépassé → 0 session pendante, avant correctif.** Fenêtre réelle mais ailleurs et plus étroite ; corrigée |
| `cla:SEC-01` | `quality_gates.py` | **Non atteignable.** Routeur sans auth, mais jamais monté dans `main.py` | `grep -n quality_gates app/main.py` → vide |
| `cla:SEC-01` / `kim:SEC-01` | `sds_versions.py` | **Déjà cloisonné.** 7 routes portant `get_current_user` + filtre `Project.user_id` | Test de cloisonnement **passe sur le code d'avant** — fichier non modifié |
| `kim:SEC-01` | `documents.py` (accès) | **Déjà cloisonné.** `_get_project_or_404()` filtre sur `user.id` | Test **passe sur le code d'avant** |
| — | `analytics.py` | **Déjà cloisonné** sur les 7 requêtes. Seul un crash `500` préexistant a été corrigé | — |
| `cla:TIER-01` | `models/subscription.py` | **Aucun défaut.** C'est la déclaration de politique, et elle est juste. Le défaut était côté route | Fichier non modifié |
| `cla:TIER-02` | « le middleware devrait vérifier le tier » | **Écarté.** `BuildEnabledMiddleware` est un interrupteur par profil de déploiement, rôle légitime et distinct. Le tier se vérifie à la route | Le middleware a en revanche été réparé : il était inerte |
| `cla:SEC-05` | `SECRET_KEY` auto-générée | **Non un défaut** — le rapport Claude le conclut lui-même. `config.py:101` lève déjà si `not DEBUG` | — |

---

## 5. Ce qui reste ouvert

Classé par gravité. **Ce qui n'est pas dans cette section ne sera pas repris.**

### 5.1 Bloquant pour la montée en charge

**`notification_service.py` — plafond dur à 5 clients de monitoring simultanés.**
Le pool asyncpg est créé `max_size=5` (`:46`) et `subscribe()` garde une
connexion pour toute la durée de l'abonnement (`:114`). Le 6e client SSE ou
WebSocket simultané attend indéfiniment — observé : blocage de 90 s puis
expiration. **Ce verrou annule en pratique le bénéfice des deux correctifs
`kim:PROD-02`** tant qu'il tient. L'estimation de Kimi (« casse dès ~30 clients »)
est optimiste d'un facteur six. Hors périmètre de tous les lots.

**`deployment.py` — 7 routes authentifiées mais non cloisonnées.** `promote`,
`validate`, `rollback`, `snapshot/create`, `snapshots`,
`release-notes/generate`, `environments` prennent des chemins de fichiers
arbitraires (`source_path`, `snapshot_path`) sans lien avec une ressource en
base. **Un client authentifié peut promouvoir le package d'un autre s'il en
devine le chemin.** Les fermer suppose de rattacher les déploiements à une
exécution en base — un modèle qui n'existe pas. Refonte, hors périmètre gelé.

**`kim:TIER-02` — les quotas de crédits ne bornent pas la dépense.**
`llm_router_service._credit_preflight` renvoie `None` dès que
`request.user_id is None`, ce qui est le cas de **100 % des appels d'agents**
(ils ne transportent que `execution_id`). Le gate du LOT-A empêche un compte
Free de *démarrer* une exécution, ce qui coupe le scénario principal, mais ne
borne pas la dépense d'une exécution légitimement démarrée. Correctif proposé :
résoudre `user_id` depuis `execution_id` en étendant `_resolve_tier_for_execution`.

### 5.2 À traiter avant l'ouverture

**Bascule cookie `HttpOnly`.** Le jeton reste lisible dans `localStorage` et
continue d'atterrir dans les journaux nginx via le query param de la SSE
(`EventSource` ne sait pas envoyer d'en-tête). Le serveur accepte désormais
l'en-tête `Authorization` en priorité (`kim:SEC-07`, LOT-A bis) : **l'exposition
est débloquée côté serveur, pas refermée.** La bascule exige une décision
conjointe frontend + backend sur `SameSite` et la protection CSRF — accepter un
cookie sur un `GET` SSE ouvre un `EventSource` cross-site authentifié par
ambiance. Ce n'est pas une ligne à glisser dans un lot de correctifs.

**`resume_from = "build_tasks"` est une valeur morte.** `execute_workflow` ne la
reconnaît pas (`pm_orchestrator_service_v2.py:377` et `:488`) : elle tombe dans
la branche générique « saute la phase 1 ». **Un retry après échec de tâches
BUILD ne reprend donc pas les tâches BUILD — il rejoue du SDS.** Concerne
directement le P0 « E2E BUILD FormaPro ».

**`kim:PROD-10` — deux chemins d'écriture incompatibles pour le secret
Salesforce** (`routes/projects.py`, `wizard.py`), et lecture sans déchiffrement.
Le script de rotation re-chiffre les lignes existantes, mais tant que les deux
chemins coexistent le problème revient.

**Enums de paliers désalignés côté frontend** (`premium` vs `pro`, `team` absent
de `FeatureGate`). Le backend refuse correctement, mais l'UI propose des actions
vouées au 403. À raccrocher au payload d'erreur de `FeatureAccessError`
(`error`, `feature`, `required_tier`, `upgrade_url`).

### 5.3 Secrets à faire tourner

- **Mot de passe PostgreSQL en dur dans 7 fichiers versionnés** (l'audit en
  annonçait 5) : `backend/app/api/routes/blog.py`,
  `backend/app/services/document_generator.py`,
  `backend/app/services/sds_template_generator.py`,
  `backend/tests/e2e/test_sds_workflow_e2e.py`,
  `backend/tests/test_wbs_task_types.py`, `backend/tests/test_wizard_phase5.py`,
  `tools/lib/collect_sds.py`. **Il est dans l'historique git : à faire tourner,
  pas seulement à retirer du code.**
- **Clé OpenAI du second `.env`** (`/opt/digital-humans/rag/.env` sur le VPS) :
  n'est plus lue, **à révoquer** après confirmation que celle de `backend/.env`
  est la bonne. Le fichier peut être supprimé du VPS.
- **Identifiants d'org Salesforce** : retirés du code, mais **dans l'historique
  git** — à traiter comme exposés. Ils subsistent hors périmètre dans
  `AUDIT_46_FEATURES.md`, `CHANGELOG.md`, `CLAUDE.md`,
  `SESSION_HANDOFF_SKILL_CREATION.md`, `docs/refonte/sources/timeline.yaml`,
  `n8n/export/ON3gl9I3DAx4IUzM.json`. Le nettoyage ne les retire pas de
  l'historique.

### 5.4 Mineur, mais réel

- **`audit_service.get_logs()` reste sans notion de propriétaire.** Le
  cloisonnement est posé dans la route, pas dans le service : tout futur
  appelant du service contournera le garde-fou.
- **Décodage SSE de `AgentTesterPage`** : `decoder.decode(value)` sans
  `{ stream: true }` ni tampon entre chunks. Un événement coupé à la frontière
  d'un chunk produit un `JSON.parse` en échec avalé par un `catch { }` — **la
  ligne de log est perdue en silence**. Deux lignes. Sur un flux de test
  d'agent, une ligne manquante peut faire conclure qu'une étape n'a pas eu lieu.
- **`AuditMiddleware` écrit une ligne `audit_logs` par requête SSE**, en SQL
  synchrone sur la boucle d'événements.
- **`MermaidRenderer.tsx:137`** conserve un `dangerouslySetInnerHTML` sur du SVG
  produit par un agent. Examiné puis écarté : Mermaid produit du SVG par nature,
  le correctif dépasse la correction minimale.
- **`/render` accepte encore le jeton en query param** en repli — résidu
  délibéré, à retirer avec la bascule cookie. Le frontend utilise l'en-tête.
- **`quality_dashboard.py` `/execution/{id}` répond 500 même au propriétaire** :
  le SQL sélectionne `validation_status` et `validation_errors`, colonnes
  absentes du modèle. Défaut préalable, mapping non devinable.
- **`change_requests.py` : `related_br_id` n'est pas validé** — on peut pointer
  un `BusinessRequirement` d'un autre projet, dont le texte ressort dans
  `related_br_text`. Fuite étroite mais réelle.
- **`redis` et `chroma` absents de `/health`** — Kimi demandait
  `SELECT 1` + `redis.ping` + `chroma.count`. Seule la base est couverte.
- **`agent_executor.py` / `agent_tester.py`** appellent désormais
  `salesforce_config.require()`, mais **`pm_orchestrator_service_v2.py:1441`**
  garde un repli `sf_cfg = salesforce_config` quand `project` est `None` : il
  n'emprunte plus d'identité, mais mériterait un refus explicite.
- **Les `migrations/*.sql` manuels doublonnent Alembic** (PROD-05) — à marquer
  morts.
- **Les 14 échecs de la suite** préexistent tous. Les 6 de
  `test_sf_admin_service.py` sont des tests de spécification sur des attributs
  jamais implémentés (`OPERATION_HANDLERS`, `FIELD_TYPE_MAP`) : les faire passer
  serait de la fonctionnalité, pas un correctif.
- **`python-docx` et `chromadb` absents de l'environnement de test.**
  `pm_orchestrator_service_v2` ne s'y importe pas. **Le test E2E BUILD FormaPro
  du P0 ne pourra pas tourner en l'état.**

---

## 6. Gestes d'exploitation — à faire avant l'ouverture

**Ces étapes ne sont pas du code. Elles sont obligatoires et leur ordre
compte.** Prises à l'envers, elles rendent les credentials illisibles ou
coupent le RAG.

1. **Poser les `DH_*` dans `backend/.env`** (valeurs commentées dans
   `.env.example`) : `DH_CHROMA_PATH`, `DH_DELIVERABLES_DIR`,
   `DH_SFDX_PROJECT_PATH`, `DH_FORCE_APP_PATH`, `DH_AGENTS_DIR`. Les défauts ne
   pointent plus vers `/opt` ni `/var/lib` ; sans ces variables le RAG
   (70 K chunks, 2,4 Go) cherchera un répertoire inexistant. `rag_health_check`
   le signalera au boot au lieu d'échouer en silence.

2. **Poser `CHAT_IP_SALT`.** Sans ce sel, le concierge public refuse tous les
   tours — comportement voulu, mais **coupure fonctionnelle silencieuse** si
   personne ne pose la variable. Elle n'est pas dans `.env.example`.

3. **Migrer les jetons en clair** :
   `python scripts/rotate_encryption_key.py --encrypt-plaintext --apply`.
   Idempotent. Sans cela, tout projet dont le jeton Git est encore en clair
   **cesse de déployer** (`git_token=None` → clone non authentifié). Arrêt net
   et journalisé, pas une corruption — mais à faire avant, pas après.

4. **`alembic stamp <rev>` sur la base de production existante.** `create_all`
   ne tourne plus au boot ; sur une base créée par l'ancien `create_all`,
   `alembic_version` est vide et **le premier `alembic upgrade head`
   échouera**. C'est exactement l'incident qu'annonce PROD-05.

5. **Rotation de clé de chiffrement si souhaitée**, puis poser
   `CREDENTIALS_ENCRYPTION_KEY` dans `.env`. **L'ordre est impératif** : d'abord
   `rotate_encryption_key.py --old-secret-key-derived --new-key <clé> --apply`,
   ensuite la clé dans `.env`, ensuite le redémarrage. L'inverse rend toutes les
   credentials illisibles. Cette clé est désormais **exigée en `DEBUG=False`** :
   le backend refusera de démarrer sans elle.

6. **`SF_ORG_ALIAS` / `SF_USERNAME` / `SF_ORG_ID` / `SF_INSTANCE_URL` restent
   vides** sauf si une org par défaut est réellement voulue. Les laisser vides
   est le comportement sûr : les projets connectés utilisent leurs propres
   credentials, et ce qui n'a pas d'org échoue au lieu d'en emprunter une.

7. **Redémarrer**, puis vérifier `/health` → 200.

---

## 7. Levée du blocage nginx — procédure

**La règle n'a pas été touchée. Elle vit hors du dépôt, dans
`/etc/nginx/sites-enabled/app.digital-humans.fr` sur le VPS. Sa levée appartient
à Sam.** Aucun agent n'a écrit sur le serveur.

Deux faits à connaître avant :

- **La règle bloque tout le routeur, pas la seule route.** C'est
  `location ~ ^/api/agent-tester { return 403; }`, une *location regex*
  prioritaire sur `location /api`. La lever réexpose les 8 routes d'un coup,
  dont `POST /test/{agent}/stream` qui déclenche des exécutions LLM facturées.
  Elles sont désormais toutes authentifiées, mais elles rouvrent ensemble.
- **Le VPS suit cette branche.** Au moment de la rédaction il était sur
  `766a89e`, donc porteur des lots A à F ter mais **pas de LOT-C** : le
  `shell=True` y était encore.

**Procédure, dans cet ordre :**

1. **Déployer puis redémarrer.** `git pull` ne recharge pas Python.
   `systemctl restart digital-humans-backend`, puis vérifier que
   `ActiveEnterTimestamp` est postérieur au pull.

2. **Vérifier que le code corrigé est celui qui *tourne*, pas celui qui est sur
   le disque.** Un worker resté vivant sert l'ancien code. Interroger le backend
   **en contournant nginx** — possible sans lever la règle :
   ```
   curl -s -o /dev/null -w '%{http_code}\n' \
     'http://127.0.0.1:8002/api/agent-tester/org/query?soql=SELECT+Id+FROM+Account'
   ```
   **Attendu : `401`.** Si `200`, `400` ou `500` → l'ancien code tourne,
   **ne pas lever la règle**.

3. **Vérifier le chemin authentifié**, même appel avec un `Bearer` valide.
   `200` → nominal. **`503` citant `org_alias` → normal, et c'est une preuve que
   le nouveau code tourne** (l'ancien n'avait aucune branche 503) : il manque
   `SF_ORG_ALIAS` dans `.env`. `401` avec jeton valide → problème
   d'authentification, à traiter avant.

4. **Rejouer l'injection sur la machine, cible inoffensive.** Créer
   `/tmp/temoin-lot-c.txt`, appeler en direct sur `127.0.0.1:8002` avec
   `soql=SELECT Id FROM Account" ; rm -f /tmp/temoin-lot-c.txt ; echo "`, puis
   vérifier que le témoin **existe toujours**. C'est le seul contrôle qui teste
   le binaire en production plutôt que le dépôt.

5. **Ne pas se fier au `grep` sur le VPS — il rendra un faux positif.** Le dépôt
   déployé contient trois sauvegardes **non versionnées** :
   ```
   backend/app/services/pm_orchestrator_service_v2.py.pre-async-sfdx   (6 × shell=True)
   backend/app/services/pm_orchestrator_service_v2.py.pre-tache1
   backend/app/services/pm_orchestrator_service_v2.py.pre-phaseprefix
   ```
   Inertes (extension non `.py`, jamais importées, absentes de git), mais
   `grep -rn "shell=True" backend/app` les renverra **même après un déploiement
   réussi** et fera croire à un correctif non appliqué. Utiliser
   `--include='*.py'`, ou les supprimer.

6. **Alors seulement** retirer le bloc `location ~ ^/api/agent-tester`,
   `nginx -t`, `systemctl reload nginx`, puis revérifier depuis Internet :
   `401` sans jeton sur `/api/agent-tester/agents`.

7. **Prévoir le retour arrière** : remettre les 3 lignes et `reload` suffit.
   Garder la fenêtre courte entre le retrait et la vérification externe.

---

## 8. Commits

| SHA | Objet |
|---|---|
| `d0f33c0` | outillage — `conftest.py` sur PostgreSQL (JSONB non compilable par SQLite) |
| `e316391` | LOT-D — UC perdus sur lot impair, `None` au lieu d'un tuple |
| `179e1fd` | LOT-A — frontière payante posée côté serveur |
| `c568523` | LOT-F — XSS contenu d'agent, JWT hors URL, services morts |
| `2c679d4` | LOT-F bis — inscription : jeton sous la mauvaise clé |
| `466a0d4` | LOT-B — authentification et cloisonnement sur 8 routeurs |
| `4e9ba34` | LOT-F ter — lien nu vers `/render`, 401 depuis LOT-B |
| `dc859ab` | LOT-E — un seul `.env`, chemins dérivés, rotation exécutable |
| `f66d644` | LOT-A bis — contournements de `retry_routes`, flux SSE rouvert |
| `90a5694` | LOT-B bis — routeur `audit` authentifié et cloisonné |
| `766a89e` | LOT-E bis — org sans identité en dur, jetons en clair refusés |
| `2cdf280` | LOT-C — plus de `shell=True`, `agent-tester` authentifié |
| `d3371fd` | LOT-F quater — `fetch` nus vers `agent-tester`, 401 depuis LOT-C |
| `7367c09` | LOT-G — sessions temps réel, `/health` profond, boot sans `create_all` |
| `33559ad` | LOT-A ter — le flux SSE n'immobilise plus de connexion |

---

## 9. Suite

`prompt-audit.md` est à rejouer à l'identique sur les quatre modèles une fois
cette vague déployée. C'est le seul moyen de vérifier que les correctifs
tiennent : l'expérience des P0–P12 montre que quatre correctifs déclarés
« corrigés » ne l'étaient pas, et cette vague en a confirmé deux de plus qui ne
l'étaient pas non plus (P8, P12).

**Hors périmètre, décision du 21/08 confirmée** : la reprise des builds entre
workers se compte en semaines et conditionne le palier 100 clients. Elle reste
hors vague 1.

Les 36 constats majeurs de la vague 2 n'ont pas été entamés.
