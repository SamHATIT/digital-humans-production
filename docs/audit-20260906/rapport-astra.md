J’ai lu intégralement le contenu transmis ; je ne peux rien exécuter et n’ai lancé aucun test, scan ni appel réseau.
**Non : je déconseille l’ouverture Free et Pro en l’état au 1er octobre 2026.**
Des accès interclients subsistent, notamment dans le testeur d’agents, le contexte des demandes de changement et le stockage des versions SDS.
Les correctifs de crédits et de reprise ne garantissent toujours ni les plafonds, ni la facturation exhaustive, ni la conservation du travail déjà produit.
L’ouverture reste possible après les bloquants ci-dessous, avec BUILD et outils internes fermés côté serveur, puis une recette indépendante des correctifs.

## Constats

### Périmètre et lecture des emplacements

- `B/` signifie `backend/app/` ; `F/` signifie `frontend/src/`.
- Les références `fichier::fonction + n` désignent une **ligne relative à la déclaration de cette fonction**, comptée à partir de zéro. Le symbole et l’instruction citée donnent un emplacement non ambigu dans les longs fichiers transmis.
- Les efforts sont des **heures de réalisation et de tests ciblés**, pas des heures d’arbitrage humain. Les correctifs qui partagent un fichier devront être intégrés par un seul responsable de lot.
- Je n’ai pas reçu le contenu des agents `backend/agents/roles/`, des configurations Nginx, des Dockerfile ni du générateur `tools/build_sds.py`. Le prompt `backend/prompts/agents/sophie_pm.yaml` est référencé, mais son contenu n’apparaît pas dans le dump. Je ne certifie donc pas leurs protections.
- Aucun secret supplémentaire ne peut être déclaré **encore valide** par cette lecture seule. Plusieurs secrets supplémentaires sont cependant exposés : leur révocation doit être vérifiée, ou effectuée, avant ouverture.

---

# 1. Sécurité

### SEC-01 — Autres secrets exposés, dont une clé d’administration Ghost

**Gravité : bloquant tant que leur révocation n’est pas établie.**

**Emplacements :** `scripts/ghost_api.py:13–14` ; `CLAUDE.md`, bloc « Reporting », instruction `urllib.request.urlopen(...)` ; `frontend/public/test.html:24–25` ; `frontend/public/login-test.html`, champs `email` et `password`.

**Constat et scénario.** Une clé **Ghost Admin**, une clé Ghost Content et un jeton de bot Telegram sont présents en clair. Deux pages publiques embarquent également un couple d’identifiants d’administration. Contrairement au mot de passe PostgreSQL expressément déclaré rotaté, aucune preuve de révocation de ces autres valeurs n’est fournie. Une clé Ghost Admin valide permettrait de modifier le contenu du site ; le jeton Telegram permettrait d’usurper le bot, notamment ses messages d’alerte.

La clé **Content** Ghost n’a pas les privilèges de la clé Admin : ne pas confondre leurs gravités.

**Correctif.** Révoquer la clé Admin et le jeton Telegram, vérifier/désactiver le compte de démonstration, supprimer les pages publiques et remplacer les littéraux par des variables obligatoires. Ne pas recopier les secrets dans les tickets, rapports ou commandes de recherche publiées. Nettoyer ensuite l’historique et les artefacts diffusés.

**Effort : 2–4 h**, dont environ 30 minutes d’intervention du propriétaire des comptes fournisseurs.

---

### SEC-02 — Le testeur d’agents reste un outil global accessible à tout compte

**Gravité : bloquant.**

**Emplacements :** `B/main.py:138–139` ; `B/api/routes/agent_tester.py:162–200` ; `B/services/agent_executor.py::AgentExecutor.execute_agent + 0`, paramètres `project_id=53`, `user_id=2` ; `B/services/agent_executor.py::get_agent_executor + 0`.

**Constat et scénario.** Le routeur est réellement monté. Il exige une authentification, **pas une autorisation d’administration**. La route de test ne transmet ni utilisateur ni projet : elle utilise les valeurs par défaut **53 et 2**. Un compte Free peut donc créer une exécution dans ce projet et provoquer des appels imputés au compte 2, si ces lignes existent.

Les routes de journaux et de workspace sont également globales. Enfin, le singleton partage `self.execution`, `self.db` et `self.logs` entre requêtes : deux tests concurrents peuvent enregistrer résultats et statuts dans la mauvaise exécution.

**Correctif.** Pour Free/Pro, **démonter entièrement ce routeur dans FastAPI**, pas seulement le masquer ou le filtrer dans Nginx. Supprimer les identifiants par défaut. Pour une réouverture ultérieure : autorisation opérateur explicite, projet possédé, instance d’exécuteur par tâche et journaux rattachés au propriétaire.

**Effort : 1–2 h pour fermer ; 10–16 h pour le rendre réouvrable.**

---

### SEC-03 — Les sorties d’agents permettent encore des écritures hors workspace

**Gravité : bloquant sur tout chemin BUILD ou testeur accessible.**

**Emplacements :**

- `B/services/agent_executor.py::AgentExecutor._save_to_workspace + 0`, `os.path.join(folder, filename)` ;
- `B/services/git_service.py::GitService.commit_files + 0`, `os.path.join(self.repo_path, path)` ;
- `B/services/git_service.py::commit_and_pr + 0`, même construction ;
- `B/services/jordan_deploy_service.py::JordanDeployService.deploy_source_code + 0` ;
- `B/services/sf_admin_service.py::SFAdminService._generate_object_metadata + 0` ;
- `B/services/phase_aggregator.py::PhaseAggregator._normalize_path + 0`.

**Constat et scénario.** Les noms et chemins issus des sorties LLM sont utilisés comme chemins d’écriture. La « normalisation » ne refuse ni `..`, ni tous les chemins absolus. Le modèle n’est pas une frontière de confiance : une sortie orientée par un brief peut écraser des fichiers accessibles au service. Dans Git, même un chemin restant dans le dépôt peut viser `.git/config` ou des hooks.

Le retrait de `shell=True` ne corrige pas cette classe d’injection.

**Correctif.** Valider **au point d’écriture**, avec une racine propre à l’exécution, une liste de répertoires/extensions autorisés et interdiction de `.git`, des liens symboliques et des chemins absolus :

```python
root = Path(workspace).resolve()
relative = Path(name)
target = (root / relative).resolve()
if relative.is_absolute() or not target.is_relative_to(root):
    raise ValueError("Chemin de livrable interdit")
```

Ce contrôle doit être complété par l’allowlist et une création sans suivi de liens ; il ne suffit pas seul dans un répertoire modifiable concurremment.

**Effort : 8–12 h.** Fermeture immédiate via SEC-02 et BILL-05.

---

### SEC-04 — Le RAG « global » inclut les documents privés

**Gravité : bloquant avant toute ingestion de documents clients.**

**Emplacements :** `B/services/rag_service.py:198–232`, notamment `where_filter = ... if project_id else None` ; `B/services/rag_service.py:234–260` ; `backend/tests/test_vague_a_a5_concierge_cloisonnement.py::test_controle_negatif_le_rag_global_sort_bien_le_chunk_du_projet_999 + 0`.

**Constat et scénario.** `project_id=None` ne signifie pas « documentation publique » : il signifie **aucun filtre**, donc tous les documents, privés compris. À l’inverse, avec un projet, la requête ne sélectionne que ses documents et exclut la documentation générale.

A5 protège bien le concierge parce qu’il n’appelle pas le RAG ; il ne protège pas les autres consommateurs. **La primitive de fuite est confirmée ; l’exhaustivité des appels des agents ne peut pas l’être, leurs sources n’étant pas transmises.**

**Correctif.** Marquer explicitement les chunks publics et privés. Sans contexte client, sélectionner uniquement les publics ; avec contexte, publics **ou** projet autorisé. Backfill prudent : ne pas classer automatiquement tous les chunks sans métadonnée comme publics. Rendre le contexte de projet obligatoire pour l’ingestion privée.

**Effort : 8–12 h**, migration de métadonnées et tests A/B/public inclus.

---

### SEC-05 — Le chat HITL recharge le livrable d’un autre client dans sa classification

**Gravité : bloquant.**

**Emplacements :** `B/api/routes/hitl_routes.py::chat_with_sophie_contextual + 0`, appel `cr_service.create_from_chat(... deliverable_id=body.deliverable_id ...)` ; `B/services/change_request_service.py::ChangeRequestService.create_from_chat + 0`, requête filtrée uniquement sur `AgentDeliverable.id` ; même service, `analyze_impact`, lecture de `related_br_id`.

**Constat et scénario.** La première lecture du livrable dans la route vérifie l’exécution ; si le livrable appartient à autrui, elle l’ignore. Mais son identifiant est ensuite passé au classificateur, qui le recharge **sans filtre d’exécution**. Les 500 premiers caractères du livrable tiers entrent dans le prompt et peuvent ressortir dans la description de CR rendue au demandeur.

Autre réapparition : une ancienne CR liée à un BR tiers est protégée dans les routes de lecture, mais `analyze_impact` recharge ce BR par son seul identifiant.

**Correctif.**

```python
.filter(
    AgentDeliverable.id == deliverable_id,
    AgentDeliverable.execution_id == execution_id,
)
```

Refuser l’identifiant incohérent dès la route ; appliquer le filtre `BusinessRequirement.project_id == cr.project_id` dans l’analyse. Tester le prompt reçu par le LLM, pas uniquement la réponse de lecture.

**Effort : 2–4 h.**

---

### SEC-06 — Deux clients peuvent écraser la même version SDS sur disque

**Gravité : bloquant.**

**Emplacements :** `B/api/routes/sds_versions.py:268–303`, particulièrement `286–289` ; `B/models/sds_version.py:14–21`.

**Constat et scénario.** Les snapshots sont enregistrés dans un répertoire commun sous `SDS_<nom_projet>_v<n>.html`, **sans identifiant de client ni de projet**. Deux projets portant le même nom et le même numéro de version désignent le même fichier. Le deuxième écrase le premier ; le premier client consulte ensuite le document du deuxième malgré un contrôle SQL de propriété correct. L’effacement d’un compte peut aussi supprimer le fichier de l’autre.

Deux snapshots concurrents du même projet calculent également le même `max(version)+1` ; aucune contrainte unique ORM ne protège ce couple.

**Correctif.** Chemin par `project_id` puis identifiant de version immuable ; allocation de version sous verrou et contrainte unique `(project_id, version_number)`. Écriture exclusive, jamais écrasante. Examiner et réparer les collisions déjà présentes avant migration.

**Effort : 6–10 h.**

---

### SEC-07 — Un nom Salesforce saisi n’établit pas la propriété de l’org

**Gravité : bloquant pour les connexions Salesforce du SaaS.**

**Emplacements :** `B/api/routes/projects.py::update_project_settings + 0`, affectation de `sf_username` ; `B/api/routes/projects.py::test_salesforce_connection + 0`, appel `sfdx_auth.test_connection(username)` ; `B/services/sfdx_auth_service.py::SFDXAuthService.get_access_token + 0` ; `B/services/pm_orchestrator_service_v2.py::PMOrchestratorServiceV2._get_salesforce_metadata + 0`.

**Constat et scénario.** Le client possède son projet, mais peut y saisir le nom d’un utilisateur Salesforce déjà authentifié **sur le serveur commun**. Le test récupère cette authentification locale et marque le projet connecté. L’orchestrateur peut ensuite lire l’org ainsi désignée. Le montage `/root/.sf` et `/root/.sfdx` dans `docker-compose.prod.yml` aggrave ce partage.

