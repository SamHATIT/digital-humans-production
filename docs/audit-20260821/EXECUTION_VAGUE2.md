# Exécution de la vague 2 — audit croisé du 21/08/2026

Branche `claude/new-session-ihss3x`, issue de `correctifs/audit-croise-20260821`
à `1438431` · 4 commits · 31 fichiers · +3227 / −171

Périmètre : `EXECUTION.md` §5, découpé en quatre lots par `PROMPT_VAGUE2.md`.
Rien hors de ce périmètre n'a été modifié. Ce qui a été trouvé au passage et
n'y appartient pas est en §5, décrit et non corrigé.

**Un lot = un commit.** Chaque correctif a un test rouge avant / vert après,
dont la sortie est citée. Les quatre constats de la vague 1 déclarés faits sans
l'être ont enseigné que la relecture ne suffit pas ; la vague 2 en a trouvé un
cinquième, et cette fois c'est **le test lui-même** qui mentait (§4.1).

---

## Suite de tests — avant / après

| | échecs | passés | xfail | erreurs |
|---|---|---|---|---|
| Point de départ **annoncé** par `EXECUTION.md` | 14 | 389 | 0 | 0 |
| Point de départ **mesuré** à `1438431` | **15** | **388** | 0 | 0 |
| Après la vague 2 | **9** | **456** | **6** | 0 |

Deux écarts à expliquer, aucun n'est une régression.

**Le point de départ annoncé ne tient pas à la tête déployée.** Le 15ᵉ échec est
`test_lot_b_cloisonnement::test_deployment_cloisonnement`, et il est causé par
`1438431` lui-même — le commit qui démonte le routeur `deployment`. Le test
attend `401` sur `POST /api/deployment/promote` ; la route n'existe plus, donc
`404`. Le chiffre 389/14 a été mesuré **avant** ce commit. Non corrigé : le
périmètre gèle `deployment.py`, et le test est correct — c'est sa cible qui a
disparu. Voir §5.1.

**Les 6 disparus des échecs sont exactement les 6 marqués `xfail`** dans
`test_sf_admin_service.py` (§3.6). Les 9 restants sont la même liste nominative
qu'au départ : `test_credit_service.py` (4), `test_auth.py` (3),
`test_emma_phase3.py` (1), `test_lot_b_cloisonnement.py` (1). Tous préexistent
et sont hors des quatre lots.

**Deux suites, pas une.** Le frontend n'avait aucun exécuteur de tests. Les
correctifs frontend de LOT 3 sont prouvés par le runner intégré de Node, **sans
ajouter une seule dépendance** :

```
cd frontend && node --experimental-strip-types --test "tests/*.test.ts"
# tests 22 / pass 22 / fail 0
```

`npx tsc -b --noEmit` et `npx vite build` passent.

---

## 1. Comment reproduire — l'environnement de test

Ce n'est pas une note de confort : monter l'environnement a produit trois
constats, dont un qui invalide un critère de fin de la vague 1.

```bash
service postgresql start
su postgres -c "psql -c \"CREATE ROLE dhtest LOGIN SUPERUSER PASSWORD 'dhtest'\""
su postgres -c "createdb -O dhtest digital_humans_test"

cd backend
python3 -m venv venv
venv/bin/pip install -r requirements-test.txt

export TEST_DATABASE_URL="postgresql://dhtest:dhtest@127.0.0.1:5432/digital_humans_test"
export SECRET_KEY="…"
venv/bin/python -m pytest tests/ -q
```

`requirements-test.txt` est neuf (LOT 1b) et **fait autorité** : la suite
s'installe avec lui et rien d'autre.

---

## 2. LOT 1 — débloquer l'E2E BUILD FormaPro *(commit `57ee795`)*

### 2.1 `resume_from="build_tasks"` était une valeur morte — **confirmé**

`retry_routes.py:78` posait `resume_from = "build_tasks"` dès qu'une
`TaskExecution` était en échec, puis enfilait `execute_sds_task`.
`execute_workflow` ne teste que quatre valeurs, dispersées dans le corps de la
méthode : `phase1`/`phase1_pm` (`:377`) et `phase4`/`phase5` (`:488`).
`build_tasks` tombait donc dans la branche générique « saute la phase 1 » et
**rejouait le SDS à partir de la phase 2**.

Coût réel : un retry après échec de tâches BUILD repayait Olivia, Emma, Marcus
et les experts pour des livrables déjà en base, et ne reprenait **aucune** tâche
BUILD. C'est le défaut qui rendait la mesure du coût d'un BUILD impossible.

