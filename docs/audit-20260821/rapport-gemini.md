Voici l'audit de la plateforme Digital·Humans.

**Verdict d'ouverture**
Ce code **ne peut pas** partir en production le 1er octobre en l'état. L'architecture globale est solide, l'approche base-de-données-d'abord pour les livrables est une excellente décision pour la résilience, mais **trois failles de sécurité critiques** (dont une injection de commande et un contournement du modèle payant) exigent un correctif immédiat. Si ces trois points (SEC-01, SEC-02, BIZ-01) sont résolus par vos agents, le lancement est viable.

---

### 1. Ce qui casse en production

**SEC-01 | Injection de commandes système via SOQL**
* **Gravité :** **Bloquant**
* **Emplacement :** `backend/app/api/routes/agent_tester.py`, ligne 45
* **Scénario réel :** L'endpoint `GET /api/agent-tester/org/query?soql=...` prend l'entrée utilisateur et l'injecte directement dans un `subprocess.run(f'sf data query --query "{soql}"...', shell=True)`. Un attaquant envoie `soql="; rm -rf / ; "` et prend le contrôle total du serveur ou détruit les données.
* **Correctif :** Supprimer `shell=True` et passer les arguments sous forme de liste.
```python
result = subprocess.run(
    ["sf", "data", "query", "--query", soql, "--target-org", salesforce_config.org_alias, "--json"],
    capture_output=True, text=True
)
```
* **Effort :** 0.5h

**DATA-01 | Transactions non sécurisées dans le Change Request Service**
* **Gravité :** **Majeur**
* **Emplacement :** `backend/app/services/change_request_service.py`, lignes 107 et 132 (`analyze_impact`), ligne 241 (`process_change_request`).
* **Scénario réel :** Un `self.db.commit()` est appelé directement. Si une erreur survient juste après (ou pendant le commit lui-même), aucune clause `except` ne déclenche de `self.db.rollback()`. La session SQLAlchemy devient "empoisonnée" (PendingRollbackError), ce qui fera planter toutes les requêtes suivantes de ce worker jusqu'à son redémarrage.
* **Correctif :** Envelopper systématiquement les mutations dans un bloc try/except/rollback.
```python
try:
    cr.status = "analyzed"
    # ... autres attributs
    self.db.commit()
except Exception as e:
    self.db.rollback()
    raise e
```
* **Effort :** 1h

---

### 2. Ce qui ne tient pas ensemble (Incohérences)

**CONF-01 | Identifiants Salesforce codés en dur dans la classe de base**
* **Gravité :** **Majeur**
* **Emplacement :** `backend/app/salesforce_config.py`, lignes 14 à 18
* **Scénario réel :** Bien que vous ayez ajouté le paramétrage par projet (`SalesforceConfig.from_project`), la classe définit des valeurs par défaut codées en dur (`shatit.1f62a5011548@agentforce.com`). Si un projet échoue à charger ses propres identifiants, le code retombera sur cette org de test, causant des fuites de données croisées ou des déploiements sur la mauvaise organisation.
* **Correctif :** Remplacer ces valeurs par `None` ou des variables d'environnement explicites, et lever une exception si elles sont absentes.
* **Effort :** 0.5h

**MISS-01 | Script de génération de blog manquant**
* **Gravité :** **Mineur**
* **Emplacement :** `backend/app/api/routes/blog.py`, ligne 39
* **Scénario réel :** L'endpoint `POST /generate-batch` tente de lancer `scripts/blog_generator.py` via `subprocess`. Ce script ne figure pas dans votre arborescence. L'appel échouera systématiquement.
* **Correctif :** Ajouter le script dans le dépôt ou désactiver cette route si elle n'est pas prévue pour la V1.
* **Effort :** 0.5h

---

### 3. Sécurité & 4. Cohérence des paliers commerciaux

**SEC-02 | Route `agent-tester` totalement ouverte au public**
* **Gravité :** **Bloquant**
* **Emplacement :** `backend/app/api/routes/agent_tester.py`, ligne 15
* **Scénario réel :** Le routeur `APIRouter(prefix="/agent-tester")` n'a aucune dépendance d'authentification (`Depends(get_current_user)`). N'importe qui sur Internet peut appeler `/api/agent-tester/test/...` pour déclencher des exécutions LLM lourdes, épuisant votre budget API instantanément (déni de service par ruine financière).
* **Correctif :** Ajouter la dépendance sur le routeur :
```python
router = APIRouter(prefix="/agent-tester", tags=["Agent Tester"], dependencies=[Depends(get_current_user)])
```
* **Effort :** 0.5h