Le repli vers `salesforce_config` subsiste aussi lorsqu’un projet connu n’a pas d’URL d’instance.

**Correctif.** Ne jamais autoriser l’emprunt d’une session CLI globale par nom saisi. Établir une connexion propre au projet par un flux prouvant l’accès à l’org ; persister et vérifier l’org ID côté serveur. Isoler les magasins d’authentification CLI. Supprimer le repli global du chemin client.

**Effort : 8–16 h**, ou **1–2 h pour fermer temporairement ces connexions** et ouvrir Pro uniquement sur le périmètre explicitement annoncé sans connexion à une org existante.

---

### SEC-08 — La règle « jamais en production Salesforce » n’est pas générale

**Gravité : bloquant si une fonction de déploiement reste accessible.**

**Emplacements :** `B/services/sf_admin_service.py::org_est_productive + 0` ; `B/services/sfdx_service.py::SFDXService.deploy_source + 0` ; `B/services/agent_executor.py::AgentExecutor._deploy_to_salesforce + 0` ; `B/services/jordan_deploy_service.py::JordanDeployService.deploy_phase + 0`.

**Constat et scénario.** Le garde-fou est local à `SFAdminService`, pas à tous les déploiements. Les déploiements de source et du testeur ne l’utilisent pas. Même là où il existe, une sous-chaîne comme `--` dans l’alias suffit à déclarer l’org non productive : un alias n’est pas une preuve du type d’org.

**Correctif.** Pour l’ouverture Free/Pro, désactiver **toutes** les écritures Salesforce au niveau service et worker. Pour Team : contrôler une identité d’org autorisée et un statut non productif obtenu d’une source Salesforce authentifiée, jamais d’une sous-chaîne fournie par l’appelant.

**Effort : 2–3 h pour fermer ; 6–10 h pour le contrôle complet.**

---

### SEC-09 — URLs Salesforce et Git arbitraires : SSRF et fuite de credentials

**Gravité : bloquant pour les tests de connexion accessibles.**

**Emplacements :** `B/services/connection_validator.py::ConnectionValidatorService.test_salesforce_connection + 0`, `requests.get(identity_url, headers=headers, ...)` ; même classe, `test_git_connection`, `git ls-remote` ; `B/api/routes/projects.py::test_salesforce_connection + 0`, GET vers `api_url` saisi.

**Constat et scénario.** Le wizard accepte une URL arbitraire et y envoie un bearer Salesforce. Un faux jeton suffit pour faire effectuer une requête serveur vers une destination choisie. Le chemin OAuth obtient un vrai jeton puis l’envoie à l’URL saisie, au lieu de l’instance authentifiée retournée par Salesforce. Git accepte des URLs et protocoles non bornés.

**Correctif.** Valider schéma, hôte, port et résolution IP ; refuser loopback, réseaux privés et destinations réservées ; interdire les redirections non revalidées. Pour Salesforce, utiliser l’instance liée au résultat OAuth. Pour Git, limiter les fournisseurs/protocoles supportés et poser `GIT_ALLOW_PROTOCOL=https`, avec validation stricte de l’URL.

**Effort : 6–10 h.** Ne pas annoncer une injection shell Git : elle n’est pas démontrée ici.

---

### SEC-10 — Le HTML des livrables redevient actif dans l’origine du Studio

**Gravité : bloquant.**

**Emplacements :** `B/api/routes/deliverables.py::render_deliverable_html + 0`, retours `HTMLResponse(content=html)` et interpolation `<pre>{html}</pre>` ; `F/services/api.ts::openAuthenticated + 0`, création et ouverture du `blob:` ; `F/components/DeliverableViewer.tsx`, bouton `Open SDS`.

**Constat et scénario.** Le rendu React du chat a été sécurisé, mais les livrables HTML sont servis sans assainissement. Le helper les transforme en Blob ouvert dans l’origine du frontend. Un script issu d’un livrable peut lire `localStorage.token` et appeler les API du lecteur. `window.open('', '_blank')` conserve également un lien d’ouverture.

Une CSP ajoutée uniquement à la réponse API ne constitue pas une solution suffisante si le frontend recrée ensuite un document Blob.

**Correctif.** Ne plus ouvrir du HTML non fiable en document de premier niveau de l’origine Studio. Utiliser un rendu assaini dans une iframe sandboxée, sans `allow-scripts` ni `allow-same-origin`, ou une origine de rendu isolée. Échapper le texte brut dans `<pre>`. Tester une charge script provenant du contenu, et pas seulement du chat.

**Effort : 6–10 h.**

---

### SEC-11 — Le blog public déclenche des dépenses et accepte une injection d’option CLI

**Gravité : bloquant.**

**Emplacements :** `B/main.py:184–189` ; `B/api/routes/blog.py::generate_batch + 0` et `generate_single_article + 0` ; `scripts/blog_generator.py`, bloc `argparse`, options `--publish` et argument `topic` facultatif ; `scripts/blog_api.py::get_ghost_token + 0`.

**Constat et scénario.** `/api/blog/generate-batch` est réellement monté sans authentification. Il déclenche des appels Anthropic/Gemini et des écritures Ghost. Le client fournit également l’identifiant du sujet à modifier, sans vérification de son statut « approved ».

Un titre égal à `--publish` devient une **option argparse**, pas un titre : le script peut publier son sujet par défaut. L’absence de shell ne protège pas de cette injection d’argument.

L’API autonome `scripts/blog_api.py` distribue en plus des JWT Ghost Admin sans authentification si elle est démarrée. **Son exposition effective sur le port 8765 n’est pas vérifiée.**

**Correctif.** Démonter le routeur blog du SaaS public et supprimer/fermer `/ghost-token`. Pour l’outil interne, sélectionner un sujet approuvé en base, autoriser l’opérateur, borner les lots et séparer clairement options et données CLI.

**Effort : 1–2 h pour fermer ; 5–8 h pour sécuriser l’outil.**

---

### SEC-12 — Inscription legacy sans vérification d’adresse et rattachement abusif des conversations

**Gravité : bloquant.**

**Emplacements :** `B/api/routes/auth.py::register + 0`, création `is_active=True` ; `signup_confirm`, branche `if existing:` ; `B/services/account_service.py::AccountService._sessions_vitrine + 0`.

**Constat et scénario.**

1. `/register` permet de créer un compte actif avec l’adresse d’un tiers sans en prouver la possession.
2. L’export RGPD rattache toutes les conversations concierge portant cet e-mail au compte. Un attaquant peut donc créer le compte correspondant à l’adresse collectée dans une conversation et l’exporter ou l’effacer.
3. Si un lien de confirmation a été émis avant qu’un autre compte occupe cette adresse, `signup_confirm` connecte le visiteur au compte existant sans remplacer le mot de passe posé par le squatteur. Celui-ci conserve son accès.

**Correctif.** Fermer le chemin legacy public ou le faire utiliser le même mécanisme de vérification. Ne pas assimiler « e-mail mentionné dans une conversation » à « session possédée ». À la confirmation, n’accepter que la création attendue ou la réutilisation du **même** échange déjà consommé, pas n’importe quel compte portant l’adresse.

**Effort : 6–10 h.**

---

### SEC-13 — Le double opt-in des leads peut être fabriqué par le demandeur

**Gravité : majeur ; fermer la collecte avant ouverture si non corrigé.**

**Emplacements :** `B/api/routes/leads.py::LeadResponse + 0`, `verification_token` ; `create_lead`, retour du jeton et `ON CONFLICT ... verified` ; `LeadCreate`, `newsletter=True`.

**Constat et scénario.** Le jeton de vérification est retourné à celui qui soumet l’adresse. Il peut immédiatement appeler `/verify` sans accéder à la boîte mail. Pour un lead déjà vérifié, un appel anonyme peut modifier ses informations et sa préférence newsletter tout en conservant `verified=true`.

**Correctif.** Ne jamais retourner le jeton ; envoyer un lien à l’adresse concernée. Une modification de consentement ne devient effective qu’après validation de ce lien. Newsletter désactivée par défaut, avec preuve distincte et jeton à usage unique stocké sous empreinte.

**Effort : 4–6 h.**

---

### SEC-14 — Les protections de débit dépendent d’une IP falsifiable et ne couvrent pas toutes les routes

**Gravité : majeur.**

**Emplacements :** `B/rate_limiter.py::get_client_ip + 0` ; `B/rate_limiter.py::limiter`, construction `Limiter(...)` ; `B/main.py:93–95,117–127`.

**Constat et scénario.** Le premier élément de `X-Forwarded-For` est accepté sans vérifier le proxy émetteur. Si Nginx transmet ou complète cet en-tête, un client fait varier la clé du limiteur et du hachage de consentement. **La configuration proxy n’étant pas fournie, l’exploitabilité depuis Internet reste à vérifier.**

Le limiteur est en mémoire. Le simple `default_limits` ne constitue pas, dans ce montage, une protection démontrée de toutes les routes non décorées ; aucun middleware SlowAPI général n’est installé dans `main.py`.

**Correctif.** N’accepter l’IP relayée que depuis les proxys de confiance ; écraser les en-têtes clients au frontal. Limiter les opérations coûteuses par compte et globalement, dans Redis. Tester les routes non décorées et les changements d’IP déclarée.

**Effort : 4–6 h.**

---

### SEC-15 — Corps sensibles, jetons Git et authentification Salesforce se retrouvent dans les sorties

**Gravité : bloquant.**

**Emplacements :**

- `B/main.py:203–222` : journal et réponse des erreurs de validation ;
- `B/services/git_service.py::GitService._run_git + 0`, journal de tous les arguments ; `clone`, URL contenant le jeton ;
- `B/services/pm_orchestrator_service_v2.py::PMOrchestratorServiceV2._get_salesforce_metadata + 0`, copie intégrale de `org_data["result"]`.

**Constat et scénario.** Une erreur de formulaire renvoie le corps complet, potentiellement mot de passe ou secret. Les erreurs Pydantic peuvent également porter l’entrée fautive. Git journalise l’URL authentifiée et la conserve normalement comme remote du clone. Le résultat complet de `sf org display --json`, susceptible de contenir `accessToken`, est stocké comme livrable puis utilisé dans le contexte d’analyse.

De nombreuses routes renvoient aussi `str(e)` ou `stderr` tels quels.

**Correctif.** Réponse de validation limitée à `loc`, `type`, `msg`, sans `input`, `ctx` ni corps ; journal technique corrélé et expurgé. Authentification Git sans secret dans l’URL/argv, remote nettoyé. Allowlist des champs Salesforce utiles avant stockage et prompt. Examiner les logs et livrables déjà produits, puis révoquer les jetons effectivement exposés.

**Effort : 6–10 h**, plus rotation des credentials concernés.

---

### SEC-16 — Le WebSocket contourne la désactivation du compte

**Gravité : majeur.**

**Emplacements :** `B/api/routes/orchestrator/chat_ws_routes.py::websocket_endpoint + 0` ; `_load_execution_snapshot`, filtre projet/utilisateur sans lecture de `User.is_active`.

**Constat et scénario.** Le WebSocket valide directement le JWT, contrairement à la dépendance HTTP commune. Un compte désactivé dont les projets existent encore peut continuer à consulter ses exécutions. Une connexion ouverte n’est pas arrêtée à l’expiration du jeton. Le SSE ne réévalue pas non plus l’activité du compte pendant le flux.

L’effacement complet supprime normalement les projets, ce qui limite ce cas précis ; cela ne justifie pas la promesse « révocation sur toute l’API ».