**Correctif, après vérification des appelants (règle 2).** `build_tasks` n'a
qu'un seul émetteur, `retry_routes.py:78`. Et le BUILD a déjà son point
d'entrée : le job ARQ `execute_build_task`, utilisé par `/resume-build`, qui
relit les `TaskExecution` et reprend celles qui ne sont pas terminées. Rien à
reconstruire : le retry enfile ce job-là. La reprise BUILD ne se porte pas par
un `resume_from` mais par l'état des tâches, que le retry remet à `PENDING`
juste avant.

Côté service, `execute_workflow` **refuse** désormais un point de reprise BUILD
au lieu de dégrader en silence, et journalise en WARNING toute valeur hors du
vocabulaire reconnu — désormais nommé (`SDS_RESUME_POINTS`,
`BUILD_RESUME_POINTS`). C'est ce WARNING qui a révélé §5.2.

Preuve :

```
$ pytest tests/test_vague2_lot1_build_resume.py
AVANT : 4 failed, 2 passed
  AssertionError: un retry de taches BUILD doit reprendre le BUILD ;
  job enfile : execute_sds_task
  (kwargs={… 'resume_from': 'build_tasks', '_queue_name': 'digital-humans'})
APRÈS : 6 passed
```

### 2.2 Environnement de test incomplet — **partiellement infirmé**

Le constat disait « `python-docx` et `chromadb` sont absents des dépendances de
test ». **Ils sont tous les deux dans `requirements.txt`.** Ce qui manquait
n'était pas la déclaration, c'était un fichier disant *ce qu'il faut installer
pour lancer la suite* — d'où des environnements partiels où ces deux imports
tombaient. L'effet décrit était donc réel, la cause non.

Et un **troisième** paquet manquait au tableau, plus grave que les deux nommés.
`requirements.txt` demande `httpx>=0.27.0`. httpx 0.28 a retiré le raccourci
`Client(app=…)`, sur lequel repose le `TestClient` de starlette 0.27
(fastapi 0.104.1). Mesure sur un environnement neuf, avant tout correctif :

```
78 errors — TypeError: Client.__init__() got an unexpected keyword argument 'app'
```

Ces 78 erreurs frappent `test_lot_b`, `test_lot_c` et `test_lot_g` — c'est-à-dire
**les tests qui portent les critères de fin des lots B, C et G de la vague 1**.
Un contributeur qui installe aujourd'hui depuis `requirements.txt` ne peut pas
rejouer ces critères. Le plafond `httpx<0.28` vit dans
`requirements-test.txt` : c'est le TestClient qui contraint, pas le code
applicatif.

Preuve : `ModuleNotFoundError: No module named 'docx'` → `test_orchestrateur_importable`
et `test_dependances_lourdes_de_l_orchestrateur_presentes` passent.

### 2.3 Garde `DATABASE_URL` dans `conftest.py` — **confirmé, fait**

`conftest.py` se replie sur `DATABASE_URL` faute de `TEST_DATABASE_URL`, et la
fixture `db_session` fait `create_all` puis **`drop_all` après chaque test**.
Sur le VPS, le service et l'arbre de travail déployé lisent le même
`backend/.env` : `DATABASE_URL` y pointe la base réelle.

`tests/db_guard.py` refuse de démarrer. Le critère est **conservateur par
construction** : on refuse ce qu'on ne peut pas prouver jetable, plutôt que
d'accepter ce qu'on n'a pas su reconnaître comme réel. Une simple liste noire
laisserait passer la prochaine base de production, qui portera un autre nom.
Dérogation par `DH_ALLOW_NON_TEST_DB=1`, qui journalise en WARNING.

**Un détail qui n'en est pas un** : la garde est posée **avant** l'import de
`app.main`. Cet import ouvre déjà une connexion et, avant LOT 4, exécutait
`create_all()`. Posée après — c'était ma première version — elle refusait la
suite *après* avoir écrit dans la base qu'elle protège. C'est le test
end-to-end qui l'a montré, pas la relecture.

Preuve :

```
$ DATABASE_URL=postgresql://…/digital_humans_db pytest tests/test_auth.py
ProductionDatabaseError: Refus de lancer la suite de tests : la base visee est
'digital_humans_db', connue comme base reelle.
    export TEST_DATABASE_URL=postgresql://user:pass@127.0.0.1:5432/digital_humans_test
$ pytest tests/test_vague2_lot1_garde_database_url.py
15 passed
```

---