**BIZ-01 | Contournement du palier payant pour la phase BUILD**
* **Gravité :** **Bloquant**
* **Emplacement :** `backend/app/api/routes/orchestrator/build_routes.py`, ligne 165 (`start_build_phase`)
* **Scénario réel :** La politique commerciale dit : "Pro = SDS uniquement, Team = BUILD". Or, la route pour lancer le build n'est protégée par aucune vérification de palier (`@require_feature("build_phase")`). Un utilisateur "Pro" (ou même "Free" si `build_enabled=True` sur le serveur) peut forger une requête HTTP `POST /projects/{id}/start-build` et lancer une génération de code très coûteuse.
* **Correctif :** Ajouter le décorateur existant sur l'endpoint.
```python
from app.utils.feature_access import require_feature
@router.post("/projects/{project_id}/start-build")
@require_feature("build_phase")
```
* **Effort :** 0.5h

**SEC-03 | Fuite cryptographique potentielle (Conception de l'Onboarding)**
* **Gravité :** **Mineur** (Tech Debt)
* **Emplacement :** `backend/app/utils/email_token.py`, ligne 33
* **Scénario réel :** Le flux d'inscription encode le mot de passe hashé dans le token JWT envoyé par email (`"hashed_password": hashed_password`). Si le lien email est intercepté par un scanner d'entreprise ou transféré par erreur, le hash est exposé. Bien que haché, ce n'est pas une pratique standard. À corriger post-lancement en utilisant une table temporaire pour les inscriptions en attente.
* **Effort :** 4h (peut attendre)

---

### 5. Passage à l'échelle (Scalability)

**Le code peut-il monter en charge ?**
Oui, *jusqu'à une certaine limite*. Les bonnes décisions ont été prises pour le court terme : asynchronisme avec FastAPI, détachement des tâches lourdes via ARQ (`worker.py`), et les appels LLM longs utilisent le streaming (`STREAM-001`).

Cependant, le goulot d'étranglement fatal sera le **SFDX CLI via subprocess** (`sfdx_service.py`). Lancer des exécutables Java/Node.js lourds via `subprocess` pour chaque déploiement va saturer la RAM des workers très rapidement.

**Coût d'inférence (pour un palier cible "Team") :**
Un cycle SDS complet (~800 crédits) + Un cycle BUILD (~3500 crédits) = 4300 crédits par itération.
À 0,001$ le crédit (équivalent Sonnet), une itération coûte ~4,30$.
À 1490 €/mois pour le palier Team, vous avez une marge brute colossale (99%+). Votre problème ne sera pas la rentabilité unitaire, mais les **limites de taux (rate limits)** des API Anthropic.

**Dimensionnement par palier :**

*   **10 Clients (Lancement) :**
    *   *Infra :* 1 serveur monolithique (4 vCPU, 8 Go RAM) gérant FastAPI, PostgreSQL, Redis, et ChromaDB.
    *   *À refaire :* Rien. L'architecture actuelle est parfaite pour ça.

*   **100 Clients :**
    *   *Infra :* 2 nœuds API (2 vCPU, 4 Go). 2 nœuds Workers ARQ (4 vCPU, 8 Go). PostgreSQL et Redis managés.
    *   *À refaire :* Sortir la base de données et Redis du serveur applicatif. Activer le `pool_size=50` sur SQLAlchemy.

*   **1 000 Clients :**
    *   *Infra :* 5 nœuds API. 10 nœuds Workers. ChromaDB déporté sur une instance serveur dédiée (actuellement il tourne localement avec le client FastAPI/Worker).
    *   *À refaire :* Refonte de `rag_service.py`. Vous utilisez `chromadb.PersistentClient(path=CHROMA_PATH)`. Avec de multiples workers, le lock SQLite de ChromaDB va s'effondrer. Il faut passer à `chromadb.HttpClient()`.

*   **10 000 Clients (La limite architecturale) :**
    *   *Ce qui casse :* SFDX CLI. `subprocess.run(["sf", ...])` ne tiendra pas 10 000 déploiements parallèles. Le système manquera de descripteurs de fichiers et de mémoire.
    *   *À refaire (Projet lourd) :* Abandonner le CLI Salesforce. Remplacer `SFDXService` par des appels natifs à la *Tooling API* et *Metadata API* via HTTP (`httpx` / `simple-salesforce` équivalent Python).

---

### 6. Ce qui manque pour être exploitable (Operability)

**OPS-01 | Sondes de santé aveugles**
* **Emplacement :** `backend/app/main.py`, ligne 114
* **Scénario :** L'endpoint `/health` retourne `{"status": "healthy"}` de manière statique. Si PostgreSQL ou Redis tombe, l'orchestrateur (Kubernetes/Docker) pensera que l'app va bien et ne la redémarrera pas, laissant vos utilisateurs face à des erreurs 500.
* **Correctif :** Ajouter un simple `SELECT 1` sur la DB dans le check de santé.

**OPS-02 | Nettoyage des exécutions "Zombies" uniquement au démarrage**
* **Emplacement :** `backend/app/workers/worker.py`, ligne 12
* **Scénario :** `startup()` appelle un flush des jobs morts. C'est bien, mais si un worker tourne pendant 3 mois sans redémarrer, les exécutions interrompues (timeout silencieux de l'API) resteront bloquées en statut `RUNNING` indéfiniment.
* **Correctif :** Créer une tâche ARQ planifiée (cron) qui tourne toutes les heures pour exécuter `cleanup_zombie_executions()`.