**Correctif.** Partager la validation d’utilisateur actif ; contrôler l’expiration et la désactivation pendant les lectures périodiques. Convertir `sub` avant `accept()` avec gestion de type invalide.

**Effort : 3–5 h.**

---

### SEC-17 — Configuration de production permissive et clés insuffisamment validées

**Gravité : majeur ; contrôle de déploiement obligatoire avant ouverture.**

**Emplacements :** `B/config.py:24–31,44–45` ; `B/config.py::Settings.validate_secret_key + 0` ; `B/utils/encryption.py::build_fernet + 0` ; `B/database.py:11–18` ; `B/main.py:98–115` ; `docker-compose.prod.yml`, commandes backend/frontend.

**Constat et scénario.** `DEBUG=True` est le défaut ; il active les traces SQL avec paramètres et les pages de debug. Toute clé JWT non vide est acceptée, y compris le placeholder du gabarit. Une clé de chiffrement mal formée est silencieusement transformée par SHA-256 au lieu d’être refusée.

Les origines CORS configurables ne sont pas consommées par `main.py`, qui utilise une liste HTTP en dur sans les domaines HTTPS commerciaux. Le compose « prod » démarre Uvicorn avec `--reload` et le serveur Vite de développement sur toutes les interfaces.

**Je ne déduis pas de ces défauts que le VPS utilise actuellement ces valeurs.**

**Correctif.** Défauts sûrs, validation de format et rejet des placeholders, `echo=False`/`hide_parameters=True`, origines HTTPS exactes depuis Settings. Produire les assets Vite et les servir statiquement ; limiter les ports internes. Ne pas générer de clé de remplacement silencieuse en production.

**Effort : 4–6 h.**

---

### SEC-18 — Dépendances backend épinglées sur des versions affectées par des vulnérabilités connues

**Gravité : bloquant pour le traitement multipart public ; majeur pour le reste.**

**Emplacements :** `backend/requirements.txt:2–4,12–14,17` ; `frontend/package.json:42` ; `frontend/vite.config.ts:7–9`.

**Constat et scénario.** `python-multipart==0.0.6` est concerné par des dénis de service connus, notamment CVE-2024-24762 et CVE-2024-53981. FastAPI 0.104.1 impose une ancienne branche Starlette, antérieure aux corrections de limites multipart, notamment CVE-2024-47874. L’upload est exposé.

`python-jose==3.3.0` est également une version affectée par des avis connus ; **je ne conclus pas à un contournement JWT actif**, l’application montrant HS256 et non tous les chemins vulnérables de la bibliothèque.

Pour Vite, `^5.4.10` autorise des versions vulnérables mais aussi des correctifs : **sans lockfile ni installation, la version effectivement résolue est inconnue**.

**Correctif.** Mettre à niveau ensemble FastAPI/Starlette/multipart vers un ensemble maintenu et compatible ; actualiser la bibliothèque JWT et verrouiller les versions résolues. Faire exécuter un audit des dépendances directes/transitives. Réévaluer alors le pin httpx : conserver une dépendance vulnérable pour préserver l’ancien TestClient n’est pas acceptable.

**Effort : 6–10 h**, recette multipart/auth/SSE comprise.

---

### Couverture des routes de sécurité relues

| Surface | Résultat de lecture |
|---|---|
| `auth`, `account`, `billing` | Authentification HTTP commune correcte pour les routes de compte ; défauts SEC-12, SEC-15 et facturation ci-dessous. |
| `projects`, `wizard`, orchestrateur `project_routes` | Propriété du projet contrôlée côté serveur. Pas de modification de `user_id` via `ProjectUpdate`. La propriété de l’org Salesforce n’est pas prouvée. |
| `business_requirements`, `project_chat` | Filtres projet/propriétaire présents, y compris suppression et réordonnancement. |
| `artifacts` | Toutes les routes appellent le contrôle d’exécution ; les méthodes de service utilisées filtrent par cette exécution. |
| `deliverables` | Propriété du livrable/exécution vérifiée ; références secondaires et rendu HTML restent à corriger. |
| `change_requests`, `hitl_routes` | Contrôles principaux présents ; recharge secondaire non cloisonnée, SEC-05. La liste `/executions/{id}/agents` ne vérifie pas la propriété. |
| orchestrateur `execution_routes` | Contrôles présents **sauf `/execute/{id}/budget`**, qui est anonyme et révèle les coûts d’exécution/projet. |
| orchestrateur `build_routes`, `retry_routes` | Propriété et principales portes de palier présentes ; autres reprises contournent ces portes, BILL-05. |
| orchestrateur `validation_gate_routes` | Propriété présente ; autorisations de palier manquantes. |
| `quality_dashboard`, `api/audit.py` | Cloisonnement principal présent ; `AuditService.get_logs` filtre réellement en SQL. |
| `documents` | Propriété présente ; défauts RAG, quotas et cycle de suppression. |
| `agent_tester`, `blog` | Surfaces effectivement montées et dangereuses, SEC-02/11. |
| `leads`, `concierge_routes`, `journal_webhook`, `config`, `subscription` | Publicité partiellement intentionnelle ; identité des sessions, opt-in, budget et secret d’URL à corriger. |
| `deployment`, `environments`, `quality_gates` | **Non montés dans le `main.py` fourni.** Leurs défauts ne sont pas présentés comme des failles Internet actives. Interdire leur remontage sans recette. |

### SEC-19 — Deux lectures et des références secondaires échappent encore au cloisonnement

**Gravité : majeur.**

**Emplacements :** `B/api/routes/orchestrator/execution_routes.py::get_execution_budget + 0` ; `B/api/routes/hitl_routes.py::list_available_agents + 0` ; `B/services/deliverable_service.py::DeliverableService.create_deliverable + 0` et `update_deliverable`.

**Scénario.** Un anonyme lit les coûts d’une exécution et de son projet. Un utilisateur authentifié observe les agents disponibles d’une exécution tierce. Un propriétaire peut rattacher son livrable à `output_file_id` ou `execution_agent_id` d’une autre exécution : l’existence d’une FK ne garantit pas la cohérence de tenant.

Je ne conclus pas à une lecture de fichier tiers par `/api/outputs/{id}` : ce routeur n’est pas fourni/monté ici.

**Correctif.** Ajouter `verify_execution_access` aux deux lectures et vérifier chaque référence secondaire dans l’exécution autorisée. Tester créations et mises à jour avec un identifiant tiers valide.

**Effort : 3–5 h.**

---

# 2. Ce qui casse en production

### PROD-01 — Un chat Sophie peut immobiliser toute la boucle API

**Gravité : bloquant.**

**Emplacements :** `B/services/sophie_chat_service.py::SophieChatService.chat + 0`, appel synchrone `generate_llm_response(...)` ; `B/services/llm_router_service.py::LLMRouterService.complete_sync + 0`, `future.result(timeout=600)` ; `B/utils/dependencies.py::get_current_user + 0`.

**Scénario.** `chat()` est asynchrone mais attend un appel synchrone. Le thread créé dans `complete_sync` ne libère pas l’event loop appelante : celle-ci attend sur `future.result`. Pendant un appel lent, les autres requêtes, sondes et flux de ce processus peuvent être figés. Stripe, certaines requêtes SQL et les appels directs des agents BUILD reproduisent ce mélange async/sync.

**Correctif.** Utiliser le wrapper LLM asynchrone dans les coroutines. Pour SQL et SDK synchrones, déplacer une unité de travail complète dans un thread, **avec sa propre session créée et fermée dans ce thread**. Ne pas déplacer seulement le réseau tout en conservant des accès ORM bloquants autour.

**Effort : 6–10 h.**

---

### PROD-02 — Délais apparents, appels non annulés et clients asynchrones réutilisés entre boucles

**Gravité : bloquant pour la fiabilité du pipeline.**

**Emplacements :** `B/services/llm_router_service.py::LLMRouterService.complete_sync + 0`, `_init_providers`, `reload_config` ; `B/services/pm_orchestrator_service_v2.py::PMOrchestratorServiceV2._run_agent_interne + 0` ; `B/services/llm_service.py::generate_llm_response + 0`.

**Scénario.** Chaque `asyncio.run` crée une nouvelle boucle, mais les clients AsyncAnthropic/AsyncOpenAI sont conservés dans le singleton. Après utilisation, leurs connexions peuvent appartenir à une boucle fermée. Les clients ne sont pas fermés au reload/shutdown.

`wait_for(to_thread(agent.run))` n’arrête pas le thread : après un timeout, il peut encore facturer ou écrire pendant qu’un retry tourne. Le contexte `ThreadPoolExecutor` attend aussi la fin du thread à sa sortie : son timeout n’est pas une borne ferme. Une session de budget reste ouverte pendant l’appel LLM.

**Correctif.** Un cycle de vie de clients par boucle stable, ou clients créés/fermés dans la boucle qui les utilise. Deadline totale explicite, identifiant de tentative et refus des écritures de tentatives périmées. Fermer les transactions de lecture avant l’attente réseau. Ne pas lancer un retry tant que la tentative précédente n’est pas clôturée ou neutralisée.

**Effort : 10–16 h.**

---

### PROD-03 — État SQL validé avant enfilage Redis : exécutions fantômes et doublons

**Gravité : bloquant.**

**Emplacements :** `B/api/routes/orchestrator/execution_routes.py::start_execution + 0` et `resume_execution` ; `retry_routes.py::retry_failed_execution + 0` ; `build_routes.py::start_build_phase + 0`.

**Scénario.** L’exécution est enregistrée `RUNNING` avant `enqueue_job`. Redis indisponible laisse une exécution en cours sans tâche. Une réponse HTTP perdue ou deux clics concurrents peuvent enfiler plusieurs tâches sur la même exécution. Les gardes worker rejettent les états terminaux, **pas une deuxième tâche lorsque la première tourne**.

**Correctif.** Enregistrer un état `queued` et un identifiant de tentative/enfilage durable ; identifiant ARQ déterministe ; prise de travail atomique côté worker. En cas d’échec d’enfilage, conserver un état explicite récupérable et retourner 503. Prévoir la réconciliation des enfilages au statut incertain, plutôt qu’un simple rollback supposé annuler Redis.

**Effort : 8–12 h.**

---

### PROD-04 — Le démarrage du worker invalide toutes les exécutions actives

**Gravité : bloquant.**

**Emplacements :** `B/workers/worker.py::startup + 0`, sélection de tous les `ExecutionStatus.RUNNING` ; `B/workers/tasks.py::execute_sds_task + 0`, message « completed successfully » ; `worker.py::WorkerSettings`, `job_timeout=3600`.

**Scénario.** Le démarrage d’un worker marque **toutes** les exécutions `RUNNING` en échec, sans propriétaire de tâche ni preuve d’abandon. Cela inclut les tâches en cours d’un autre worker et celles créées juste avant son démarrage. La purge de file cherche également à annuler tous les jobs retournés, sans critère de vétusté.

Les fonctions retournant `{"success": False}` sont néanmoins journalisées comme réussies par `execute_sds_task`. Les annulations asyncio ne sont pas traitées par les `except Exception` et peuvent laisser l’état SQL actif.

**Correctif.** Supprimer la purge globale. Récupérer uniquement les tentatives dont le bail/heartbeat a expiré. Traiter explicitement annulation, timeout, pause HITL et échec métier. Ne jamais écrire « succès » sur un résultat négatif. Tester un redémarrage avec tâche en attente et tâche réellement active.

**Effort : 8–12 h.**

---

### PROD-05 — La table de reprise corrigée saute précisément la phase qu’il fallait reprendre