## 3. LOT 2 — cloisonnement et cohérence *(commit `9d6d3de`)*

`tests/test_vague2_lot2_cloisonnement.py` : **15 failed / 4 passed → 19 passed**.
Les 4 verts d'emblée sont les contrôles positifs et de non-régression.

### 3.1 `audit_service.get_logs()` sans notion de propriétaire — **confirmé**

`owner_user_id` devient un mot-clé **obligatoire et sans défaut** sur
`get_logs`, `get_execution_timeline` et `get_task_history`. L'omettre est une
`TypeError`, pas un journal global silencieux. Un appelant système passe la
sentinelle `ALL_OWNERS`, nommée et assumée.

Deux points qui décident de la qualité du correctif :

- **Le filtre est dans le SQL**, pas appliqué après coup. Filtrer les lignes
  rendues fausserait `limit`/`offset` : une page pleine de lignes d'autrui
  devient une page vide alors qu'il restait des lignes à rendre. Un test le
  vérifie explicitement (5 lignes de B, 3 de A, `limit=3` → 3 lignes de A).
- **Les lignes à `project_id NULL`** (auth.login, auth.fail, événements
  système) ne sont pas atteignables avec un `owner_user_id`. C'est la décision
  déjà prise et documentée par LOT-B bis, désormais portée par le service et
  non par la route.

Les vérifications de propriété de `api/audit.py` restent : elles rendent 404 sur
une ressource d'autrui au lieu d'une liste vide, ce que le filtre du service ne
sait pas faire. Elles ne sont plus le seul rempart.

### 3.2 `change_requests.py` : `related_br_id` non validé — **confirmé**

