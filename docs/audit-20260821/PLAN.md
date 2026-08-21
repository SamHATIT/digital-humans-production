# Plan d'exécution — vague 1

Sept lots. Un lot = un agent = un périmètre de fichiers **exclusif**.
Deux agents ne touchent jamais au même fichier : c'est la contrainte qui
commande le découpage. Sept fichiers concentrent l'essentiel des constats
(`main.py` en porte 7, venus de 4 modèles) — y faire travailler plusieurs
agents en parallèle produirait des conflits, pas du gain.

**Un lot n'est clos que si son critère de fin est démontré par une commande.**

---

## LOT-A · Frontière payante — priorité 1

Signalé par les **quatre** modèles. 15 constats convergents.

**Fichiers** `backend/app/utils/feature_access.py` · `api/routes/orchestrator/build_routes.py` · `api/routes/orchestrator/execution_routes.py` · `middleware/build_enabled.py` · `models/subscription.py`

**Constats** cla:TIER-01, cla:TIER-02, gem:BIZ-01, kim:TIER-01, kim:TIER-02, ope:TIER-01

Le décorateur `require_feature` existe déjà (`feature_access.py:54`). Sa seule
occurrence dans tout le code est son propre exemple de docstring, ligne 60.
Le garde-fou a été écrit et jamais posé. Un compte gratuit peut donc produire
ce qui est vendu 79 €, et probablement déclencher le BUILD facturé 1 490 €.

**Fin** — compte Free → 403 sur `POST /api/pm-orchestrator/execute` ;
compte Pro → 403 sur déclenchement BUILD ; les deux couverts par un test.

## LOT-B · Authentification et cloisonnement client — priorité 1

3 modèles / 4. Kimi signale des **routeurs entiers** exposés, dont un qui
exécute des déploiements.

**Fichiers** `api/routes/` : `artifacts.py` `deployment.py` `deliverables.py` `sds_versions.py` `quality_dashboard.py` `change_requests.py` `documents.py` `analytics.py`

**Constats** cla:SEC-01, kim:SEC-01, kim:SEC-05

Ajouter `Depends(get_current_user)` où il manque. Sur chaque accès à une
ressource, vérifier la **propriété**, pas seulement l'authentification.

**Fin** — utilisateur A → 403/404 sur toute ressource de B. Test par routeur.

## LOT-C · Injections et exécution de commandes — priorité 1

**Fichiers** `api/routes/agent_tester.py` · `services/agent_executor.py` · `services/pm_orchestrator_service_v2.py` (lignes subprocess uniquement)

**Constats** gem:SEC-01, gem:SEC-02, kim:SEC-01, kim:SEC-02, kim:SEC-03

État : route bloquée au frontal nginx (403) le 21/08. Pansement, pas correctif.
`shell=True` subsiste à **quatre** emplacements. Traiter aussi les deux
traversées de répertoire (kim:SEC-03), puis retirer le blocage nginx.

**Fin** — `grep -rn "shell=True" backend/app` ne renvoie rien ;
route → 401 sans jeton, 200 avec.

⚠ Touche `pm_orchestrator_service_v2.py` : passe **avant** LOT-G.

## LOT-D · Plantages fonctionnels — priorité 1

**Fichiers** `backend/agents/roles/` : `salesforce_business_analyst.py` `salesforce_pm.py` `salesforce_trainer.py` `salesforce_devops.py` `salesforce_admin.py`

**Constats** kim:PROD-01, kim:PROD-03, cla:CRASH-02..05

`PROD-01` **vérifié dans le code le 21/08** — `salesforce_business_analyst.py:337` :

```python
if batch_mode:
    prompt = get_uc_generation_prompt_batch(brs, rag_context)
logger.info(f"...{len(prompt)}...")   # NameError si batch_mode faux
```

Pas de `else`. L'orchestrateur envoie par lots de 2 : **tout projet à nombre
impair de BR perd son dernier cas d'usage**, silencieusement, après avoir payé
les appels précédents. Correctif : 2 lignes.

**Fin** — un SDS à 3 BR produit 3 UC complets. Test avec nombre impair.

## LOT-E · Secrets et configuration — priorité 1

**Fichiers** `app/config.py` · `app/utils/encryption.py` · `app/services/rag_service.py` · `app/services/sf_admin_service.py` · `.env` · `backend/.env`

**Constats** cla:SEC-03, cla:SEC-05, cla:INTEG-03, gem:CONF-01, kim:SEC-06, kim:PROD-10, kim:COH-05

**P8 non corrigé** : `encryption.py` admet dans sa docstring que le script de
ré-encryption n'existe pas. Procédure écrite, pas capacité.
**P12 non corrigé** : `rag_service.py` relit le second `.env` en repli
silencieux — ce défaut a coûté du temps le 21/08 (deux clés OpenAI, une morte).

**Fin** — un seul `.env` fait autorité ; aucun chemin absolu résiduel ;
le script de rotation s'exécute sur une base de test.

## LOT-F · Frontend — jetons et injection — priorité 1

**Fichiers** `frontend/src/services/api.ts` · `components/ChatSidebar.tsx` · `services/deliverableService.js` · `services/pmService.ts`

**Constats** cla:SEC-02, ope:SEC-01, ope:SEC-04, ope:SEC-05, ope:REL-01, kim:SEC-07, kim:DEBT-04

Un message d'agent contenant du HTML malveillant s'exécute aujourd'hui dans le
navigateur (`dangerouslySetInnerHTML`), et le jeton est lisible dans
`localStorage`. Supprimer aussi les services appelant des routes inexistantes.

**Fin** — aucun `dangerouslySetInnerHTML` sur contenu d'agent ; aucun jeton en
URL ; aucun appel vers une route absente du backend.

## LOT-G · Sessions, async, démarrage — priorité 2, après LOT-C

**Fichiers** `app/main.py` · `services/llm_service.py` · `services/budget_service.py` · `api/routes/chat_ws_routes.py` · `services/sophie_concierge_service.py`

**Constats** cla:CRASH-01, cla:OPS-01, cla:OPS-02, kim:PROD-02, kim:PROD-05, kim:SEC-03

`main.py` porte 7 constats de 4 modèles — fichier le plus chaud, **un seul agent**.
P0 a reparu sur trois endpoints temps réel (SSE, WebSocket, concierge public).

**Fin** — aucune session pendante après 100 exécutions ; `/health` échoue si la
base est arrêtée.

---

## Ordre

**En parallèle** : A · B · D · E · F (périmètres disjoints)
**Puis** : C
**Enfin** : G

## Hors périmètre

La reprise des builds entre workers se compte en semaines et conditionne le
palier 100 clients. Décision du 21/08 : hors périmètre pour le 1er octobre.