**Gravité : bloquant.**

**Emplacements :** `B/api/routes/orchestrator/retry_routes.py::retry_failed_execution + 0`, boucle `phase_order` ; `B/services/pm_orchestrator_service_v2.py::EMITTED_TO_RESUME_POINT` ; `backend/tests/test_vague3_correspondance.py::test_retry_enfile_un_point_de_reprise_canonique + 0`, paramétrisation immédiatement précédente.

**Scénario.**

- Sophie terminée → la route émet `phase_ba` → traduction `phase2_5` : **Olivia est sautée**.
- Olivia terminée → `phase_architect` → `phase4` : **Emma et Marcus sont sautés**.
- Marcus terminé → `phase_data` → `phase5` : **les experts sont sautés**.

Les tests attendent expressément ces valeurs erronées. Le correctif a transformé des valeurs mortes en valeurs reconnues, **sans préserver leur sens**.

L’initialisation du workflow réinitialise aussi les statuts ; la reprise réécrit des checkpoints antérieurs avant d’avoir terminé la nouvelle phase.

**Correctif.** Décider depuis `last_completed_phase` et les sorties persistées, pas depuis le nom de l’agent suivant. Tester l’ensemble **route → worker → agents effectivement appelés** : l’assertion « point canonique » seule est insuffisante. Ne jamais faire reculer le dernier checkpoint validé.

**Effort : 6–10 h.**

---

### PROD-06 — Les portes HITL peuvent perdre la décision ou boucler

**Gravité : bloquant si ces portes sont proposées au lancement.**

**Emplacements :** `B/services/validation_gate_service.py::ValidationGateService.pause_for_validation + 0`, `submit_validation`, `should_pause` ; `B/services/execution_state.py::TRANSITIONS` ; `B/api/routes/orchestrator/validation_gate_routes.py::_relancer_apres_porte + 0`.

**Scénario.**

- Le passage de `sds_phase5_running` à `waiting_sds_validation` n’est pas autorisé. Le rollback de la machine d’état peut annuler `pending_validation` et le statut posés juste avant ; le service force ensuite seulement `execution_state`.
- Une approbation est commitée et `pending_validation` effacé **avant** de vérifier si la reprise/export est possible. L’état réel `waiting_sds_validation` n’est pas accepté par `resolve_export_action` : 409 après consommation de la porte.
- La reprise après experts repasse par `should_pause`, qui ne tient pas compte d’une approbation déjà donnée pour cette version : nouvelle pause possible sur la même porte.

**Correctif.** Une transaction pour décision, état et intention de reprise ; transitions explicites ; approbation rattachée à une version de sortie ; ne pas reposer une porte déjà franchie sans nouveau contenu.

**Effort : 10–16 h**, ou **2 h pour retirer proprement les portes configurables de l’offre initiale** sans contourner les validations nécessaires.

---

### PROD-07 — Échecs de production, de QA et de persistance transformés en SDS terminé

**Gravité : bloquant Pro.**

**Emplacements :** `B/services/pm_orchestrator_service_v2.py::PMOrchestratorServiceV2.execute_workflow + 0`, branches BA échouée, `Coverage check skipped`, architecture partielle ; `_execute_from_phase4`, commentaire `Expert failures are non-fatal` ; `_save_deliverable` ; `B/services/sds_section_writer.py::generate_uc_section_batched + 0`.

**Scénario.** Un lot BA échoué est ignoré si d’autres UC existent. Des UC bruts non parsés suffisent à franchir la porte de comptage, alors que les lecteurs suivants ne prennent que les parsés. L’échec d’Emma Validate devient « completed ». L’échec d’Elena n’empêche pas le SDS final. Un échec d’écriture de livrable est journalisé puis avalé. Les sous-lots de l’annexe sont sautés, mais la suite annonce le nombre total d’UC.

La couverture des spécialistes déclare les agents sélectionnés « intervenus », pas nécessairement ceux ayant réussi.

**Correctif.** Séparer `completed`, `partial`, `failed`, `waiting_validation`. Une étape obligatoire ou une persistance échouée interdit la finalisation. Vérifier couverture BR→UC et présence des sections obligatoires. Les omissions explicitement acceptables doivent être visibles dans l’API **et dans le livrable**, avec accord utilisateur.

**Effort : 12–20 h.**

---

### PROD-08 — La régénération par CR appelle une méthode inexistante puis réussit avec un Markdown minimal

**Gravité : bloquant si les CR sont commercialisées au lancement.**

**Emplacements :** `B/services/pm_orchestrator_service_v2.py::PMOrchestratorServiceV2.execute_targeted_regeneration + 0`, appel `self._generate_word_sds(...)` ; `_generate_markdown_sds`, `_run_ba_with_context`, `_create_sds_version_for_cr`.

**Scénario.** `_generate_word_sds` n’est pas définie dans la classe fournie. L’erreur est capturée et remplacée par un document Markdown de secours ; la CR peut alors être marquée terminée. Les erreurs des agents relancés ne font pas échouer la régénération. Les UC régénérés sont enregistrés comme livrable, sans mise à jour du magasin `deliverable_items` consommé par d’autres générateurs.

Plusieurs versions de CR peuvent pointer le même `SDS_Exec<id>.md`, réécrit.

**Correctif.** Utiliser le générateur réellement supporté, rendre ses erreurs bloquantes, persister les données dans le magasin canonique et créer un fichier immuable par version. Tester qu’une modification demandée apparaît dans le document final et que la version précédente demeure inchangée.

**Effort : 10–16 h**, ou **2 h pour fermer création/exécution de CR initialement**.

---

### PROD-09 — Upload non borné avant lecture, collisions et ingestion disproportionnée

**Gravité : majeur ; bornes minimales avant ouverture Pro.**

**Emplacements :** `B/api/routes/documents.py::upload_document + 0`, `file.file.read()` puis contrôle de taille et écriture sous `safe_filename` ; `_extract_text` ; `B/services/rag_service.py:389–441`.

**Scénario.** La limite de 20 Mo est contrôlée après lecture intégrale. Un document compressé peut produire un volume de texte bien supérieur ; un fichier texte de taille autorisée produit des milliers de chunks et autant d’appels d’embedding séquentiels, puis un unique gros `upsert`.

Deux uploads de même nom créent deux lignes pointant le même fichier ; supprimer l’une supprime le fichier de l’autre. Un parser PDF/DOCX absent provoque une lecture binaire comme texte, potentiellement ingérée comme si elle était valide.

**Correctif.** Lecture bornée `MAX_FILE_SIZE + 1`, limites de texte extrait/pages/chunks/temps, nom disque généré par ID, refus explicite d’un parser absent, ingestion par lots bornés. Fermer le PDF par context manager. Ajouter un quota de stockage/ingestion, indépendant des jetons de génération.

**Effort : 6–10 h.**

---

### PROD-10 — Contrats frontend/API cassés sur les opérations ordinaires

**Gravité : majeur ; correctifs courts à faire avant ouverture.**

**Emplacements :** `F/services/api.ts::apiCall + 0`, `return response.json()` ; `F/pages/ProjectDetailPage.tsx::sendChat + 0`, `submitCR`, `snapshotSDS` ; `B/api/routes/project_chat.py::chat_with_sophie + 0`.

**Scénario.**

- Une suppression réussie en 204 est parsée comme JSON : l’interface affiche un échec après suppression réelle.
- Le chat renvoie `message`, mais la page attend `assistant_message` : **la réponse réussie de Sophie n’apparaît pas**.
- La soumission de CR répond `analyzed`, mais le frontend force `submitted` : le bouton d’approbation disparaît jusqu’au rechargement.
- Le snapshot envoie `{}` alors que l’API exige `execution_id`.
- Une erreur structurée de palier devient `Error("[object Object]")`.

**Correctif.** Aligner les types et consommateurs ; gérer 204 ; conserver `status`, `code`, `detail.message` dans une erreur API structurée. Ajouter des tests de contrat sur ces cinq parcours.

**Effort : 4–6 h.**

---

### PROD-11 — Le wizard n’envoie pas le PDF et perd des informations déterminantes

**Gravité : bloquant pour la promesse d’upload Pro ; majeur pour les autres points.**

**Emplacements :** `F/pages/ProjectWizard.tsx::ActTwo + 0`, `onPickFile` ; `ProjectWizard`, fonction `handleSubmit` ; `F/pages/BRValidationPage.tsx::BRValidationPage + 0`, chargement des BR uniquement au montage.

**Scénario.** Le PDF sélectionné n’est conservé que par son **nom**, jamais uploadé, alors que l’écran annonce que Sophie le lira. Le choix d’édition Salesforce est transformé en choix de produit : Enterprise→Sales Cloud, Unlimited→Service Cloud, deux concepts différents. L’édition, le secteur et la sélection d’agents envoyés ne sont pas tous acceptés/persistés par le schéma de création utilisé.

Après enfilage SDS, le wizard ouvre immédiatement la page BR ; celle-ci peut charger zéro BR et ne se rafraîchit pas à la fin de l’extraction. Un échec de démarrage est aussi absorbé par une navigation vers cette page vide.

**Correctif.** Uploader réellement et attendre l’état d’ingestion avant lancement ; sinon retirer le champ et la promesse. Séparer produit/édition. Naviguer vers le monitoring jusqu’à `waiting_br_validation`. Afficher le refus de lancement, ne pas le transformer en succès de navigation.

**Effort : 6–10 h.**

---

### PROD-12 — Le format « livrable terminé » n’a pas un contrat unique

**Gravité : bloquant Pro.**

**Emplacements :** `B/services/pm_orchestrator_service_v2.py::PMOrchestratorServiceV2._generate_sds_document + 0`, `_execute_from_phase4`, `resolve_export_action` ; `B/api/routes/orchestrator/execution_routes.py::download_sds_document + 0` ; `B/api/routes/sds_versions.py:104–110,175–181` ; `F/pages/ExecutionMonitoringPage.tsx::handleDownload + 0`.

**Scénario.** Le backend accepte un Markdown de secours comme chemin final, puis annonce `COMPLETED`. Les routes de téléchargement annoncent systématiquement du DOCX, même lorsque la version est HTML/Markdown. Le frontend traite au contraire le HTML Jinja comme canonique. La décision « livrable présent » vérifie l’extension, pas l’existence du fichier.

Dans `_generate_sds_document`, le chemin renvoyé par `convert_markdown_to_docx` est ignoré : si le convertisseur change de format, la route peut pointer un DOCX inexistant.

**Correctif.** Définir le format canonique livré le 1er octobre ; persister format, MIME, chemin et état d’export. Ne finaliser qu’après vérification du fichier et du contenu minimal. Un échec d’export doit reprendre **l’export seul**, sans nouvel appel LLM.

**Effort : 8–12 h.**

---

### PROD-13 — Le BUILD ne reprend pas ses tâches et peut terminer une phase incomplète

**Gravité : majeur si BUILD fermé ; bloquant avant ouverture Team.**

**Emplacements :** `B/workers/tasks.py::execute_build_task + 0` ; `B/services/phased_build_executor.py::PhasedBuildExecutor.execute_build + 0`, `generate_phase_batches`, `_generate_single_batch`, `_group_apex_classes`, `_mark_tasks_completed` ; `B/services/pm_orchestrator_service_v2.py::BuildPhaseService.pause_build + 0`.

**Scénario.** Le worker recharge toutes les tâches sans leur statut ; l’exécuteur régénère les phases sans filtre des tâches terminées et sans relecture du drapeau `build_paused`. La pause annoncée ne suspend donc pas ce pipeline. Un retry peut redéployer les phases réussies.

