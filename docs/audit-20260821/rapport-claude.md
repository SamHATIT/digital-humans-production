

# Rapport d'audit — Digital·Humans

## Verdict d'ouverture

**Non, ce code ne peut pas partir en production le 1er octobre en l'état.** Trois problèmes sont bloquants : (1) les secrets sont absents de la rotation mais présents en clair dans au moins deux chemins (credentials Git, cookie JWT sans flag `HttpOnly`), (2) l'isolation entre locataires est insuffisante — un utilisateur authentifié peut accéder aux projets, exécutions et livrables d'un autre utilisateur sur plusieurs routes, et (3) la base de données n'a aucune protection contre les connexions saturées sous charge (pool de 40 pour un worker ARQ qui ouvre des sessions synchrones sans les limiter). Les correctifs sont ciblés et applicables — il n'y a pas de refonte à faire — mais ils nécessitent un arbitrage humain immédiat sur les priorités sécurité et multi-tenant.

---

## 1. Ce qui casse en production

### CRASH-01 · Fuite de sessions DB dans les workers ARQ — **bloquant**

**Fichier :** `backend/app/services/llm_service.py`, lignes 107-126  
**Fichier :** `backend/app/services/budget_service.py`, ligne 175  

**Ce qui se passe :** `generate_llm_response` ouvre une `SessionLocal()` quand `execution_id` est fourni sans `db` dans kwargs (le cas normal depuis le worker ARQ). Le `BudgetService.record_cost` appelle `db.commit()`. Mais si une exception survient entre l'ouverture et le `finally`, la session peut rester ouverte. Plus grave : la session auto-créée n'est pas fermée en cas d'exception dans `router.generate()` car le `finally` ne couvre que la fin de la fonction, pas le bloc `try` entier — le `return response` court-circuite le `finally` dans le chemin nominal, mais un `raise` dans `check_budget` laisse la session pendante car `auto_created_db` n'est `True` que si le code atteint la ligne 119.

**Déclencheur :** Toute exécution SDS qui dépasse le budget ou dont le LLM timeout — sous charge, les 40 connexions du pool sont épuisées en quelques minutes.

**Correctif :**
```python
# llm_service.py — restructurer le bloc try/finally
db_session = None
auto_created_db = False
try:
    execution_id = clean_kwargs.get("execution_id")
    if execution_id:
        from app.database import SessionLocal
        db_session = SessionLocal()
        auto_created_db = True
    # ... tout le reste du code existant, en utilisant db_session ...
    return response
finally:
    if auto_created_db and db_session:
        try:
            db_session.close()
        except Exception:
            pass
```

**Effort :** 1h

---

### CRASH-02 · `_call_llm` retourne `None` quand le fallback OpenAI n'est pas configuré — **bloquant**

**Fichiers :** `backend/agents/roles/salesforce_business_analyst.py` lignes 186-202, `salesforce_trainer.py` lignes 205-215, `salesforce_devops.py` lignes 133-165, `salesforce_pm.py` lignes 183-195

**Ce qui se passe :** Plusieurs agents ont des méthodes `_call_llm` qui appellent `generate_llm_response` dans le chemin `LLM_SERVICE_AVAILABLE`, puis retournent le tuple. Mais si `LLM_SERVICE_AVAILABLE` est `False` (aucun fallback), la méthode se termine sans `return` — elle retourne implicitement `None`. Le code appelant tente ensuite de déstructurer ce `None` : `content, tokens_used, ... = self._call_llm(...)` → `TypeError: cannot unpack non-iterable NoneType object`.

**Cas le plus grave :** `BusinessAnalystAgent._call_llm` n'a aucune branche `else` après le `if LLM_SERVICE_AVAILABLE`. Même chose pour `TrainerAgent._call_llm` et `PMAgent._call_llm`.

**Déclencheur :** Environnement où `app.services.llm_service` n'est pas importable (test, CI, déploiement partiel).

**Correctif :** Ajouter un `raise` ou un retour d'erreur explicite à la fin de chaque méthode `_call_llm` :
```python
# À la fin de chaque _call_llm qui n'a pas de branche else
raise RuntimeError(f"[{self.agent_id}] No LLM provider available")
```