Création et mise à jour recopiaient l'entier tel quel.
`_resolve_related_br()` résout le BR **dans le projet de la CR** ; un id hors
projet est un 404 (on ne confirme pas l'existence d'une ressource d'autrui).

Ajout non demandé mais nécessaire : `_related_br_text()` borne aussi la
**lecture** au projet de la CR. Une ligne déjà corrompue en base — écrite avant
ce correctif — rendrait sinon toujours le texte du BR d'autrui. Fermer
l'écriture sans fermer la lecture aurait laissé la fuite ouverte sur l'existant.
Un test couvre ce cas.

### 3.3 `kim:PROD-10` — **confirmé, et plus large que décrit**

Les deux chemins d'écriture sont confirmés : `routes/projects.py` posait le
secret **en clair** dans `project_credentials.encrypted_value`, `wizard.py`
passait par `EnvironmentService` et le chiffrait en Fernet. Même colonne, deux
formats, selon l'écran utilisé.

Deux volets que le constat ne nommait pas :

- **La lecture.** `test-salesforce` prenait `cred.encrypted_value` tel quel et
  l'envoyait à Salesforce comme `client_secret` — donc du Fernet
  (`Z0FBQUFB…`) dès que le wizard avait écrit la ligne. L'authentification
  échouait sans que le message le dise.
- **Le jeton Git.** Le même fichier l'écrivait aussi en clair. Or
  `jordan_deploy_service` **refuse** depuis LOT-E bis un jeton en clair au
  déploiement (cla:SEC-03) : cette route produisait des lignes que l'aval
  rejette. Le correctif de LOT-E bis était donc contourné par l'écran de
  configuration.

Trois helpers font le chemin unique (`_store_project_credential`,
`_read_project_credential`, `_read_salesforce_oauth_credentials`), tous délégant
à `EnvironmentService` comme `wizard.py`.

**Piège du chemin unifié**, trouvé par un test et non par relecture :
`store_credential` supprime puis recrée la ligne. Modifier la seule clé
consommateur effacerait le secret. La valeur courante est relue et fusionnée, et
rien n'est écrit tant que les deux moitiés ne sont pas connues.

### 3.4 `pm_orchestrator_service_v2` — repli `sf_cfg` — **confirmé, fait**

Quand la résolution du projet échouait, `sf_cfg = salesforce_config` prenait la
config globale. Depuis LOT-E bis elle n'emprunte plus d'identité, mais elle
échouait **plus bas**, sur un message parlant de l'org par défaut, alors que le
vrai défaut est qu'on ne sait pas de quel projet il s'agit. `project is None`
rend maintenant `{"success": False, "error": "no_project_resolved"}` avec un
ERROR qui le dit.

**Distinction conservée** : « projet connu mais sans `sf_instance_url` » garde
l'org par défaut du déploiement. C'est un choix légitime, vide par défaut, et
`require("org_alias")` refuse plus bas — `EXECUTION.md` §6.6. Refuser les deux
cas aurait cassé le comportement voulu.

### 3.5 `quality_dashboard.py` `/execution/{id}` — **confirmé, fait**

Le SELECT demandait `validation_status` et `validation_errors`, absentes de
`task_executions` (vérifié dans `app/models/task_execution.py`). PostgreSQL
rendait un `UndefinedColumn`, capté par le `except Exception` et réémis en 500.
La route était morte pour tout le monde, propriétaire compris.

Les deux colonnes sont retirées du SELECT. **Aucune des deux n'était lue** — la
boucle n'utilise que `task_id` et `generated_files`. Les ajouter serait de la
fonctionnalité, pas un correctif.

---

## 4. LOT 3 — observabilité et petits défauts réels *(commit `70a4a34`)*

### 4.1 `redis` et `chroma` absents de `/health` — **confirmé, fait**

`_check_redis` (ping, timeout 2 s) et `_check_chroma` (`rag_health_check`,
0 chunk = down) rejoignent `_check_database`. **Une seule dépendance morte
suffit à rendre 503.** Les trois sondes partent en `asyncio.to_thread`, en
parallèle — elles sont bloquantes par nature (socket, disque).

Pourquoi ces deux-là comptent : Redis porte la file ARQ, donc sans lui
`enqueue_job` échoue et **aucune exécution ne démarre**. ChromaDB porte
70 K chunks, donc sans lui les agents tournent sans contexte Salesforce et
rendent des livrables plausibles mais pauvres — la panne qu'on ne voit pas sans
sonde. Dans les deux cas `/health` rendait 200 pendant que le produit était à
l'arrêt.

**Effet de bord traité, pas absorbé.** `test_lot_g_health_and_boot::
test_health_ok_when_database_reachable` est devenu rouge — légitimement :
l'environnement de test n'a ni Redis ni chunks. Le test porte sur la base ; il
tient désormais les deux autres sondes, sinon il mesurerait l'environnement
d'exécution au lieu du code.

Preuve : 3 failed → 6 passed sur les tests `/health`.

### 4.2 Décodage SSE de `AgentTesterPage` — **confirmé ; « deux lignes » était optimiste**

Le constat annonçait « deux lignes ». Il en a fallu un module, pour une raison
qui est le fond du problème : le découpage en chunks vient de la pile TCP, pas
du serveur. Il faut donc un **tampon d'état entre les appels**, ce qu'aucune
ligne ne fait.

`frontend/src/lib/sseStream.ts` — `SseLineReader` décode en mode flux
(`{ stream: true }`), tient le tampon, gère `\r\n`, les `data:` multi-lignes, et
rend l'événement encore en tampon à la fermeture (un serveur qui ferme juste
après le dernier `data:` a bien envoyé un événement complet — le jeter serait le
même repli silencieux, une ligne plus loin). Un événement complet et illisible
ressort en ligne d'erreur au lieu d'être avalé par le `catch { }`.

Preuve : `frontend/tests/sseStream.test.ts`, 10 tests, dont la coupure au milieu
d'un objet JSON, au milieu du préfixe `data:`, sur le `\n` séparateur, et au
milieu d'un caractère accentué (`é` = deux octets).

### 4.3 `AuditMiddleware` et les flux SSE — **confirmé, deux défauts distincts**

`EventSource` se reconnecte seul : un onglet ouvert produisait une ligne
`audit_logs` par reconnexion, indéfiniment, pour un événement qui n'apprend rien.
Les flux **réussis** ne sont plus audités ; un flux en 401, 403 ou 500 le reste —
on ne tait pas les échecs.

Second volet : `audit_service.log` ouvre une session, INSERT, commit. Fait sur la
boucle d'événements, **toutes** les autres coroutines — flux SSE, WebSocket,
appels LLM en cours — attendaient l'aller-retour PostgreSQL, à un endroit
traversé par 100 % du trafic. C'est le même défaut que les correctifs P0
async/sync, au pire endroit possible. L'écriture part en `asyncio.to_thread`.

Preuve : 2 failed → 3 passed.

### 4.4 Enums de paliers désalignés — **confirmé, et le composant n'a aucun appelant**

Le désalignement est réel : `SubscriptionBadge.tsx` connaissait
`free | premium | enterprise`, le backend sert `free | pro | team | enterprise`.
`team` étant absent de la table d'ordre de `FeatureGate`, la comparaison portait
sur `undefined` : un compte Team se voyait refuser par l'UI une fonctionnalité
que le backend lui accorde. Et les seuils du hook accordaient BUILD et Git dès
le palier 1, donc à un compte Pro, que le backend refuse en 403.