Des lots échoués sont ignorés ; la phase peut déployer les lots restants puis marquer **toutes** ses tâches terminées. Certains tests Apex non appariés sont perdus. Description détaillée, dépendances et caractère manuel/automatisable ne sont pas correctement transportés jusqu’à l’exécuteur.

**Correctif.** Reprise sur tâches/phases persistées, contexte reconstruit, contrôle de pause entre unités, couverture exacte tâches→lots→résultats. Tout lot obligatoire échoué bloque la phase ; ne pas automatiser les tâches manuelles.

**Effort : 14–22 h**, après fermeture des chemins BUILD de Free/Pro.

---

### PROD-14 — Plusieurs contrats Git/SFDX BUILD sont mécaniquement incompatibles

**Gravité : majeur si BUILD fermé ; bloquant avant Team.**

**Emplacements :** `B/services/jordan_deploy_service.py::JordanDeployService.create_phase_pr + 0`, `deploy_phase`, `deploy_source_code` ; `B/services/git_service.py::GitService.create_pr + 0`, `merge_pr` ; `B/services/sfdx_service.py::SFDXService.retrieve_metadata + 0`, `execute_anonymous`, `deploy_with_manifest`, `_run_command`.

**Scénario.**

- `create_phase_pr` appelle `create_pr(branch_name, title, body)` alors que la signature est `(title, body, head_branch, ...)`.
- L’exécuteur lit `pr_result["url"]`, mais Git renvoie `pr_url`.
- `merge_pr` ne renvoie pas le SHA attendu par le rollback.
- Plusieurs extensions SFDX passent déjà le binaire dans `cmd` à `_run_command`, qui le préfixe encore.
- Le déploiement de source temporaire ne garantit pas le projet SFDX/cwd requis.
- Les résultats de branche, commit, retrieval et tag ne sont pas systématiquement exigés pour déclarer le succès.

**Correctif.** Aligner les signatures et schémas de retour ; arguments CLI sans binaire dans `_run_command` ; tests avec faux exécutables vérifiant l’argv exact ; refuser une étape obligatoire échouée. Conserver l’identifiant du déploiement distant et consulter son état après timeout avant tout rejeu.

**Effort : 8–12 h.**

---

### PROD-15 — Les générateurs de métadonnées peuvent perdre ou élargir silencieusement le plan

**Gravité : majeur si BUILD fermé ; bloquant avant Team.**

**Emplacements :** `B/services/sf_admin_service.py::SFAdminService._generate_metadata_files + 0`, `_generate_object_metadata`, `_generate_flow`, `_generate_sharing_rule`, `_generate_permission_set`, `_field_to_xml`, `_deploy_via_sfdx` ; `B/services/jordan_deploy_service.py::PHASE_CONFIGS`.

**Scénario.** Les record types sont collectés mais non émis par le générateur d’objet. Les Flows produits sont des coquilles Draft ; les types inconnus sont ignorés ou transformés en texte. Plusieurs générateurs ajoutent encore `__c` aux objets standards. Les chaînes/formules ne sont pas échappées en XML.

Les permissions manquantes prennent parfois un défaut autorisant lecture/écriture ; la règle de partage est forcée vers tous les utilisateurs internes. La phase automation traite les `operations` mais peut perdre les fichiers XML agrégés ; la phase sécurité attend des fichiers et peut perdre les opérations JSON. Enfin, une exception/expiration de validation XML autorise tout de même le déploiement.

**Correctif.** Schémas d’opérations stricts ; refus des opérations non supportées ; construction XML par bibliothèque ; valeurs de permissions explicites, sans défaut permissif ; déploiement uniquement sur validation positive. Retirer du catalogue les opérations qui ne peuvent pas être réalisées correctement.

**Effort : 14–24 h**, sans nécessité de les ouvrir avec Free/Pro.

---

# 3. Cohérence des paliers et facturation

### BILL-01 — Les crédits ne sont pas réservés atomiquement : dépassements et lignes perdues

**Gravité : bloquant.**

**Emplacements :** `B/services/credit_service.py:254–306`, `preflight` ; `B/services/llm_router_service.py::LLMRouterService._credit_post_charge + 0` et `complete`.

**Scénario.** Deux requêtes passent le préflight sur le même disponible. Les débits lisent puis réécrivent `used_credits` sans verrou : les transactions peuvent totaliser deux débits et le solde n’en refléter qu’un. Le plafond Free, calculé par somme, peut être dépassé par des commits concurrents.

Si le débit final est refusé ou échoue, le routeur journalise CRITICAL mais livre la réponse sans ligne de crédit. Les appels échoués ne créent aucune transaction, contrairement à l’exigence « chaque appel d’un compte produit une ligne ».

**Correctif.** Identifiant unique par appel ; réservation durable et atomique sous verrou du compte/solde avant réseau ; règlement au coût mesuré et libération du reliquat. Une tentative aboutit à un état traçable, y compris débit nul/échec. Les erreurs de règlement doivent rester réconciliables durablement, pas seulement dans un journal.

Tester avec plusieurs connexions PostgreSQL, pas avec SQLite séquentiel.

**Effort : 14–22 h.**

---

### BILL-02 — L’estimation ne couvre ni le vrai prompt ni le plafond réellement envoyé

**Gravité : bloquant, à traiter avec BILL-01.**

**Emplacements :** `B/services/credit_service.py::CreditService.preflight + 0`, `_credits_for_tokens(pricing, max_tokens, max_tokens)` ; `B/services/llm_router_service.py::LLMRouterService._call_gpu_local + 0`, planchers 2 000/6 000 jetons.

**Scénario.** Le préflight assimile le prompt à `max_tokens`, sans compter le prompt système, l’historique ou le RAG. Le routeur augmente ensuite le plafond de sortie à 2 000, voire 6 000. Une classification annoncée à 500 peut donc consommer davantage que ce qui a été contrôlé. Le débit après génération est refusé, puis perdu suivant BILL-01.

À l’inverse, une estimation trop haute refuse un petit message alors que son coût réel tiendrait dans les crédits restants.

**Correctif.** Calculer d’abord la requête effective ; borner/tokeniser entrée et sortie selon le modèle ; réserver ce budget. Si le disponible est insuffisant, réduire explicitement la sortie lorsque possible ou refuser avec un montant expliqué.

**Effort : 4–6 h**, en complément de BILL-01.

---

### BILL-03 — Paiement initial non crédité et renouvellements rejouables

**Gravité : bloquant Pro.**

**Emplacements :** `B/services/stripe_service.py:238–280,302–363`, notamment `330–345` ; `B/services/credit_service.py::CreditService._ensure_balance + 0`.

**Scénario.** Un utilisateur Free ayant consulté son solde possède déjà une ligne à zéro. `subscription.created` change son tier mais ne recharge pas ce solde. L’événement du premier paiement est explicitement ignoré parce que le code suppose cette recharge déjà faite : le nouveau Pro peut rester sans crédits.

Au renouvellement, aucune déduplication d’événement/facture n’empêche plusieurs remises à zéro. Le commentaire dit « seulement subscription_cycle », mais le code accepte tous les motifs sauf `subscription_create`, dès qu’un abonnement est présent.

**Correctif.** Provisionner l’allocation initiale une seule fois ; dédupliquer facture/période sous contrainte unique ; réserver la recharge aux raisons explicitement autorisées. Mise à jour du tier, allocation et marquage de l’événement dans une transaction maîtrisée.

**Effort : 8–12 h.**

---

### BILL-04 — L’état Stripe n’est pas robuste aux événements désordonnés, impayés et abonnements multiples

**Gravité : bloquant Pro.**

**Emplacements :** `B/services/stripe_service.py:140–166,238–300` ; `_handle_invoice_failed` ; `B/api/routes/billing.py::cancel_subscription + 0`, `limit=1`.

**Scénario.** Chaque Checkout peut créer un nouvel abonnement. L’annulation ne traite que le premier actif ; la suppression d’un ancien abonnement rétrograde le compte même si un autre est encore payé. Un événement ancien peut écraser un état plus récent. Les états `past_due` et `unpaid` conservent le tier sans échéance applicative : l’hypothèse « Stripe finira toujours par envoyer deleted » dépend de la configuration de recouvrement, non vérifiée.

Un price inconnu ou un client introuvable est acquitté en 200 et perdu pour la reprise normale.

**Correctif.** Persister l’abonnement canonique et sa période ; dédupliquer puis réconcilier avec l’état Stripe actuel. Interdire les abonnements actifs multiples, traiter changement de formule et grâce explicitement. Conserver les événements non appliqués dans une file de réconciliation.

**Effort : 10–16 h.**

**Point confirmé :** la signature est vérifiée par `stripe.Webhook.construct_event` (`stripe_service.py:198–209`) avant traitement. **Rotation du secret : non vérifiable** sans configuration/preuve fournisseur.

---

### BILL-05 — Les portes Free/Pro sont contournables par des chemins secondaires

**Gravité : bloquant.**

**Emplacements :** `B/api/routes/orchestrator/validation_gate_routes.py::submit_validation_decision + 0`, `_relancer_apres_porte` ; `B/middleware/build_enabled.py::BUILD_PATH_PATTERNS` et `dispatch` ; `B/api/routes/documents.py::upload_document + 0` ; routes CR et snapshots SDS ; `B/workers/tasks.py::execute_build_task + 0`.

**Scénario.** La validation d’une porte peut enfiler un BUILD sans `ensure_feature("build_phase")`. Le middleware ne reconnaît pas ce chemin et laisse passer en cas d’erreur de lecture du profil. Un ancien Team rétrogradé Pro peut ainsi relancer un BUILD en attente. Le worker ne revalide pas les droits.

Les uploads, analyses/régénérations CR et créations de snapshots ne portent pas leurs portes Free. Cela **aggrave** le défaut connu de création de projet Free ; ce n’est pas sa simple redécouverte.

**Correctif.** Contrôler les capacités avant mutation et enfilage, puis au démarrage du job ; refuser par défaut si le profil est illisible. Garde globale d’écriture BUILD pour l’ouverture Free/Pro. Appliquer aussi les limites BR/UC : les helpers actuels ne fournissent pas une application réelle des plafonds.

**Effort : 6–10 h**, en plus du correctif déjà connu de `max_projects`.

---

### BILL-06 — Fermer les projets Free casse le seul parcours de dialogue authentifié disponible

**Gravité : bloquant Free.**

**Emplacements :** `B/api/routes/project_chat.py::chat_with_sophie + 0` ; `B/api/routes/hitl_routes.py::chat_with_sophie_contextual + 0` ; `F/pages/Dashboard.tsx`, `EMPTY_CARDS` ; `F/components/onboarding/WelcomeBanner.tsx:28–38` ; `F/App.tsx`, routes Studio.

**Scénario.** Le dialogue Sophie authentifié exige un projet ; le dialogue multiagent exige une exécution. Le parcours Free conduit au wizard puis à une extraction SDS refusée. Corriger uniquement `max_projects=0` laisse le Free sans son service promis Sophie+Olivia.

Le concierge public ne remplace pas ce service : il ne débite pas les crédits du compte et utilise un autre modèle/parcours.

**Correctif.** Ajouter un petit endpoint de dialogue authentifié hors projet, limité à Sophie/Olivia, tier résolu côté serveur, facturation normale et politique de mémoire conforme au Free. Adapter la page d’accueil Free ; ne pas créer de projet technique caché pour contourner la règle commerciale.

**Effort : 8–12 h.**

---

### BILL-07 — Prix correct, produit vendu incorrect, et abonnement Pro non branché