**Effort :** 30 min (11 agents à vérifier, 5 affectés)

---

### CRASH-03 · `BusinessAnalystAgent._parse_response` utilise `parsed_content` et `uc_count` avant affectation — **bloquant**

**Fichier :** `backend/agents/roles/salesforce_business_analyst.py`, lignes 217-243

**Ce qui se passe :** La méthode `_parse_response` déclare `parsed_content` et `uc_count` à l'intérieur d'un bloc `if 'results' in parsed_content` (ligne 230). Si le JSON n'est pas en mode batch (pas de clé `results`), ces variables ne sont jamais assignées. Le `return parsed_content, uc_count` à la fin du `try` lève un `UnboundLocalError`.

**Correctif :**
```python
def _parse_response(self, content, br_id, br_ids, batch_mode):
    parsed_content = None  # ADD
    uc_count = 0           # ADD
    try:
        if JSON_CLEANER_AVAILABLE:
            parsed_content, parse_error = clean_llm_json_response(content)
            if parsed_content is None:
                raise json.JSONDecodeError(parse_error or "Parse error", content, 0)
        # else: parsed_content stays None → caught below
        if parsed_content and 'results' in parsed_content and isinstance(parsed_content['results'], list):
            # batch handling...
            uc_count = len(all_use_cases)
        elif parsed_content:
            uc_count = len(parsed_content.get('use_cases', []))
        return parsed_content, uc_count
    except json.JSONDecodeError as e:
        return {"raw": content, "parse_error": str(e)}, 0
```

**Effort :** 20 min

---

### CRASH-04 · `DevOpsAgent.run` ne dispatch jamais le mode `deploy` — **majeur**

**Fichier :** `backend/agents/roles/salesforce_devops.py`, lignes 99-112

**Ce qui se passe :** La méthode `run()` vérifie `if mode == "spec"` et retourne le résultat, mais la branche `else` pour `mode == "deploy"` n'existe pas — la méthode se termine implicitement par `None`. La méthode `_execute_deploy` existe (ligne 122) mais n'est jamais appelée.

**Correctif :**
```python
try:
    if mode == "spec":
        return self._execute_spec(input_content, execution_id, project_id)
    elif mode == "deploy":          # ADD
        return self._execute_deploy(input_content, execution_id, project_id)  # ADD
except Exception as e:
```

**Effort :** 10 min

---

### CRASH-05 · `generate_build_v2` dans `salesforce_admin.py` — `cost_usd` retourné sans être stocké — **mineur**

**Fichier :** `backend/agents/roles/salesforce_admin.py`, ligne 279

```python
response.get("cost_usd", 0.0)  # valeur jetée, jamais assignée
```

Pas de crash mais le coût n'est pas tracé. Assigner à une variable et l'inclure dans le résultat.

**Effort :** 5 min

---

## 2. Ce qui ne tient pas ensemble

### INTEG-01 · `agents/__init__.py` déclare 9 agents, le code en a 11 — **mineur**

**Fichier :** `backend/agents/__init__.py`

Le docstring liste 9 agents (manquent Sophie et Emma). Cosmétique mais trompeur pour un nouveau développeur.

**Effort :** 5 min

---

### INTEG-02 · `build_sds` importé par `sys.path.insert` dans 3 fichiers différents — **mineur**

**Fichiers :** `backend/agents/roles/salesforce_research_analyst.py` ligne 485, `backend/app/api/routes/sds_versions.py` lignes 18-21, `backend/app/api/routes/orchestrator/execution_routes.py` lignes 204-212

Le module `build_sds` n'est pas dans le package Python — il est importé par manipulation de `sys.path` vers `tools/`. Ça fonctionne mais c'est fragile : si le répertoire `tools/` est absent (conteneur Docker mal monté), l'import échoue silencieusement et le SDS ne peut pas être rendu.

**Correctif recommandé :** Créer un lien symbolique ou un package `tools_bridge` importable proprement.

**Effort :** 1h

---