**Mais** (règle 2, vérifier les appelants) :

```
$ grep -rn "SubscriptionBadge\|FeatureGate\|LockedFeature\|useFeatureAccess" frontend/src
frontend/src/components/SubscriptionBadge.tsx: (définitions seules)
```

**Aucun appelant.** La page qui affiche réellement les paliers, `Pricing.tsx`,
utilise déjà `free | pro | team | enterprise`. Le correctif est donc une remise
en cohérence du vocabulaire, **pas un changement de comportement observable** —
et il faut le dire, sinon le rapport laisse croire qu'une fuite d'UX a été
fermée.

Ce qui est fait : `frontend/src/lib/tiers.ts` porte le vocabulaire (`premium`
traité comme alias historique de `pro`, même correspondance que
`credit_service._resolve_credit_tier`), et `parseFeatureAccessError` lit le
payload de `FeatureAccessError` — `error`, `feature`, `required_tier`,
`upgrade_url` — qui est la seule source de vérité sur le palier requis. Les
seuils du hook sont relevés de `TIER_FEATURES`, pas devinés :

| Fonctionnalité | free | pro | team | enterprise | Seuil |
|---|---|---|---|---|---|
| `build_phase` | ✗ | ✗ | ✓ | ✓ | Team |
| `git_integration` | ✗ | ✗ | ✓ | ✓ | Team |
| `custom_templates` | ✗ | ✗ | ✗ | ✓ | Enterprise |

Preuve : `frontend/tests/tiers.test.ts`, 12 tests. `tsc -b --noEmit` et
`vite build` passent.

### 4.5 `migrations/*.sql` manuels — **marqués morts**

Deux sources pour un même schéma, dont une seule tient `alembic_version` :
appliquer un `.sql` d'ici n'avance pas le pointeur de révision, et le prochain
`alembic upgrade head` échoue sur un objet déjà existant. C'est l'incident
qu'annonce PROD-05, et il ne se manifeste qu'au déploiement suivant, loin de sa
cause.