**Gravité : bloquant commercial.**

**Emplacements :** `F/pages/Pricing.tsx:29–43,64–76`, `handleCta` ; `F/pages/SignupPage.tsx:27–28` ; `F/pages/ProjectWizard.tsx:48–50`, `ActFour` ; `B/models/subscription.py`, `TIER_FEATURES`.

**Scénario.** La page lit bien prix et crédits depuis l’API, mais annonce :
- SDS et un projet en Free ;
- BUILD, Git et SFDX en Pro ;
- projets illimités et templates personnalisés en Team.

La matrice serveur dit autre chose. Le wizard affiche encore des coûts fixes SDS/BUILD et une option Express +20 % sans transmission ni mécanisme d’exécution correspondant. Le CTA Pro ouvre toujours « bientôt », pas Checkout.

Sur une erreur de chargement des tiers, `formatCredits(undefined)` affiche même **« Illimité »**.

**Correctif.** Rendre fonctionnalités et limites depuis la réponse API déjà disponible. Corriger toutes les copies d’inscription/onboarding. Supprimer Express tant qu’il n’existe pas. Afficher « indisponible », jamais « illimité » sur donnée absente. Brancher le parcours Pro seulement après BILL-03/04 ; indiquer clairement HT et vérifier le prix/taxes configurés chez Stripe.

**Effort : 6–10 h.**

---

### BILL-08 — L’arrondi n’est pas un plafond supérieur et les modèles inconnus sont tarifés par ressemblance

**Gravité : majeur ; règle à stabiliser avant la première facture.**

**Emplacements :** `B/services/credit_service.py:122–142`, `_resolve_pricing` ; `backend/alembic/versions/015_free_50_credits_jour.py:7–15` ; `F/pages/Pricing.tsx`, FAQ crédits.

**Scénario.** Le calcul utilise `ROUND_HALF_UP`, pas `ROUND_CEILING`. Par exemple 1,2 crédit brut devient **1**, pas 2. Le minimum de 1 explique le petit message cité en migration 015, mais ne prouve pas un arrondi toujours vers le haut.

Le fallback par sous-chaîne peut tarifer un nouveau modèle « sonnet » au tarif d’une ancienne version et enregistrer celle-ci comme modèle utilisé. `requires_opt_in` n’est pas contrôlé.

**Correctif.** Si l’engagement est bien l’arrondi supérieur :

```python
from decimal import ROUND_CEILING
return int(raw.to_integral_value(rounding=ROUND_CEILING)) if raw > 0 else 0
```

Publier minimum et unité d’arrondi **par appel**. Utiliser des aliases explicites vers un tarif versionné, conserver le modèle réellement servi et appliquer l’opt-in prévu. Ne pas modifier rétroactivement le grand livre sans règle de régularisation.

**Effort : 3–5 h.**

---

### BILL-09 — Le budget public du concierge est calculé à zéro et peut être effacé

**Gravité : bloquant si le concierge reste public.**

**Emplacements :** `B/services/sophie_concierge_service.py::converse + 0`, `force_provider="anthropic/claude-sonnet-4-6"` ; `_check_daily_budget` ; `B/services/llm_router_service.py::LLMRouterService._calculate_cost + 0` ; `backend/config/llm_routing.yaml`, bloc `pricing` ; `B/api/routes/concierge_routes.py::forget_session + 0`.

**Scénario.** Le fournisseur forcé n’a pas de clé correspondante dans le dictionnaire de prix, qui utilise `anthropic/claude-sonnet`. `_calculate_cost` prend alors zéro. Le plafond de 20 USD ne monte donc pas sur ce chemin.

Même avec le tarif corrigé, `/forget` supprime les lignes qui servent à calculer les dépenses : le budget de sécurité dépend de données effaçables par le visiteur. Contrôle et dépense ne sont pas atomiques.

**Correctif.** Résolution tarifaire explicite, refus d’un tarif inconnu, budget opérationnel indépendant des messages personnels et réservation concurrente. Pour le modèle local, borner aussi nombre de requêtes/jetons/concurrence : un coût monétaire nul n’est pas une capacité infinie.

**Effort : 4–6 h.**

---

### BILL-10 — Les coûts USD sont écrits plusieurs fois et le local reçoit un coût fictif

**Gravité : majeur.**

**Emplacements :** `B/services/llm_service.py::generate_llm_response + 0`, `budget.record_cost` ; `B/services/pm_orchestrator_service_v2.py::PMOrchestratorServiceV2._track_tokens + 0`, `_accumulate_cost`, `_calculate_cost` ; `B/services/budget_service.py::_resolve_pricing + 0`.

**Scénario.** Le wrapper LLM enregistre le coût réel, puis l’orchestrateur ajoute encore une estimation. Le zéro légitime du modèle local est considéré comme « coût absent » et remplacé par une estimation cloud. Des écritures concurrentes peuvent aussi perdre des incréments. Le garde-fou de 30 USD peut arrêter un SDS malgré des crédits disponibles.

**Correctif.** Un seul écrivain par métrique ; distinguer zéro et inconnu. Totaux dérivés du journal d’appels ou incrémentés atomiquement. Séparer coût fournisseur USD, crédits client et quota opérationnel local. Raccrocher l’interface à la bonne unité.

**Effort : 4–6 h.**

---

### BILL-11 — Le refus de crédits reste invisible dans le parcours réellement utilisé

**Gravité : majeur ; avant ouverture pour respecter le contrat annoncé.**

**Emplacements :** `F/hooks/useExecutionStream.ts:23–32`, `progressChanged`, `fetchProgress` ; `F/pages/ExecutionMonitoringPage.tsx`, bloc `Failure rescue` ; `B/services/change_request_service.py::ChangeRequestService.analyze_impact + 0`.

**Scénario.** La page utilise du polling via `useExecutionStream`, pas le hook SSE historique. Elle ne lit pas `failure_reason` et propose toujours de rejouer. Un client épuisé répète donc une action impossible.

L’analyse CR capture même `InsufficientCreditsError`, remplace l’analyse par un fallback et retourne `success=True` ; la route ne restitue pas toujours `fallback_used`. Les autres erreurs de budget/circuit breaker n’ont pas de motif structuré.

**Correctif.** Propager des codes d’erreur stables jusqu’à l’interface ; afficher palier, disponible et action utile. Ne pas transformer un refus de crédit en analyse réussie. Inclure ces champs dans la détection de changement et permettre de recharger un état terminal enrichi.

**Effort : 4–6 h.**

---

# 4. RGPD concret

### RGPD-01 — L’export n’est pas exhaustif par rapport à l’inventaire et aux modèles

**Gravité : majeur ; compléter avant ouverture ou prévoir un traitement manuel réellement documenté.**

**Emplacements :** `B/services/account_service.py::AccountService.exporter + 0`, dictionnaire retourné ; `B/models/llm_interaction.py:19–45` ; `docs/vague-b/INVENTAIRE_DONNEES_PERSONNELLES.md`, tableau des 34 tables ; `B/services/sophie_concierge_service.py::_maybe_create_lead + 0`.

**Scénario.** L’export omet notamment :
- les trois champs de consentement ;
- `agent_deliverables`, `execution_artifacts`, `deliverable_items`, `llm_interactions` ;
- tâches, questions, validations, contenus de formation, fusions et orchestration ;
- métadonnées des connexions, credentials et templates personnalisés ;
- contenu des fichiers, pas seulement leurs chemins ;
- les leads, écrits en SQL hors ORM.

Les interactions LLM peuvent avoir `execution_id=NULL`, sans autre propriétaire. L’inventaire fondé uniquement sur les tables ORM manque aussi les stockages écrits en SQL brut et les fichiers de logs agents.

L’exclusion des données Stripe au motif qu’il est sous-traitant ne dispense pas le responsable de traitement de répondre au droit d’accès.

**Correctif.** Matrice automatisée table/stockage→rattachement→export→effacement. Exporter les données personnelles pertinentes sans divulguer les valeurs d’authentification inutiles. Prévoir récupération/communication des données détenues par les sous-traitants et rattachement fiable des interactions hors exécution.

**Effort : 10–16 h.**

---

### RGPD-02 — L’« anonymisation irréversible » annoncée est une pseudonymisation incomplète

**Gravité : majeur.**

**Emplacements :** `B/services/account_service.py::AccountService.supprimer + 0`, étape 8 ; `B/models/user.py:32–42` ; `B/models/credit.py`, `CreditTransaction.note` ; `backend/tests/test_vague_b_b4_droits_rgpd.py::_creer_compte + 0` ; inventaire, paragraphes « anonymisation en place » et « Colonne à venir ».

**Scénario.** `stripe_customer_id` et `consent_ip_hash` restent présents. Les notes du grand livre ne sont pas nettoyées : le test lui-même crée `note="appel LLM de Alice"` puis ne vérifie pas sa disparition. Les contenus libres d’audit et de templates peuvent également conserver des identifiants ; détacher `created_by` ne les anonymise pas.

L’inventaire avait prévu explicitement de vider `consent_ip_hash` après B3 ; l’intégration B3/B4 ne l’a pas fait.

**Correctif.** Vider le hash de consentement à l’effacement, examiner les champs libres et distinguer :
1. données supprimées ;
2. données réellement anonymisées ;
3. pièces personnelles conservées sous obligation légale, accès restreint et échéance.

Ne pas qualifier automatiquement tout le journal de crédits de pièce comptable à conserver dix ans, ni présenter des données réidentifiables via Stripe comme anonymes.

**Effort : 6–10 h**, plus validation limitée de la politique de conservation.

---

### RGPD-03 — Un effacement partiel devient définitif sans possibilité fiable de reprise

**Gravité : bloquant pour l’engagement d’effacement et pour la confidentialité des documents.**

**Emplacements :** `B/services/account_service.py::AccountService.supprimer + 0`, `_purger_chroma`, `_purger_fichiers`, `_racines_de_fichiers` ; `B/services/rag_service.py:444–468` ; `B/api/routes/documents.py::delete_document + 0` ; `B/api/routes/orchestrator/project_routes.py::delete_project + 0`.

**Scénario.** Une erreur Chroma est transformée en zéro suppression ; les références SQL sont quand même détruites. Les fichiers ignorés ne sont pas conservés dans un travail de reprise durable. Supprimer un projet par le CRUD ne nettoie ni Chroma ni les fichiers ; un effacement ultérieur du compte ne retrouve plus ces références.

Les snapshots sont écrits dans `<repo>/outputs`, alors que la racine par défaut de l’effacement est `<repo>/backend/outputs`. Les temporaires SDS et les logs d’agents ne sont pas couverts.

L’effacement ne suspend pas d’abord les tâches en cours et ne résilie pas l’abonnement Stripe : des appels peuvent continuer et le client supprimé peut continuer à payer.

**Correctif.** Désactiver le compte et bloquer les nouveaux travaux d’abord ; enregistrer une tâche durable d’effacement avec toutes les références ; étapes idempotentes, retries et état « en cours/partiel ». Un échec externe doit rester un échec, pas zéro. Répercuter résiliation et instructions d’effacement aux sous-traitants, en préservant seulement les pièces légalement requises.

**Effort : 12–20 h.**

---

### RGPD-04 — La promesse Zero Data Retention du Free est fausse

**Gravité : bloquant commercial et confidentialité.**

**Emplacements :** `F/pages/Pricing.tsx`, `TIER_COPY.free` et FAQ « Where does my data go? » ; `B/services/sophie_chat_service.py::SophieChatService._save_message + 0` ; `B/services/sophie_concierge_service.py::converse + 0` ; `F/pages/ProjectWizard.tsx`, persistance `wizard-draft-*` ; `F/src` non applicable : fichier réel `F/index.css:3`.