### INTEG-03 · Chemin absolu résiduel `/opt/digital-humans/...` dans `config.py` — **mineur** (P2 partiel)

**Fichier :** `backend/app/config.py`, lignes 49-51

```python
CHROMA_PATH: Path = Path(os.environ.get("DH_CHROMA_PATH") or "/opt/digital-humans/rag/chromadb_data")
RAG_ENV_PATH: Path = Path(os.environ.get("DH_RAG_ENV_PATH") or "/opt/digital-humans/rag/.env")
```

Les chemins de fallback sont des absolus codés en dur. Le P2 déclare le problème corrigé mais ces deux lignes restent. En environnement conteneurisé ou cloud, ChromaDB ne sera pas trouvé sans la variable d'environnement explicite.

**Effort :** 10 min — changer les fallbacks en chemins relatifs au `PROJECT_ROOT`

---

## 3. Sécurité

### SEC-01 · Isolation multi-tenant absente sur 14+ routes — **bloquant**

**Fichiers principaux :** 
- `backend/app/api/routes/orchestrator/build_routes.py` : `get_build_tasks`, `get_build_phases` — filtrent par `execution_id` mais ne vérifient pas que l'execution appartient au `current_user`. `verify_execution_access` est appelé mais la vérification remonte au projet via un JOIN qui n'est pas fait dans `get_build_phases` (utilise du SQL brut sans filtre user).
- `backend/app/api/routes/deliverables.py` : toutes les routes (`get_deliverable`, `get_execution_deliverables`, etc.) n'ont aucune vérification d'appartenance. Un utilisateur A peut lire les livrables d'un utilisateur B en devinant l'ID.
- `backend/app/api/routes/artifacts.py` : même problème — aucune des 15+ routes ne vérifie l'appartenance utilisateur.
- `backend/app/api/routes/quality_gates.py` : idem.
- `backend/app/api/routes/quality_dashboard.py` : utilise du SQL brut sans filtre utilisateur.

**Ce qui se passe concrètement :** Un utilisateur avec un compte Free peut appeler `GET /api/deliverables/42/full` et obtenir le SDS complet d'un autre client. C'est une fuite de données commerciale et contractuelle.

**Correctif :** Ajouter un middleware ou une dépendance FastAPI qui vérifie `execution.project.user_id == current_user.id` sur toute route qui accepte un `execution_id` ou un `deliverable_id`. Le pattern existe déjà dans `_helpers.py:verify_execution_access` — il faut l'appliquer systématiquement.

**Effort :** 4h (14 fichiers de routes à auditer et protéger)

---

### SEC-02 · Token JWT stocké en cookie sans `HttpOnly` — **bloquant**

**Fichier :** `frontend/src/services/api.ts`, lignes 10-15

```typescript
function setTokenCookie(token: string) {
  const expires = new Date();
  expires.setDate(expires.getDate() + TOKEN_COOKIE_DAYS);
  const secure = location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `token=${token}; expires=${expires.toUTCString()}; path=/; SameSite=Lax${secure}`;
}
```

Le cookie n'a pas le flag `HttpOnly`. Un XSS (même via une dépendance npm compromise) peut lire le JWT et l'exfiltrer.

**Correctif :** Le cookie doit être posé côté serveur avec `HttpOnly; Secure; SameSite=Strict`. Si le seul usage est nginx `auth_request`, le frontend n'a pas besoin de le lire.

**Effort :** 2h (modifier le login backend pour poser le cookie dans la réponse HTTP, retirer `setTokenCookie` du frontend)

---

### SEC-03 · Credentials Git potentiellement en clair dans `project_credentials` — **majeur**

**Fichier :** `backend/app/services/jordan_deploy_service.py`, lignes 79-108

Le code tente de déchiffrer le token Git avec `decrypt_credential`, mais le fallback est :
```python
if brut.startswith(("ghp_", "github_pat_", "glpat-")):
    git_token = brut  # ancien format, deja en clair
```

Cela signifie que des tokens GitHub sont stockés en clair dans la colonne `encrypted_value`. C'est un défaut de migration : les anciens tokens n'ont jamais été chiffrés. En cas de fuite de la base (backup non chiffré, accès DBA), tous ces tokens sont compromis.

