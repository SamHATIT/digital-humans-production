# Inventaire des données personnelles rattachées à un compte

Lot **B4** — RGPD droits d'accès, d'effacement et de portabilité (art. 15, 17, 20).
Établi le 03/09/2026 par lecture des **34 modèles SQLAlchemy** de
`backend/app/models/` et par `grep` sur les colonnes de rattachement.

Art. 22 (décision automatisée) : **hors périmètre**, décision D11 de Sam du 30/08
(validation humaine à chaque étape, client = personne morale).

## Méthode et preuves

Trois commandes, jouées depuis `/home/user/wt/b4/backend` :

```
grep -n "user_id\|email\|ip_hash\|session_uuid" app/models/*.py
grep -n "__tablename__\|ForeignKey(" app/models/*.py
grep -n "file_path\|filename\|_email\|_name = Column\|username\|phone\|token\|encrypted\|ip_address\|user_agent" app/models/*.py
```

La liste des tables est celle des `__tablename__` déclarés. `wbs_task_type.py` et
`subscription.py` ne déclarent **aucune** table : ce sont des catalogues Python
(`TIER_FEATURES`, types de tâches WBS). Ils ne figurent donc pas dans l'inventaire.

Deux chemins de rattachement existent :

- **direct** — la table porte `user_id` (ou `created_by`, `validated_by`) ;
- **indirect** — la table pend d'un `project_id` ou d'un `execution_id`, qui
  eux-mêmes portent `user_id`. La suppression y est portée par la contrainte
  `ON DELETE CASCADE` déclarée sur la clé étrangère, pas par du code.

## Contrainte mesurée qui commande tout le reste

`credit_transactions.user_id` est `nullable=False` avec
`ForeignKey("users.id", ondelete="CASCADE")`
(`app/models/credit.py:78-82`, lu). Supprimer physiquement la ligne `users`
**détruirait le grand livre des crédits**, qui doit être conservé pour la
comptabilité. Modifier cette clé étrangère exigerait une migration Alembic,
exclue du périmètre du lot.

**Conséquence** : l'effacement au titre de l'art. 17 est réalisé par
**anonymisation en place de la ligne `users`** (pseudonymisation irréversible :
plus aucune donnée identifiante ne subsiste), et par **suppression physique** de
tout le reste. La ligne conservée n'est plus une donnée à caractère personnel au
sens de l'art. 4.1 dès lors que l'identifiant direct a disparu.

Marqueur d'anonymisation retenu : `users.email` réécrit en
`compte-supprime-<id>@anonymised.invalid`. Le TLD `.invalid` est réservé par la
RFC 6761 et ne résout jamais — ce n'est pas une adresse de service (règle 9).

## Tableau — 34 tables