**Scénario.** Le Free est annoncé ZDR alors que ses conversations projet sont persistées, le concierge conserve ses messages, le wizard conserve le brief dans le navigateur et les journaux peuvent porter le contenu. Le chargement de Google Fonts fait également communiquer le navigateur avec un tiers absent de l’inventaire applicatif.

**Correctif.** Retirer la promesse ZDR tant qu’elle n’est pas définie et tenue de bout en bout. Pour le dialogue Free prévu en BILL-06, choisir explicitement durée/mémoire, distinguer contenu et journal comptable minimal. Purger les brouillons à la déconnexion/effacement et héberger les polices localement.

**Effort : 3–5 h**, hors endpoint Free de BILL-06.

**Consentement vérifié :** les deux chemins d’inscription montés exigent le consentement CGV ; le frontend part d’une case non cochée. Je ne trouve pas de route d’inscription OAuth ou invitation dans le code transmis : je ne certifie pas des chemins externes absents.

---

# 5. Exploitabilité, diagnostic et reprise

### OPS-01 — A6/B6 laisse un recomptage à froid et une santé RAG faussement verte

**Gravité : majeur.**

**Emplacements :** `B/services/rag_service.py:475–515,584–613` ; `B/main.py::_check_chroma + 0` ; `backend/tests/test_vague_b_b6_health_cache.py::test_cache_vide_au_premier_appel_declenche_un_comptage_synchrone + 0`.

**Scénario.** Avant la fin de la sonde de boot, chaque `/health` trouvant le cache vide peut lancer son propre comptage synchrone : le verrou de rafraîchissement ne couvre pas ce cas. Un premier watchdog peut donc reproduire les délais annoncés corrigés.

Une seule collection non vide rend `ok=True` malgré l’échec des autres. Un rafraîchissement bloqué laisse servir indéfiniment le dernier état vert. Le comptage ne prouve pas que les embeddings ou recherches fonctionnent.

**Correctif.** Cache initial `warming`, un seul calcul en vol, aucune attente disque dans `/health`. Exposer âge et état de rafraîchissement ; seuil maximal de vétusté ; vérifier chaque collection requise et une recherche représentative séparément. Ne pas transformer « état non encore connu » en succès inventé.

**Effort : 4–6 h.**

Le comptage est bien détaché du startup dans le code actuel ; **je n’ai pas remesuré les 90 secondes** et ne reprends pas cette durée comme un fait actuel.

---

### OPS-02 — La sonde « worker health » ne vérifie pas le worker, et les pools Redis fuient

**Gravité : majeur ; sonde réelle avant ouverture.**

**Emplacements :** `B/api/routes/orchestrator/execution_routes.py::worker_health + 0` ; `B/workers/arq_config.py::get_redis_pool + 0` ; `B/workers/worker.py::WorkerSettings` ; `scripts/dh-watchdog.sh`, boucle des services.

**Scénario.** La sonde vérifie Redis, pas le heartbeat ARQ. Elle interroge `LLEN arq:queue:digital-humans`, alors que l’enfilage utilise la file ARQ `digital-humans`, structurée en ensemble trié. Elle peut annoncer zéro alors que des tâches attendent. Le watchdog ne sonde pas le service worker.

Chaque appel à `get_redis_pool()` crée un pool, sans fermeture chez les appelants. Une panne de worker peut laisser l’ensemble du produit immobile avec Redis et `/health` verts.

**Correctif.** Un pool partagé par processus, fermé au shutdown ; vérifier heartbeat réel, âge du plus ancien job, tâches actives et erreurs. Utiliser les API ARQ ou les bonnes clés/opérations. Vérifier la dernière purge réussie ; fixer explicitement le fuseau UTC du cron.

**Effort : 4–6 h.**

---

### OPS-03 — Le correctif SSE a déplacé l’épuisement vers le pool de notifications

**Gravité : majeur.**

**Emplacements :** `B/services/notification_service.py::NotificationService.initialize + 0`, `max_size=5` ; `subscribe`, `await self._pool.acquire()` ; `notify` ; `B/api/routes/orchestrator/execution_routes.py::stream_execution_progress + 0`.

**Scénario.** Chaque abonnement conserve une connexion asyncpg pendant tout le flux. Cinq flux occupent tout le pool ; le sixième attend sans délai d’acquisition, et les notifications utilisent ce même pool. Le fallback ne s’active pas tant que l’acquisition attend. Plusieurs abonnements d’un même canal multiplient aussi les callbacks diffusant à toutes les files.

Le test du pool SSE neutralise expressément ce service : son vert ne couvre pas le chemin complet.

**Correctif.** Pour le lancement, utiliser le polling court déjà disponible et désactiver ce chemin de notifications. Ensuite, une écoute partagée par canal avec acquisition bornée, files bornées et publication non bloquée par les abonnés.

**Effort : 1–2 h pour le repli sûr ; 6–10 h pour corriger les notifications.**

---

### OPS-04 — La piste d’audit mélange les contextes et ne permet pas une corrélation fiable

**Gravité : majeur.**

**Emplacements :** `B/services/audit_service.py::AuditService.__init__ + 0`, `set_request_context`, `_insert_log` ; `B/middleware/audit_middleware.py::AuditMiddleware.dispatch + 0` ; `B/middleware/execution_context.py::ExecutionContextMiddleware.dispatch + 0`.

**Scénario.** `_request_context` est un dictionnaire mutable du singleton. Entre son affectation et la lecture dans le thread d’écriture, une autre requête peut l’écraser. Les adresses et request IDs d’une requête se retrouvent dans une autre.

Le middleware d’audit crée un request ID distinct de celui du contexte de logs, et identifie l’acteur par IP plutôt que par utilisateur authentifié. L’extraction cherche `executions`, alors que nombre de routes utilisent `execute`. Une panne ou un abus devient difficile à reconstruire.

**Correctif.** Passer un contexte immuable explicitement à l’écriture, ou utiliser les `ContextVar` déjà présents. Un seul request ID, renvoyé dans la réponse ; utilisateur authentifié et identifiants de ressource validés. Nettoyage en `finally`. Compteur/alerte sur échec d’écriture d’audit.

**Effort : 4–6 h.** L’IP en clair déjà connue n’est pas recomptée comme nouveau défaut.

---

### OPS-05 — La garde des tests ne protège pas la base réellement utilisée par tous les services

**Gravité : bloquant pour l’application des correctifs en parallèle.**

**Emplacements :** `backend/tests/conftest.py:9–36`, imports `app.main`, `app.database` ; `backend/tests/test_flow_steps.py::test_step_by_step + 0` ; `backend/tests/test_lot_a_ter_sse_pool.py::seeded + 0` ; `B/main.py:4–6`.

**Scénario.** La garde vérifie `TEST_DATABASE_URL`, mais `app.main` charge ensuite `.env` et les services utilisant `SessionLocal` gardent `settings.DATABASE_URL`. Poser une base de test sans remplacer l’URL applicative laisse donc les tests ouvrir/écrire sur la base réelle. Plusieurs fixtures et tests utilisent directement cet engine, hors override `get_db`.

Les clients Stripe, le RAG, Redis et les sondes de startup peuvent également utiliser les configurations réelles. Le danger est particulièrement concret avec plusieurs agents exécutant la suite en parallèle.

**Correctif.** Avant tout import applicatif, imposer la même base jetable à l’application et aux fixtures ; refuser toute divergence. Environnement de test hermétique, sans credentials réels, Chroma/Redis/stockage séparés. Interdire les connexions directes hors fixtures. Ne pas se contenter d’un nom de base rassurant dans un seul moteur.

**Effort : 6–10 h.**

---

### OPS-06 — Plusieurs tests sont verts sans vérifier leur résultat métier

**Gravité : majeur ; recette des bloquants obligatoire avant ouverture.**

**Emplacements :** `backend/tests/test_full_flow.py::test_01_imports + 0` et autres tests retournant un booléen ; `backend/tests/test_flow_steps.py::test_step_by_step + 0` ; `backend/tests/services/test_git_extensions.py` ; `backend/tests/test_vague3_correspondance.py` ; `backend/tests/test_auth.py::test_login_success + 0`.

**Scénario.** Pytest ne transforme pas un `return False` en échec : plusieurs tests capturent leurs exceptions puis retournent un booléen. Les tests d’extensions Git/SFDX vérifient la présence de méthodes, pas leurs arguments. Les tests de reprise attendent le défaut PROD-05. Les tests login continuent à s’inscrire sans le consentement désormais requis ; le test « mauvais mot de passe » peut réussir parce que le compte n’a jamais été créé.

Le pin httpx rétablit une compatibilité, pas une preuve d’aptitude au lancement.

**Correctif.** Assertions sur effets réels, préconditions vérifiées, contrôle positif et négatif ; transport seul simulé lorsque possible. Ajouter des recettes intégrées PostgreSQL/Redis et navigateur : deux clients, quotas concurrents, webhook doublé/désordonné, panne en milieu de SDS, reprise et export final.

**Effort : 8–14 h**, hors tests inclus dans chaque correctif.

---

### OPS-07 — Le schéma diverge aussi sur des colonnes et contraintes, pas seulement sur les tables manquantes

**Gravité : majeur ; vérifier la base SaaS existante avant déploiement.**

**Emplacements :** `backend/alembic/versions/003_add_audit_logs.py::upgrade + 0`, colonne `metadata` ; `B/models/audit.py`, colonne `extra_data` ; `backend/alembic/versions/002_add_artifacts_system.py::upgrade + 0`, `valid_artifact_type` ; `B/schemas/artifact.py:13–25`.

**Scénario.** La migration d’audit crée `metadata`, le modèle écrit `extra_data`. La contrainte des artefacts n’accepte pas `plan`/`review`, pourtant exposés par le schéma API, ni `output`, écrit par le testeur. Les tests par `create_all()` ne reproduisent pas toutes ces contraintes de migration.

Les `downgrade` initiaux laissent également certains types enum créés par leurs tables : un aller-retour peut échouer à la recréation.

**Correctif.** Sur une copie de la base SaaS, comparer colonnes, types, nullabilité, FK et CHECK aux modèles/écrivains. Produire des migrations correctives explicites, avec upgrade/downgrade/upgrade. Ne pas réécrire les migrations déjà déployées et ne pas utiliser `create_all` comme validation.

**Effort : 6–10 h.** L’installation vierge déjà connue reste un chantier distinct.

---

### OPS-08 — Les scripts d’alerte et de rotation peuvent annoncer ou conserver un état faux

**Gravité : majeur.**

**Emplacements :** `scripts/dh-watchdog.sh::send_or_print + 0`, écriture de `STATE` après l’appel ; `scripts/rotate_anthropic_key.sh:26–29`, défaut `/api/health` ; `scripts/ops/export_logs_24h.sh::export_unit + 0`, appel `journalctl`.

**Scénario.** Le watchdog ignore l’échec HTTP Telegram et enregistre quand même l’état comme notifié, supprimant les tentatives suivantes. Sans credentials, il sort avec succès sans alerte locale.

Le script de rotation sonde `/api/health`, absent du backend fourni : il peut restaurer l’ancienne clé après une rotation réussie. Ses curls n’ont pas tous de délai. L’export de logs ignore l’échec de `journalctl` et peut remplacer un export exploitable par du vide.