**Correctif :** Script de migration one-shot qui chiffre tous les tokens en clair existants avec `encrypt_credential`.

**Effort :** 1h

---

### SEC-04 · Concierge chat rate-limit insuffisant — **majeur**

**Fichier :** `backend/app/api/routes/concierge_routes.py`, ligne 56

```python
@limiter.limit("30/hour")  # per IP
```

30 appels/heure par IP pour un endpoint public qui appelle Claude Sonnet. Avec un réseau de proxies, un attaquant peut générer des milliers d'appels facturés. Le budget quotidien de $20 (`DAILY_BUDGET_USD = 20.0` dans `sophie_concierge_service.py`) est le seul garde-fou, mais il est vérifié sur `SUM(cost_usd)` de `chat_logs` — or `cost_usd` est stocké en micro-cents (entier), et la conversion `int((response.cost_usd or 0) * 1_000_000)` peut être 0 si le routeur ne retourne pas `cost_usd` (cas du fallback).

**Correctif :** Réduire à `10/hour` par IP et ajouter un compteur de tokens journalier en plus du compteur de coût.

**Effort :** 30 min

---

### SEC-05 · `SECRET_KEY` auto-générée en dev change à chaque restart — **mineur** mais documenté

**Fichier :** `backend/app/config.py`, lignes 69-82

En mode `DEBUG=True`, si `SECRET_KEY` n'est pas dans `.env`, une clé est auto-générée. Tous les JWT deviennent invalides au redémarrage. C'est intentionnel pour le dev, mais la condition `not self.DEBUG` pour lever l'erreur en prod est correcte. **Ce point est bien géré.**

---

### SEC-06 · CORS permet `http://72.61.161.222` et `http://srv1064321.hstgr.cloud` — **majeur**

**Fichier :** `backend/app/main.py`, lignes 29-39

Les origines CORS incluent des IP et hostnames non-HTTPS, sans wildcard mais sans chiffrement. En production, seules les origines HTTPS devraient être autorisées.

**Effort :** 10 min — retirer les origines HTTP, ne garder que les domaines HTTPS de production.

---

## 4. Cohérence des paliers

### TIER-01 · Le palier gratuit peut déclencher la séquence SDS complète — **bloquant**

**Fichier :** `backend/app/models/subscription.py`, lignes 93-127

Le modèle déclare :
```python
SubscriptionTier.FREE: {
    "features": {
        "br_extraction": False,
        "uc_generation": False,
        "solution_design": False,
        "sds_document": False,
        ...
    }
}
```

Mais **aucune vérification côté serveur** n'empêche un utilisateur Free de lancer `POST /api/pm-orchestrator/execute`. La route `start_execution` dans `execution_routes.py` vérifie uniquement que `pm` est dans `selected_agents` — elle ne vérifie pas le tier de l'utilisateur.

**Ce qui se passe :** Un utilisateur Free peut lancer une exécution SDS complète (11 agents, ~$20 de coûts LLM), produire un SDS professionnel, et ne jamais payer.

**Correctif :** Ajouter un décorateur `@require_feature("sds_document")` sur `start_execution`, ou un check explicite du tier dans la route. Le décorateur existe déjà dans `feature_access.py` mais n'est appliqué nulle part.

**Effort :** 30 min

---

### TIER-02 · Le palier Pro ne devrait pas pouvoir déclencher le BUILD — vérifié côté middleware

**Fichier :** `backend/app/middleware/build_enabled.py`

Le middleware `BuildEnabledMiddleware` bloque les routes BUILD quand `build_enabled=false` (profil `freemium`). Mais cette vérification est basée sur le **profil de déploiement** (cloud/freemium), pas sur le **tier de l'utilisateur**. En profil `cloud`, un utilisateur Pro peut lancer le BUILD alors que `subscription.py` déclare `build_phase: False` pour Pro.

Le `BuildPhaseService.prepare_build_phase` ne vérifie pas non plus le tier — il vérifie seulement `project.status == ProjectStatus.SDS_APPROVED`.