Les fichiers sont **conservés** (trace de l'état du schéma avant Alembic).
`migrations/README.md` les déclare morts et donne la correspondance
fichier → révision Alembic. Marquer mort n'est pas écrire une note que personne
ne lit : `tests/test_vague2_lot3_migrations_mortes.py` échoue si un `.sql` est
ajouté, et un autre test vérifie qu'aucun code Python ne les référence.

### 4.6 Les 6 échecs de `test_sf_admin_service.py` — **`xfail(strict=True)`**

Tests de spécification (`BUILD_V2_SPEC.md` §6.5) sur des attributs jamais
implémentés : `OPERATION_HANDLERS`, `FIELD_TYPE_MAP`, `_tooling_api_create`,
`_tooling_api_delete`. Les faire passer serait écrire la fonctionnalité.

`strict=True` et non `skip`, délibérément : l'écart entre la spécification et le
code reste lisible dans le rapport de pytest, et le jour où quelqu'un
implémente `OPERATION_HANDLERS` le marqueur devient un `XPASS` qui casse la
suite — c'est ce que `strict` achète. Un `skip` aurait effacé l'écart ; un test
rouge en permanence finit par ne plus être lu.

Un `sys.path.insert(0, '/root/workspace/…')` — chemin absolu contraire aux
conventions du dépôt — est retiré au passage.

---

## 5. LOT 4 — les deux défauts du 23/08 *(commit `6a7e3ec`)*

Les deux ont **la même cause racine** : la production tourne en `DEBUG=True`, et
deux dispositifs de sécurité sont conditionnés à `DEBUG=False`. Déclarés dans le
code, annoncés dans les rapports, inopérants sur la machine qui sert les clients.

### 5.1 `create_all` au démarrage — **le critère était déclaré et non tenu**

Le verdict demandé était binaire. **Ce n'est pas autre chose : c'est bien
`create_all`.** Les requêtes `pg_catalog.pg_type` observées au boot sont la
vérification d'existence des enums que fait `create_all(checkfirst=True)`.

Mesure, avec la configuration de production :

```
# base vierge, configuration de production (DEBUG=True, AUTO_CREATE_SCHEMA non posée)
$ DEBUG=True python -c "import app.main" 2>&1 \
    | grep -oE "CREATE TABLE [a-z_]+" | sort -u | wc -l
AVANT : 34      # 34 tables créées à l'import de app.main
APRÈS : 0
```

`main.py` faisait `if settings.DEBUG: Base.metadata.create_all()`. `DEBUG` vaut
`True` par défaut (`config.py:31`), `.env.example` livre `DEBUG=True`, et la
production tourne en `DEBUG=True`. LOT-G annonçait « boot sans `create_all` » ;
il tournait à chaque démarrage.

#### Le test qui portait ce critère prouvait le défaut

C'est le constat le plus important de cette vague. `test_lot_g_health_and_boot::
test_schema_creation_is_debug_only` se terminait par :

```python
assert "if settings.DEBUG:\n    Base.metadata.create_all(bind=engine)" in source
```

« Le code contient bien `if settings.DEBUG: create_all()` » — c'est-à-dire
l'assertion que la ligne fautive est présente. Pendant que sa docstring
annonçait « le boot ne doit plus appeler `create_all` ». Le critère de fin de
LOT-G a été accepté sur cette base, et il était vert.

C'est la leçon centrale de cet audit appliquée à l'audit lui-même : **un test
vert ne vaut que ce que vaut son assertion.** Un correctif sans test ne vaut
rien ; un correctif avec un test qui regarde ailleurs ne vaut pas mieux, et
coûte davantage — il ferme le dossier.

Le test est réécrit, et doublé d'un test qui vérifie le **comportement** de la
décision plutôt que le texte du fichier.

#### Correctif

La décision sort de `main.py` vers `app/schema_bootstrap.py`, testable sans
démarrer un processus, et **ne dépend plus de `DEBUG`** : elle se demande par
`AUTO_CREATE_SCHEMA`, non posée par défaut. Corriger par `DEBUG=False` aurait
été l'autre voie, mais la consigne l'interdit et le service refuserait de
démarrer : le correctif devait tenir **à `DEBUG=True`**. La décision est
journalisée dans les deux sens — désactivée en silence, ce serait un dispositif
de plus dont personne ne sait s'il agit.

Mesure refaite sur une base de test **recréée vide**, pour que d'anciennes
tables ne masquent pas un boot qui les créerait encore.

### 5.2 `DEBUG=True` en production rend inerte le garde-fou de LOT-E — **confirmé**

`config.py:172` :

```python
if self.CREDENTIALS_ENCRYPTION_KEY or self.DEBUG:
    return self
```

La clé n'est exigée qu'à `DEBUG=False`. Elle est absente. Le garde-fou ne
s'oppose donc à rien, et `app/utils/encryption.py` retombe sur une clé
**dérivée de `SECRET_KEY`**.

Ce que cela coûte concrètement : le secret qui signe les JWT chiffre aussi les
credentials Salesforce et Git. Une rotation de `SECRET_KEY` — geste banal, prévu
par la documentation en cas de fuite de jeton — rend d'un seul coup
**illisibles tous les credentials de tous les projets**. Pas une corruption : un
`InvalidToken` à chaque lecture, donc un arrêt net de tout déploiement.

**`DEBUG=False` n'est pas basculé**, conformément à la consigne. Ce qui est
fait : le boot **le dit**. Un `CRITICAL` à chaque démarrage nomme l'état réel,
dit que le garde-fou est inerte, et donne la séquence de sortie. Dire n'est pas
réparer — mais un dispositif déclaré et inopérant qui se tait est exactement ce
que la règle 5 interdit, et c'est ce qui a fait passer trois replis silencieux
pour des correctifs.

Sortie réelle du boot :

```
CRITICAL app.main GARDE-FOU DE CHIFFREMENT INERTE. CREDENTIALS_ENCRYPTION_KEY
est absente et DEBUG=True : config.validate_encryption_key ne l'exige qu'a
DEBUG=False, il ne s'oppose donc a rien. […]
```

La séquence est préparée et documentée, **non exécutée** :
`docs/audit-20260821/BASCULE_DEBUG_FALSE.md`. L'ordre y est impératif —
rotation, puis clé dans `.env`, puis redémarrage, puis `DEBUG=False` — parce que
pris à l'envers il rend les credentials illisibles. Le document couvre la
sauvegarde préalable, la vérification par lecture réelle (`--verify-only` : le
`/health` ne lit aucune credential), le repli à chaque étape, et ce que
`DEBUG=False` change **en plus** du chiffrement.

Un test vérifie que le document existe et que l'ordre des étapes y est le bon :
une procédure dont l'ordre se dégrade à la relecture suivante n'est pas une
protection.

---

## 6. Constats infirmés, ou plus étroits qu'annoncé

Ils valent autant que les confirmés.

| Constat | Verdict |
|---|---|
| « `python-docx` et `chromadb` absents des dépendances de test » | **Partiellement infirmé.** Tous deux dans `requirements.txt`. L'effet — orchestrateur non importable — était réel ; la cause était l'absence d'un fichier de dépendances de test, pas une déclaration manquante. §2.2 |
| « Décodage SSE — deux lignes » | **Confirmé, chiffrage infirmé.** Il faut un tampon d'état entre les appels, donc un module, pas deux lignes. §4.2 |
| « Enums de paliers désalignés côté frontend » | **Confirmé, portée infirmée.** Le désalignement est réel, mais `SubscriptionBadge.tsx` n'a **aucun appelant** : cohérence, pas comportement. La page qui affiche vraiment les paliers utilise déjà les bons noms. §4.4 |
| « Suite au départ : 389 passés, 14 échecs » | **Infirmé à la tête déployée.** 388/15 à `1438431` : le commit qui démonte le routeur `deployment` a rendu rouge `test_deployment_cloisonnement`, mesuré avant lui. |
| `kim:PROD-10`, « deux chemins d'écriture » | **Confirmé et plus large** : la lecture non déchiffrée et le jeton Git en clair n'étaient pas nommés, et ce dernier contournait le correctif de LOT-E bis. §3.3 |

---

## 7. Ce qui reste ouvert

### 7.1 `test_deployment_cloisonnement` est rouge, et le restera

`1438431` démonte le routeur `deployment` ; le test attend `401` sur
`POST /api/deployment/promote` et obtient `404`. Le test est **correct** — c'est
sa cible qui a disparu.

Non traité : le périmètre gèle `deployment.py`. Trois issues, toutes hors
périmètre : marquer le test `xfail` en citant le démontage volontaire, le
réécrire pour attendre `404`, ou le supprimer avec le routeur. **La première est
la bonne** — elle garde la trace que sept routes non cloisonnées existaient et
que leur fermeture est une refonte en attente, non un oubli. Un test rouge en
permanence finit par ne plus être lu, et celui-ci porte une information qui
compte.

### 7.2 Le vocabulaire de `resume_from` est fracturé — bien au-delà de `build_tasks`

Le WARNING ajouté en LOT 1a a mis ceci en évidence. Valeurs **émises** par les
quatre appelants, contre les cinq **reconnues** par `execute_workflow`
(`phase1`, `phase1_pm`, `phase2`, `phase4`, `phase5`) :

| Émetteur | Valeur | Reconnue ? | Effet réel |
|---|---|---|---|
| `retry_routes:67` | `phase_ba`, `phase_architect`, `phase_data`, `phase_trainer`, `phase_qa`, `phase_devops` | non | rejoue à partir de la phase 2 au lieu de la phase visée |
| `execution_routes:180` | `phase2_ba` | non | rejoue à partir de la phase 2 — **c'est l'intention**, juste par accident |
| `validation_gate:161` | `phase5_sds`, `phase6_export`, `deploy` | non | approuver une porte **rejoue tout le SDS depuis la phase 2** |
| `validation_gate:195` | `phase4_experts`, `build` | non | rejeter une porte rejoue depuis la phase 2 au lieu de la phase visée |

Onze valeurs mortes en plus de `build_tasks`. La plus coûteuse :
`after_build_code` approuvé envoie `deploy`, non reconnu, donc **rejoue la
chaîne SDS entière** — le même défaut que celui corrigé en LOT 1a, à un autre
endroit. Hors périmètre : le prompt nomme `build_tasks`, et refermer les onze
autres demande de décider quelle phase chaque porte doit reprendre, ce qui est
une décision produit. Le WARNING les rend visibles en attendant.

### 7.3 `validation_gate_routes.py:211` enfile un job qui échouera

```python
job = await pool.enqueue_job(
    "execute_sds_task", …,
    annotations=submission.annotations,   # <- execute_sds_task ne l'accepte pas
)
```

`execute_sds_task` (`workers/tasks.py:9`) n'a pas de paramètre `annotations`.
L'enfilage réussit — ARQ sérialise les kwargs sans les valider — et le job
échoue en `TypeError` **dans le worker**, donc côté client la porte est rejetée
et rien ne redémarre. Trouvé en vérifiant les appelants pour LOT 1a. Hors
périmètre, non corrigé, et ce n'est pas dans `EXECUTION.md` §5.

### 7.4 Reste de `EXECUTION.md` §5, volontairement non touché

`notification_service.py` (plafond assumé), la bascule cookie `HttpOnly`
(décision d'architecture), `kim:TIER-02` (échelle de crédits côté produit),
`deployment.py` (routeur démonté), les secrets de §5.3 à faire tourner,
`MermaidRenderer.tsx` (examiné puis écarté en vague 1), `/render` en query param
(résidu délibéré, à retirer avec la bascule cookie).

### 7.5 `EXECUTION.md` §6.4 reste à faire

Sur une base créée par l'ancien `create_all`, `alembic_version` est vide et le
premier `alembic upgrade head` échouera : `alembic stamp <rev>` d'abord. La
vague 2 a cessé d'en créer de nouvelles occurrences (§5.1) ; elle n'a pas traité
la base existante. C'est un geste d'exploitation, pas du code.

---

## 8. Ce qui n'a pas été fait, et pourquoi

- **Aucun redémarrage du backend.** Règle 4. Tout est préparé, testé hors ligne
  et commité. La mise en production est une décision de Sam.
- **`DEBUG=False` non basculé.** Consigne explicite. La séquence est écrite,
  vérifiée par un test quant à l'ordre de ses étapes, et non exécutée.
- **Aucune rotation de secret, aucune clé générée.** §5.3 d'`EXECUTION.md` et
  l'étape 1 de `BASCULE_DEBUG_FALSE.md` supposent des gestes sur le VPS.
- **Aucune écriture sur le VPS.**

## 9. Commits

| SHA | Objet |
|---|---|
| `57ee795` | LOT 1 — retry BUILD reprend le BUILD ; dépendances de test ; garde `DATABASE_URL` |
| `9d6d3de` | LOT 2 — cloisonnement dans les services, chemin unique pour les secrets |
| `70a4a34` | LOT 3 — `/health` à trois sondes, flux SSE, audit hors boucle, paliers, migrations mortes, `xfail` |
| `6a7e3ec` | LOT 4 — plus de `create_all` au boot, garde-fou inerte annoncé, séquence de bascule |

### Note sur la branche

Le livrable demandait un commit par lot sur `correctifs/audit-croise-20260821`.
Les cinq commits sont sur **`claude/new-session-ihss3x`**, que la consigne de
session impose comme branche de travail. Elle est issue de `1438431`, la tête de
`origin/correctifs/audit-croise-20260821` et la version déployée.

Aucune divergence : `1438431` est ancêtre direct de `HEAD`, donc l'intégration
est une avance rapide, sans commit de fusion ni conflit possible.

```bash
git merge-base --is-ancestor origin/correctifs/audit-croise-20260821 HEAD   # vrai
git checkout correctifs/audit-croise-20260821
git merge --ff-only claude/new-session-ihss3x
```

Le déploiement demande **un redémarrage** : `git pull` ne recharge pas Python
(`EXECUTION.md` §7.1). Rien n'a été redémarré (règle 4).

---

## 10. Fichiers ajoutés

| Fichier | Rôle |
|---|---|
| `backend/requirements-test.txt` | dépendances de la suite, fait autorité (LOT 1b) |
| `backend/tests/db_guard.py` | garde `DATABASE_URL` (LOT 1c) |
| `backend/app/schema_bootstrap.py` | décisions de boot : schéma, posture de chiffrement (LOT 4) |
| `backend/migrations/README.md` | marque le répertoire mort (LOT 3.5) |
| `frontend/src/lib/sseStream.ts` | décodage SSE avec tampon (LOT 3.2) |
| `frontend/src/lib/tiers.ts` | vocabulaire des paliers, lecture du payload d'erreur (LOT 3.4) |
| `docs/audit-20260821/BASCULE_DEBUG_FALSE.md` | séquence préparée, non exécutée (LOT 4.2) |
| `backend/tests/test_vague2_lot1_build_resume.py` | 6 tests |
| `backend/tests/test_vague2_lot1_garde_database_url.py` | 15 tests |
| `backend/tests/test_vague2_lot2_cloisonnement.py` | 19 tests |
| `backend/tests/test_vague2_lot3_observabilite.py` | 9 tests |
| `backend/tests/test_vague2_lot3_migrations_mortes.py` | 4 tests |
| `backend/tests/test_vague2_lot4_boot.py` | 13 tests |
| `frontend/tests/sseStream.test.ts` | 10 tests (runner Node, zéro dépendance) |
| `frontend/tests/tiers.test.ts` | 12 tests (idem) |

88 tests ajoutés : 66 côté Python, 22 côté TypeScript.