**Correctif.** Vérifier transport **et résultat API** des alertes ; enregistrer l’état seulement après succès ; journaliser les configurations absentes avec code non nul. Utiliser `/health`, délais bornés et rollback testé. Conserver l’ancien export si la collecte échoue. Vérifier les scripts effectivement installés, pas seulement leur copie git.

**Effort : 3–5 h.**

---

### OPS-09 — Le build frontend strict contient au moins un échec statique identifiable

**Gravité : majeur ; corriger avant livraison des assets.**

**Emplacements :** `frontend/tsconfig.app.json:24–25`, `noUnusedLocals`/`noUnusedParameters` ; `F/components/studio/ChatSidebarStudio.tsx::ChatSidebarStudio + 0`, destructuration `const { t, lang } = useLang()` ; `frontend/package.json:8`.

**Scénario.** `lang` n’est pas utilisé dans ce composant. Avec `noUnusedLocals=true` et `tsc -b` dans le script de build, c’est un diagnostic bloquant de compilation. Les anciennes sorties « TSC OK » ne certifient pas l’arbre transmis.

**Correctif.** Retirer la variable inutilisée et faire exécuter le build complet de l’artefact livré. Je ne fournis pas un décompte supposé des erreurs TypeScript : **aucune compilation n’a été exécutée**.

**Effort : 1–2 h**, vérification de l’ensemble incluse.

---

## Table séparée des déclarations vérifiées

**« Confirmé » ci-dessous signifie confirmé par lecture du code transmis, jamais validé sur le VPS.**

| Réf. | Verdict | Vérification et limites |
|---|---|---|
| **A1** | **incomplet** | Pin `httpx>=0.27.0,<0.28` présent, `backend/requirements.txt:23–26`. La réexécution des 118 tests n’a pas été reproduite ; les assertions et l’isolation présentent les défauts OPS-05/06. |
| **A3/012** | **confirmé** | Migration 012 fixe 79 € et 15 000 ; `B/models/subscription.py`, entrée Pro, vaut 79 ; `Pricing.tsx` affiche le prix de `/tiers`, servi depuis la table. Cela ne confirme ni le Price Stripe réel ni la cohérence des fonctionnalités, BILL-07. |
| **A5** | **confirmé** | `B/services/sophie_concierge_service.py::converse` n’appelle pas le RAG ; le routeur LLM non plus. Le test contient espions et sentinelle avec contrôle négatif pertinent. La sécurité du RAG général reste défectueuse, SEC-04. |
| **A6/B6** | **incomplet** | Comptage de boot lancé en tâche de fond ; cache TTL 1 800 s présent. `rag_service.py:605–608` recompte encore sur cache vide ; concurrence à froid et vétusté non bornées, OPS-01. |
| **A9** | **confirmé** | Sonde de modèles locaux branchée au startup ; `_call_gpu_local` envoie et rapporte `model_id`, non l’alias. Test `test_hotfix_gpu_model_id.py::test_vllm_recoit_le_model_id_pas_la_cle` pertinent. Disponibilité réelle du tunnel non testée. |
| **B1** | **contourné** | Propriétaire obligatoire et chemin `sans_compte` présents ; propagation par exécution/contexte réelle. Mais testeur imputé au compte 2, appels blog hors routeur et lignes perdues après préflight : SEC-02/11, BILL-01/02. CRITICAL existe, mais ne remplace pas le grand livre. |
| **B2/014** | **incomplet** | Tarif Nemotron 0,2/1,0 posé ; Free forcé local sous `cloud`, et profil `test_gpu_complet` tout local. Certains appels HITL/CR passent `user_id` sans résoudre son tier ; le profil `freemium` reste Sonnet. Le modèle effectif ne doit pas dépendre de l’omission du contexte de palier. |
| **B3/013** | **confirmé** | Colonnes présentes ; `/register` et `signup-request` exigent consentement/version ; `signup-confirm` exige la preuve signée. Case frontend non cochée. Aucun chemin OAuth/invitation trouvé dans les sources transmises. SEC-12 concerne la vérification d’adresse, pas l’absence de case CGV. |
| **B4** | **incomplet** | Routes montées, contrôle du compte présent, suppression/anonymisation implémentées. Export incomplet, consentement non nettoyé, rattachement des sessions par e-mail non fiable, Stripe et suppressions externes non réconciliés : SEC-12, RGPD-01/03. |
| **B5** | **incomplet** | Suppression sur `created_at < maintenant−365 jours`, fermeture de session et cron 03:17 présents. UTC non fixé explicitement ; erreur retournée `-1` plutôt que tâche échouée ; dernière réussite non surveillée. `B/workers/retention.py::purge_chat_logs_task`, `worker.py::WorkerSettings`. |
| **B7** | **contourné** | Prix/crédits de `Pricing.tsx` et substitution `tier_summary` effectivement dynamiques. Mais coûts fixes dans le wizard, prix dans d’autres réponses d’abonnement, limites/capacités marketing incorrectes et fallback « Illimité ». Le YAML du prompt lui-même n’est pas fourni. |
| **015** | **confirmé** | `015_free_50_credits_jour.py::upgrade` fixe bien 50/jour et sa description. Le service lit ce plafond en base. Cela ne certifie pas sa résistance à la concurrence ni un arrondi supérieur : BILL-01/08. |
| **Hotfix 05/09** | **contourné** | Le chat projet vérifie bien succès et contenu non vide. Le chat HITL et le concierge ne contrôlent pas correctement un résultat LLM négatif retourné sans exception ; le transport GPU peut encore déclarer un contenu vide réussi. Le frontend projet ignore par ailleurs le champ `message` valide, PROD-10. |

**Complément nécessaire au hotfix :** centraliser le contrat de réponse LLM : une réponse vide, tronquée ou remplacée par `reasoning_content` n’est pas une réponse finale valide. Ne pas exposer automatiquement le raisonnement interne comme réponse client. Emplacements : `B/services/llm_router_service.py::LLMRouterService._call_gpu_local`, `B/api/routes/hitl_routes.py::chat_with_sophie_contextual`, `B/services/sophie_concierge_service.py::converse`. **Bloquant pour les chats ouverts ; 3–5 h**, à intégrer au lot PROD-01/02.

---

# Feuille de route

## Lot 1 — Avant le 1er octobre

**Ordre par risque évité / effort. Les fermetures temporaires sont des correctifs serveur testés, pas des arbitrages reportés au frontend.**

| Ordre | Travail | Critère de sortie |
|---:|---|---|
| **1** | **Révoquer les secrets supplémentaires et fermer les surfaces internes** — SEC-01/02/11 ; fermer aussi l’API autonome Ghost si déployée. | Aucun outil interne accessible avec un simple compte ; aucun jeton Admin fourni publiquement ; révocations attestées sans exposer les valeurs. |
| **2** | **Environnement de correction sûr** — OPS-05. | Les suites et agents de développement ne peuvent joindre aucune base, file, org ou clé de production. |
| **3** | **Fuites interclients à correctif court** — SEC-05/06/19 ; puis SEC-12. | A ne lit/modifie/supprime rien de B, y compris contexte LLM, références secondaires, fichiers et conversations concierge. |
| **4** | **Neutraliser les contenus actifs et sorties réseau non autorisées** — SEC-09/10/15 ; SEC-03 pour les chemins conservés. | HTML malveillant inerte ; secrets absents des prompts/logs ; destinations réseau bornées ; aucune écriture hors racine. |
| **5** | **Fermer toutes les écritures BUILD pour Free/Pro** — SEC-08, BILL-05, contrôles worker compris. | Démarrage, retry, validation de porte et appel direct de service refusés sans effet de bord. |
| **6** | **Sécuriser le RAG avant données réelles** — SEC-04, PROD-09, RGPD-03. | Recherches publiques/projet A excluent B ; suppression en panne reste reprenable ; documents bornés. |
| **7** | **Grand livre et Stripe** — BILL-01/04/08/09 ; coûts USD BILL-10. | Solde = journal ; concurrence ne dépasse pas les plafonds ; paiement initial crédite ; doublon/désordre ne recharge pas deux fois ; impayé traité explicitement. |
| **8** | **Stabiliser LLM, jobs et reprises** — PROD-01/07/12 et hotfix généralisé. | Panne injectée après chaque phase : pas de travail oublié, pas de succès partiel caché, pas de retry concurrent, export seul sans nouveau LLM. |
| **9** | **Parcours réellement vendus** — BILL-06/07/11, PROD-10/11, OPS-09. | Free dialogue sans projet ; Pro souscriptible ; PDF réellement utilisé ou fonction retirée ; prix, capacités et messages conformes. |
| **10** | **Dépendances, posture de déploiement et sondes minimales** — SEC-17/18, OPS-01/02/08. | Artefact compilé, versions auditées, debug désactivé, worker et LLM réellement surveillés, alerte de bout en bout reçue. |
| **11** | **Recette indépendante de fermeture** — OPS-06. | Tests négatifs et positifs sur l’artefact exact, copie réaliste du schéma SaaS et deux tenants ; preuves enregistrées par scénario. |

**Pour limiter le temps humain :** quatre files parallèles — **sécurité**, **crédits/Stripe**, **pipeline/reprise**, **parcours/recette** — avec un intégrateur désigné par fichier partagé. Ne pas attribuer simultanément plusieurs modifications indépendantes de `pm_orchestrator_service_v2.py` sans propriétaire d’intégration.

**Trois décisions humaines suffisent :**
1. périmètre exact ouvert et fonctions explicitement fermées ;
2. modèle Pro et promesse correspondante, à arrêter avant la recette finale ;
3. politique de conservation des données personnelles et pièces nécessaires.

Les vérifications techniques, les tests négatifs et la cohérence des contrats ne doivent pas devenir des dizaines de demandes d’arbitrage.

---

## Lot 2 — Dans les trente jours suivant l’ouverture

1. Compléter l’export et la politique d’anonymisation/conservation — **RGPD-01/02**, si une procédure manuelle effective couvre l’intervalle.
2. Corriger la piste d’audit et la corrélation — **OPS-04**.
3. Fermer les derniers écarts de révocation et de limitation de débit — **SEC-14/16**.
4. Corriger les contraintes/migrations supplémentaires sur copie réaliste — **OPS-07**.
5. Si retirées du lancement, rétablir les CR et portes configurables **après** recette de leur cycle réel — **PROD-06/08**.
6. Si le concierge/leads reste fermé, corriger opt-in et budget avant réactivation — **SEC-13, BILL-09**.
7. Remplacer les tests de présence et les faux succès restants par des tests de comportement — **OPS-06**.

---

## Lot 3 — Plus tard, avant activation des fonctions concernées

1. **BUILD/Team :** SEC-03/07/08 et PROD-13/15, puis recette réelle complète sur sandbox dédiée, avec interruption, reprise et rollback. Aucun simple test d’import ne vaut validation.
2. Réouverture éventuelle du testeur interne avec autorisation opérateur et isolation — **SEC-02**.
3. Réparer le service de notifications si son bénéfice justifie de le réactiver — **OPS-03** ; le polling sûr suffit au lancement.
4. Résoudre l’installation vierge Alembic déjà connue avant toute offre on-premise ; conserver séparément le nettoyage de l’ancien mot de passe PostgreSQL et des chemins historiques.
5. Nettoyage des routeurs non montés et services morts, sans les remettre en service par accident.

**Décision finale :** une ouverture Free/Pro est envisageable avec un périmètre réduit mais honnête et techniquement fermé. **L’état actuel ne permet pas de soutenir les déclarations « isolation client », « plafonds stricts », « reprise sûre » et « effacement réalisé » qui conditionnent cette ouverture.**