---

### 7. Dette technique qui coûtera cher

**DEBT-01 | Listes d'agents codées en dur malgré le registre**
* **Emplacement :** `frontend/src/lib/agents.ts` et `frontend/src/constants.ts`
* **Scénario :** Bien que vous ayez créé un `agents_registry.yaml` au backend, le frontend duplique toute la définition de l'ensemble (noms, rôles, id). Si vous ajoutez un 12ème agent, vous devrez modifier le backend *et* traquer les 4 endroits du frontend où ils sont listés en dur.
* **Correctif :** Le front doit être nourri exclusivement par `/api/agent-tester/agents` ou un nouvel endpoint de configuration.

**DEBT-02 | Le Parsing JSON LIFO est un pansement sur une jambe de bois**
* **Emplacement :** `backend/app/utils/json_cleaner.py`
* **Scénario :** `_close_truncated_json_lifo` est une merveille d'ingénierie, mais c'est un symptôme. Si les LLM tronquent le JSON, c'est que la taille de sortie dépasse `max_tokens`.
* **Correctif :** Avec les récents modèles (Claude 3.5 Sonnet permet 8192 tokens de sortie en natif, voire plus en beta), paramétrez les appels pour autoriser la sortie maximale, plutôt que de tenter de réparer des JSONs hachés en plein vol.

---

### Feuille de route (Roadmap)

**Vague 1 : Avant le 1er octobre (Immédiat - Les bloqueurs)**
1. Corriger l'injection SOQL (`agent_tester.py`). *(0.5h)*
2. Sécuriser les routes publiques par `get_current_user` (`agent_tester.py`). *(0.5h)*
3. Bloquer l'accès au BUILD par un contrôle strict des tiers (`build_routes.py`). *(0.5h)*
4. Fixer l'absence de rollback sur les commits de base de données (`change_request_service.py`). *(1h)*
5. Retirer l'email d'exemple en dur dans `salesforce_config.py`. *(0.5h)*

**Vague 2 : Dans les 30 jours suivant le lancement (Consolidation)**
1. Rendre le `/health` check dépendant de Postgres et Redis. *(1h)*
2. Ajouter le script de cron ARQ pour purger les exécutions zombies à chaud. *(2h)*
3. Supprimer le fichier fantôme `blog_generator.py` des appels API. *(0.5h)*

**Vague 3 : Plus tard (Dette pour la montée en charge à 1000+ clients)**
1. Remplacer `chromadb.PersistentClient` par l'architecture client/serveur de Chroma.
2. Déprécier le CLI SFDX (`subprocess.run`) au profit d'appels directs à la Metadata API REST.
3. Rendre le frontend dynamique vis-à-vis de la liste des agents (supprimer `constants.ts`).