**Correctif :** Ajouter `if not current_user.has_build_access: raise HTTPException(403)` dans `start_build_phase`.

**Effort :** 15 min

---

## 5. Passage à l'échelle

### Jugement global

Le code **ne monte pas en charge** au-delà de ~20 utilisateurs simultanés. Les goulots sont, par ordre de criticité :

1. **Pool PostgreSQL (40 connexions max)** : Chaque exécution SDS ouvre 7-12 sessions (une par appel LLM via `generate_llm_response` auto-créant des sessions, plus l'orchestrateur, plus les workers ARQ). 5 SDS simultanés saturent le pool.

2. **Worker ARQ single-process** : `max_jobs = 10` dans `worker.py`, mais les jobs SDS durent 3-15 minutes chacun. Avec 10 slots et un seul worker process, la queue s'accumule rapidement.

3. **ChromaDB monolithique** : Un seul répertoire sur disque, pas de réplication. Les queries RAG sont synchrones et bloquent le thread appelant.

4. **Appels LLM synchrones dans les agents** : Tous les agents font `asyncio.to_thread(agent.run, task_data)` — ça débloque l'event loop mais consomme un thread du pool Python par agent. Le pool par défaut est de 40 threads (CPython).

5. **Notifications via PostgreSQL LISTEN/NOTIFY** : Fonctionne bien jusqu'à ~100 connexions WebSocket simultanées. Au-delà, le overhead par notification devient significatif.

### Configuration par palier

#### 10 clients (situation actuelle)

- **Infrastructure :** 1 VPS (4 vCPU, 8 Go RAM) — suffisant
- **Pool DB :** Réduire `pool_size=10, max_overflow=10` (le 20/20 actuel est trop agressif pour 1 serveur)
- **ARQ workers :** 1 process, `max_jobs=5`
- **ChromaDB :** Local, tel quel
- **Ce qui doit être fait avant :** Corriger CRASH-01 (fuite de sessions), SEC-01 (isolation multi-tenant), TIER-01 (gate free→SDS)

#### 100 clients

- **Infrastructure :** 2 VPS — 1 pour l'API/frontend, 1 pour les workers ARQ + ChromaDB
- **Pool DB :** `pool_size=20, max_overflow=30` sur l'API, `pool_size=10, max_overflow=10` sur le worker
- **ARQ workers :** 2 processes, `max_jobs=5` chacun, sur une queue Redis dédiée
- **ChromaDB :** Migrer vers un service séparé (Chroma server mode ou Qdrant)
- **Nginx :** Ajouter un cache en amont pour les assets statiques et les endpoints en lecture seule
- **Ce qui doit être refait :** Séparer la base de données du serveur applicatif (RDS ou PG managé)

#### 1 000 clients

- **Infrastructure :** Cluster Kubernetes ou 4-6 VPS spécialisés
  - 2 pods API (derrière un LB)
  - 3 workers ARQ (queue Redis)
  - 1 PostgreSQL managé (RDS)
  - 1 Redis managé (ElastiCache)
  - 1 service vectoriel (Qdrant/Weaviate)
- **Pool DB :** PgBouncer en frontal, `pool_size=5` par pod (PgBouncer gère le multiplexage)
- **ChromaDB :** Remplacer par Qdrant (réplication, sharding, API HTTP native)
- **LLM calls :** Ajouter un circuit breaker global (pas par agent) avec file d'attente Redis pour lisser les pics
- **Ce qui doit être refait :** 
  - Sessions DB : passer à un pattern `async with get_db_session()` au lieu du générateur synchrone
  - Notification service : migrer de PG LISTEN/NOTIFY vers Redis Pub/Sub
  - File storage : migrer les outputs de `/var/lib/digital-humans/` vers S3/MinIO

#### 10 000 clients

- **Limites architecturales non corrigeables en ajoutant des machines :**
  1. **SQLAlchemy synchrone partout** : L'ORM est synchrone, wrappé dans `asyncio.to_thread`. À 10K clients, le coût du context-switching thread ↔ event-loop devient prohibitif. Il faudrait migrer vers SQLAlchemy AsyncSession + asyncpg.
  2. **Orchestrateur monolithique** : `PMOrchestratorServiceV2` (3800+ lignes) gère tout le workflow en séquentiel dans un seul job ARQ. À 10K clients, il faut un orchestrateur distribué (Temporal.io ou Prefect) avec des steps indépendants.
  3. **État d'exécution dans PostgreSQL** : `execution.agent_execution_status` est un JSONB muté à chaque progress update. Sous charge, c'est un hotspot de contention sur la ligne. Il faut un store spécialisé (Redis + event sourcing).
  4. **ChromaDB embarqué** : Même en mode serveur, ChromaDB n'est pas conçu pour du multi-tenant à grande échelle. Migrer vers Qdrant ou Pinecone.

- **Coût d'inférence à 10K clients :**
  - Hypothèse : 10K clients, 20% actifs/mois, 1.5 SDS/mois/client actif, 0.3 BUILD/mois/client actif
  - SDS : 2000 clients × 1.5 SDS × ~$0.15/SDS (Sonnet) = **$450/mois** (hors Marcus en Opus)
  - Marcus Opus : 2000 × 1.5 × ~$0.80 = **$2400/mois**
  - BUILD : 600 BUILDs × ~$0.40 = **$240/mois**
  - **Total LLM : ~$3090/mois**
  - Avec le tier Team à 1490€/mois × 200 clients Team (2%) = **298 000€/mois de revenus** vs **$3090 de coûts LLM** → marge LLM > 98%
  - Le poste LLM n'est pas le facteur limitant. C'est l'infrastructure (compute, DB, réseau) qui dominera.

---

## 6. Ce qui manque pour être exploitable

### OPS-01 · Pas de health check de la base de données — **majeur**

**Fichier :** `backend/app/main.py`, ligne 177

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

Le health check retourne toujours `healthy` sans vérifier PostgreSQL ni Redis. Si la DB est down, l'API continue de répondre 200 au load balancer et les requêtes échouent en 500 sur chaque appel.

**Correctif :** Ajouter un `SELECT 1` et un ping Redis dans le health check.

**Effort :** 30 min

---

### OPS-02 · Pas de migration Alembic automatisée au démarrage — **majeur**

**Fichier :** `backend/app/main.py`, ligne 25

```python
Base.metadata.create_all(bind=engine)
```

`create_all` ne gère pas les migrations — il crée les tables manquantes mais ne modifie jamais les colonnes existantes. Les migrations Alembic doivent être exécutées manuellement. En production, un schéma désynchronisé cause des erreurs silencieuses (colonnes NULL non attendues, contraintes manquantes).

**Effort :** 1h — ajouter un `alembic upgrade head` dans le startup ou le script de déploiement

---

### OPS-03 · Pas de métriques Prometheus/StatsD — **majeur**

Le code produit des logs structurés JSON (bien fait via `logging_config.py`) mais aucune métrique n'est exportée : pas de compteur de requêtes, pas d'histogramme de latence LLM, pas de gauge sur le pool DB. En production, le premier signe d'un problème sera un utilisateur qui se plaint, pas une alerte.

**Effort :** 4h pour intégrer `prometheus-fastapi-instrumentator` + compteurs custom sur les appels LLM

---

## 7. Dette technique qui coûtera cher

### DEBT-01 · `pm_orchestrator_service_v2.py` — 3800+ lignes, logique SDS + BUILD + HITL + CR mélangés — **majeur**

**Fichier :** `backend/app/services/pm_orchestrator_service_v2.py`

Le P4 (split du fat controller des routes) a été fait correctement, mais le **service** reste monolithique. `execute_workflow` fait 400 lignes. `resume_from_architecture_validation` duplique 50% de la logique de `execute_workflow`. `_merge_patched_section` est défini au niveau module. `_execute_from_phase4` est un helper de 180 lignes extrait mais toujours dans la même classe.

**Impact :** Tout changement dans le workflow SDS risque de casser le resume, le retry, ou le CR flow. La couverture de test ne couvre pas les chemins combinatoires (resume + architecture_validation + retry).

**Effort estimé pour une extraction propre :** 16h (pas une refonte — une extraction de 4-5 méthodes en services séparés)

---

### DEBT-02 · `BaseAgent` (P10) partiellement adopté — agents avec `_call_llm` dupliqué — **mineur**

**Fichiers :** Tous les agents dans `backend/agents/roles/`

Le `BaseAgent` de P10 fournit un `_call_llm` standard, mais 6 agents sur 11 le surchargent avec leur propre version (parfois identique). La factorisation est déclarée faite mais n'est pas complète — les agents `DataMigrationAgent`, `LWCDeveloperAgent`, `QATesterAgent`, `DevOpsAgent` ont chacun leur propre `_call_llm` qui duplique la logique de fallback OpenAI et le tracking de coût.

**Impact :** Tout changement dans la politique de routing LLM doit être propagé dans 6 endroits.

**Effort :** 4h pour migrer les 6 agents vers `BaseAgent._call_llm`

---

### DEBT-03 · Double source de vérité pour les agents — `AGENT_CONFIG` dans 3 fichiers — **mineur** (P10 partiel)

**Fichiers :** 
- `backend/config/agents_registry.yaml` (source officielle)
- `backend/app/services/pm_orchestrator_service_v2.py` lignes 42-55 (redéclaré)
- `backend/app/services/agent_executor.py` lignes 236-257 (redéclaré)

Le registre YAML est la source de vérité (B-2d), mais deux dictionnaires `AGENT_CONFIG` parallèles existent encore dans l'orchestrateur et l'exécuteur. Le registre est utilisé par `agents_registry.py` pour les résolutions d'alias, mais le dispatch réel des agents passe par les dicts locaux.

**Effort :** 2h pour migrer les deux consommateurs vers `agents_registry.get_agent()`

---

## Vérification des correctifs déclarés

| Réf | Statut déclaré | Verdict |
|-----|----------------|---------|
| P0 | corrigé | **Vérifié partiellement.** `asyncio.to_thread` est utilisé dans les routes (`execution_routes.py` lignes 51, 78), mais `generate_llm_response` crée encore des sessions synchrones dans le thread principal quand appelé depuis un agent (pas depuis une route). Le problème est atténué mais pas éliminé. |
| P1 | corrigé | **Vérifié.** `pm.py` v1 n'existe plus. Seul `pm_orchestrator_service_v2.py` subsiste. |
| P2 | corrigé | **Partiel.** 2 chemins absolus résiduels dans `config.py` (ChromaDB, RAG .env). Voir INTEG-03. |
| P3 | corrigé | **Vérifié.** Les agents sont importés directement, `subprocess.run` n'est plus utilisé dans le chemin nominal. Le fallback subprocess existe encore dans `agent_executor.py` pour les agents non migrés, mais `MIGRATED_AGENTS` couvre les 11. |
| P4 | partiel | **Confirmé partiel.** Les routes sont bien splitées (6 fichiers), mais le service reste monolithique (3800 lignes). Voir DEBT-01. |
| P5 | corrigé | **Vérifié.** Logs JSON structurés via `logging_config.py`, contextvars pour execution_id/agent_id. |
| P6 | corrigé | **Vérifié.** `llm_routing.yaml` est la source unique. `LLMRouterService` charge le YAML au démarrage. |
| P7 | corrigé | **Vérifié.** `get_db()` a un `rollback()` dans le `except`. `retry_routes.py` a un `try/except` avec `db.rollback()`. |
| P8 | corrigé | **Partiel.** La rotation des secrets est documentée dans `encryption.py` mais le script `scripts/rotate_encryption_key.py` mentionné dans le docstring n'existe pas. Les tokens Git en clair (SEC-03) n'ont pas été migrés. |
| P9 | corrigé | **Non vérifiable dans ce code.** `safe_content()` n'apparaît nulle part — possiblement renommé ou supprimé. |
| P10 | partiel | **Confirmé partiel.** `BaseAgent` existe et est hérité par les 11 agents, mais `_call_llm` est surchargé dans 6 d'entre eux. Voir DEBT-02. |
| P11 | corrigé | **Vérifié.** `rag_health_check()` est appelé au startup (`main.py` ligne 169). Les erreurs de collection sont loggées à ERROR. |
| P12 | partiel | **Confirmé partiel.** Le code utilise une variable `ANTHROPIC_API_KEY` et un `.env` chargé par `dotenv` au startup. Mais `rag_service.py` tente de lire `OPENAI_API_KEY` depuis un second fichier `.env` dans `/opt/digital-humans/rag/.env` (ligne 89-93). Ce second fichier est un vestige de P12. |

---

## Ce qui est bien fait

- **State Machine d'exécution** (`execution_state.py`) : Propre, avec table de transitions explicite, row-level locking, historique des transitions. Design solide.
- **Logging structuré** (`logging_config.py`) : JSON + contextvars. Excellente base pour un ELK/Loki.
- **Audit middleware** (`audit_middleware.py`) : Capture toutes les requêtes HTTP avec timing, IP, user-agent. Bien intégré.
- **Budget service** (`budget_service.py`) : Circuit breaker + pricing YAML. Architecture saine.
- **Agents registry** (`agents_registry.yaml` + `agents_registry.py`) : Source unique avec résolution d'alias, lazy loading, cache LRU. Bien pensé.
- **Prompt service** (`prompt_service.py`) : Séparation prompts YAML / code Python. Maintenable.
- **Garde anti-production** (`sf_admin_service.py` `GARDE-PROD-001`) : Liste blanche de marqueurs non-production. Règle métier correctement implémentée.

---

## Feuille de route

### Avant le 1er octobre (bloquants)

| Réf | Effort | Description |
|-----|--------|-------------|
| SEC-01 | 4h | Isolation multi-tenant sur toutes les routes (deliverables, artifacts, quality_gates, quality_dashboard) |
| TIER-01 | 30min | Gate palier gratuit → exécution SDS (vérifier `has_feature("sds_document")`) |
| TIER-02 | 15min | Gate palier Pro → BUILD (vérifier `has_build_access`) |
| SEC-02 | 2h | Cookie JWT → `HttpOnly; Secure; SameSite=Strict` posé côté serveur |
| CRASH-01 | 1h | Fuite de sessions DB dans `generate_llm_response` |
| CRASH-02 | 30min | `_call_llm` retourne `None` dans 5 agents |
| CRASH-03 | 20min | `UnboundLocalError` dans `BusinessAnalystAgent._parse_response` |
| CRASH-04 | 10min | `DevOpsAgent.run` ne dispatch pas le mode `deploy` |
| OPS-01 | 30min | Health check DB + Redis |
| SEC-06 | 10min | Retirer les origines CORS HTTP |

**Total estimé : ~9h15 de travail agent, ~2h d'arbitrage humain.**

### Dans les 30 jours

| Réf | Effort | Description |
|-----|--------|-------------|
| SEC-03 | 1h | Migration des tokens Git en clair vers chiffré |
| SEC-04 | 30min | Rate-limit concierge → 10/h + compteur tokens |
| OPS-02 | 1h | Automatiser `alembic upgrade head` au déploiement |
| OPS-03 | 4h | Intégrer Prometheus |
| INTEG-02 | 1h | Rendre `build_sds` importable proprement |
| INTEG-03 | 10min | Corriger les 2 chemins absolus résiduels |
| DEBT-02 | 4h | Migrer les 6 agents vers `BaseAgent._call_llm` |
| DEBT-03 | 2h | Éliminer les `AGENT_CONFIG` dupliqués |
| P12 | 30min | Supprimer le second `.env` RAG et unifier sur une seule source |

### Plus tard (après le lancement)

| Réf | Effort | Description |
|-----|--------|-------------|
| DEBT-01 | 16h | Extraction de `PMOrchestratorServiceV2` en 4-5 services ciblés |
| SCALE | variable | Migration AsyncSession, PgBouncer, service vectoriel dédié — seulement si le trafic le justifie |