| # | Table | Rattachement au compte | Nature | Sort à la suppression | Vérifié par |
|---|---|---|---|---|---|
| 1 | `users` | `id` (la ligne elle-même) | identité : `email`, `name`, `hashed_password`, `stripe_customer_id` | **anonymiser en place** : `email` → marqueur, `name` → `Compte supprimé`, `hashed_password` → valeur inutilisable, `is_active` → `false`. `stripe_customer_id` **conservé** (pièce comptable, cf. « hors base »). `subscription_*` conservés (facturation). | lecture `app/models/user.py:15-38` |
| 2 | `projects` | `user_id` direct | `client_name`, `client_contact_name`, `client_contact_email`, `client_contact_phone`, `sf_username`, `requirements_file_path` — données de tiers saisies par l'utilisateur | **supprimer** (déclenche la cascade sur 20 tables) | grep + lecture `app/models/project.py:45-138` |
| 3 | `executions` | `user_id` direct **et** `project_id` | `sds_document_path`, `logs`, `state_history` | **supprimer** | lecture `app/models/execution.py:31-85` |
| 4 | `credit_balances` | `user_id` clé primaire | solde courant — état, pas pièce comptable | **supprimer** | lecture `app/models/credit.py:42-58` |
| 5 | `credit_transactions` | `user_id` direct, `execution_id` / `project_id` en `SET NULL` | grand livre des crédits : `credits_consumed`, `model_used`, jetons | **conserver**, rattachée au `users` anonymisé. `project_id` et `execution_id` deviennent `NULL` par la contrainte quand les projets partent. Justification : obligation de conservation des pièces comptables (art. L123-22 code de commerce, 10 ans) ; base légale art. 6.1.c RGPD. Aucune colonne identifiante ne subsiste après anonymisation de `users`. | lecture `app/models/credit.py:75-105` |
| 6 | `chat_logs` | **pas de `user_id`** — `email_collected`, `session_uuid`, `ip_hash` | conversations du site vitrine, e-mail visiteur, IP hachée | **supprimer** toutes les lignes des sessions dont un tour porte `email_collected = email du compte` (la session entière, pas seulement le tour qui porte l'e-mail) | lecture `app/models/chat_log.py:23-56` |
| 7 | `audit_logs` | `actor_id` (texte : id utilisateur **ou** adresse IP, voir ci-dessous), `project_id` / `execution_id` en `SET NULL` | `actor_name`, **`ip_address` en clair**, `user_agent` | **conserver la ligne, anonymiser les champs identifiants** des lignes dont `actor_id` est l'id du compte : `actor_id` → `compte-supprime`, `actor_name` → `NULL`, `ip_address` → `NULL`, `user_agent` → `NULL`. Justification : piste d'audit de sécurité, intérêt légitime art. 6.1.f. | lecture `app/models/audit.py:100-140` |
| 8 | `project_documents` | `project_id` (cascade) | `filename`, **`file_path` — fichier hors base**, `collection_name` | **supprimer** la ligne (cascade) ; le fichier et les chunks Chroma sont purgés avant, cf. « hors base » | lecture `app/models/project_document.py:16-33` |
| 9 | `project_credentials` | `project_id` (cascade) | `encrypted_value` : jetons Salesforce / Git chiffrés | **supprimer** (cascade) | lecture `app/models/project_credential.py:24-42` |
| 10 | `project_environments` | `project_id` (cascade) | `username`, `instance_url`, `org_id`, libellés de secrets | **supprimer** (cascade) | lecture `app/models/project_environment.py:43-76` |
| 11 | `project_git_config` | `project_id` (cascade) | `repo_url`, `repo_name`, libellés de secrets | **supprimer** (cascade) | lecture `app/models/project_git_config.py:40-73` |
| 12 | `project_conversations` | `project_id` (cascade) | `message`, `context_summary` — conversations projet | **supprimer** (cascade) | lecture `app/models/project_conversation.py:11-28` |
| 13 | `outputs` | `project_id` + `execution_id` (cascade) | `file_name`, **`file_path` — fichier hors base** | **supprimer** la ligne (cascade) ; fichier purgé avant | lecture `app/models/output.py:14-27` |
| 14 | `sds_versions` | `project_id` (cascade) | **`file_path`**, `file_name` | **supprimer** (cascade) ; fichier purgé avant | grep + lecture `app/models/sds_version.py:11-20` |
| 15 | `business_requirements` | `project_id` (cascade) ; `validated_by` → `users` en `SET NULL` | `requirement`, `original_text`, `client_notes` | **supprimer** (cascade) ; `validated_by` d'autres comptes déjà couvert par `SET NULL` | lecture `app/models/business_requirement.py:37-71` |
| 16 | `change_requests` | `project_id` (cascade) ; `created_by` → `users` | `description`, `resolution_notes` | **supprimer** (cascade) | lecture `app/models/change_request.py:43-79` |
| 17 | `document_fusion` | `project_id` + `execution_id` (cascade) | contenu fusionné | **supprimer** (cascade) | grep FK `app/models/document_fusion.py:27-38` |
| 18 | `pm_orchestration` | `project_id` (cascade) | état d'orchestration | **supprimer** (cascade) | grep FK `app/models/pm_orchestration.py:27-28` |
| 19 | `llm_interactions` | `execution_id` (cascade) | **`prompt` et `response` en clair** — peuvent contenir tout ce que l'utilisateur a écrit | **supprimer** (cascade) | lecture `app/models/llm_interaction.py:15-45` |
| 20 | `agent_deliverables` | `execution_id` (cascade) | livrables générés | **supprimer** (cascade) | grep FK `app/models/agent_deliverable.py:18` |
| 21 | `agent_iterations` | `execution_id` (cascade) | itérations d'agents | **supprimer** (cascade) | grep FK `app/models/agent_iteration.py:25` |
| 22 | `execution_agents` | `execution_id` (cascade) | état par agent | **supprimer** (cascade) | grep FK `app/models/execution_agent.py:25` |
| 23 | `execution_artifacts` | `execution_id` (cascade) | artefacts | **supprimer** (cascade) | grep FK `app/models/artifact.py:69` |
| 24 | `validation_gates` | `execution_id` (cascade) | décisions de validation | **supprimer** (cascade) | grep FK `app/models/artifact.py:139` |
| 25 | `agent_questions` | `execution_id` (cascade) | questions posées à l'utilisateur | **supprimer** (cascade) | grep FK `app/models/artifact.py:207` |
| 26 | `deliverable_items` | `execution_id` (cascade) | items de livrable | **supprimer** (cascade) | grep FK `app/models/deliverable_item.py:24` |
| 27 | `quality_gates` | `execution_id` (cascade) | scores qualité | **supprimer** (cascade) | grep FK `app/models/quality_gate.py:25` |
| 28 | `training_content` | `execution_id` (cascade) | supports de formation | **supprimer** (cascade) | grep FK `app/models/training_content.py:35` |
| 29 | `uc_requirement_sheets` | `execution_id` (cascade) | fiches UC | **supprimer** (cascade) | grep FK `app/models/uc_requirement_sheet.py:20` |
| 30 | `task_executions` | `execution_id` — **`ForeignKey("executions.id")` sans `ondelete`** | tâches BUILD | **supprimer explicitement avant** les exécutions : sans `ondelete=CASCADE`, la contrainte bloquerait la suppression de l'exécution | lecture `app/models/task_execution.py:31-39` |
| 31 | `sds_templates` | `created_by` → `users`, **sans `ondelete`** | gabarits de SDS, `name`, `description` | **détacher** : `created_by` → `NULL` pour ce compte. Un gabarit personnalisé n'est pas une donnée personnelle une fois détaché ; le supprimer casserait les SDS qui le référencent. Même traitement pour `business_requirements.validated_by` et `change_requests.created_by`, qui peuvent désigner ce compte depuis le projet d'un autre. | lecture `app/models/sds_template.py:35-70` |
| 32 | `agents` | aucun | catalogue des 11 agents | **conserver** — aucune donnée personnelle | lecture `app/models/agent.py:13-20` |
| 33 | `model_pricing` | aucun | tarif par modèle | **conserver** | lecture `app/models/credit.py:112-135` |
| 34 | `tier_config` | aucun | quotas et prix par tier | **conserver** | lecture `app/models/credit.py:141-150` |

### Deux limites du journal d'audit, mesurées à l'implémentation

`AuditMiddleware` écrit une ligne pour chaque requête auditée avec
`actor_type=API` et **`actor_id = adresse IP en clair`**
(`app/middleware/audit_middleware.py:132-133`, lu, et vérifié par un test qui a
échoué sur `assert 'testclient' is None`) :

1. `audit_logs` porte donc l'IP en clair dans **deux** colonnes, `ip_address` et
   `actor_id`, pas une seule. C'est la seule table du dépôt qui garde une IP non
   hachée — `chat_logs` hache la sienne.
2. Ces lignes ne sont rattachées à **aucun compte** : rien ne permet, à partir
   d'un `user_id`, de retrouver les requêtes API qu'il a faites. Une demande
   d'effacement ne peut donc pas les atteindre. La requête d'effacement
   elle-même en produit une, postérieure à l'anonymisation, qui porte l'IP de
   l'appelant.

Corriger cela demanderait de modifier `AuditMiddleware` — hors périmètre du lot
B4. Reste ouvert.

### Colonne à venir — lot B3

Le lot B3 ajoute à `users` : `consent_cgv_at TIMESTAMPTZ`, `consent_version VARCHAR(16)`,
`consent_ip_hash VARCHAR(64)`. **À venir, lot B3** — non présentes au moment de cet
inventaire (`grep -n "consent" app/models/user.py` → aucune ligne).
Sort à la suppression, à appliquer quand elles existeront : `consent_ip_hash` → `NULL`
(donnée identifiante), `consent_cgv_at` et `consent_version` **conservés** — ce sont
la preuve du consentement, dont la conservation est elle-même une obligation
(art. 7.1 RGPD, EDPB) et qui ne réidentifient personne.

## Données hors base rattachées à un compte

### 1. Fichiers sur disque

Cinq colonnes portent un chemin de fichier :
`project_documents.file_path`, `outputs.file_path`, `sds_versions.file_path`,
`executions.sds_document_path`, `projects.requirements_file_path`.

Les racines sont configurables (`app/config.py:49,105-125`, lu) :
`UPLOAD_DIR`, `OUTPUT_DIR` (`DH_OUTPUT_DIR`), `DELIVERABLES_DIR`, `METADATA_DIR`.

**Sort** : supprimer le fichier avant la ligne. Garde-fou implémenté dans
`account_service` : un chemin qui ne se résout pas **sous l'une de ces racines
configurées** n'est pas supprimé, il est signalé dans le compte rendu. Un chemin
absolu hérité d'une autre installation ne doit pas donner un `unlink` aveugle
(règle 10 : un chemin de prod dans une donnée n'est pas un détail).

### 2. ChromaDB — la prémisse « une collection par projet » est fausse

Mesuré par lecture de `app/services/rag_service.py` :

- les collections sont **cinq, fixes et globales** : `technical_collection`,
  `operations_collection`, `business_collection`, `apex_collection`,
  `lwc_collection` (`rag_service.py:47-53`) ;
- l'isolation par projet n'est **pas** une collection nommée par projet, c'est une
  **métadonnée de chunk** : `chunk_meta["project_id"] = str(project_id)` et
  `chunk_meta["document_id"] = str(document_id)`, avec un identifiant de chunk
  `f"proj{project_id}_doc{document_id}_{i}"` (`rag_service.py:418-425`) ;
- la seule fonction de suppression existante est
  `delete_project_document_chunks(collection_name, document_id)`
  (`rag_service.py:442-465`), qui filtre sur `where={"document_id": ...}`.

**Sort** : pour chaque ligne `project_documents` des projets du compte, appeler
`delete_project_document_chunks(doc.collection_name, doc.id)`. Il n'existe pas de
purge par `project_id` ; en écrire une exigerait de modifier `rag_service.py`,
lecture seule pour ce lot. **Limite connue** : un chunk ingéré sans
`document_id` (le code l'autorise, `document_id` est optionnel) ne serait pas
atteint par cette purge. Signalé, non corrigé.

### 3. Stripe

`users.stripe_customer_id` pointe un client chez Stripe qui détient nom,
e-mail et pièces de facturation. La suppression du compte côté Digital·Humans
**n'efface rien chez Stripe**. C'est un sous-traitant au sens de l'art. 28 :
l'effacement doit lui être répercuté, ce que le service ne fait pas aujourd'hui.
Reste ouvert.

### 4. Journaux

`journalctl -u digital-humans-backend` et les journaux applicatifs contiennent
des e-mails et des identifiants d'utilisateurs. Aucune purge n'est implémentée
par ce lot ; la rétention des journaux est un sujet distinct.

## Effet de l'effacement sur un jeton JWT — mesuré

Le JWT est sans état : il n'existe aucune liste de révocation. Ce qui rend un
jeton inopérant, c'est `_authenticate_user` (`app/utils/dependencies.py:17-62`),
qui relit la ligne `users` à chaque appel et refuse un compte inactif.

Mesuré par les tests du lot, pas déduit :

| Appel après effacement | Code | Cause |
|---|---|---|
| `POST /api/auth/login` avec l'e-mail d'origine | **401** | l'e-mail a été réécrit : aucun `users` ne correspond (`auth.py:250-256`) |
| `GET /api/account/export` avec l'ancien jeton | **404** | la dépendance `proprietaire_du_compte` reconnaît un compte anonymisé |
| `GET /api/auth/me` avec l'ancien jeton | **403** | `is_active = False` — révocation de fait sur tout le reste de l'API |

**Ce qui reste ouvert** : un jeton encore valide n'est pas révoqué au sens
strict, il est seulement refusé parce que la ligne `users` le dit inactif. Une
révocation par liste noire de `jti` demanderait de modifier
`app/utils/auth.py`, hors périmètre du lot B4.
