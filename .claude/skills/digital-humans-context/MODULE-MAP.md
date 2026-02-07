# MODULE-MAP — Digital Humans

> Généré: 2026-02-07 | Agent: Architect Phase 1
> Source: Analyse exhaustive de 139 fichiers Python (hors venv/__pycache__/backup)

## Légende statuts

| Statut | Signification |
|--------|--------------|
| ACTIF | En production, pas de problème identifié |
| DEAD_CODE | Non utilisé en production, à supprimer |
| LEGACY | V1 encore référencé quelque part, à migrer |
| À_REFACTORER | Actif mais ciblé par un problème P0-P9 |
| BACKUP | Fichier de sauvegarde, à archiver puis supprimer |

---

## Routes (`backend/app/api/routes/`)

| Fichier | Lignes | Rôle | Imports sortants clés | Importé par | Statut |
|---------|--------|------|----------------------|-------------|--------|
| `pm_orchestrator.py` | 2636 | Routes V2 principales — 36 endpoints (projets, exécutions, SDS, BUILD, WS, SSE) | `pm_orchestrator_service_v2`, `models.*`, `schemas.*`, `dependencies`, `incremental_executor` | `main.py` | À_REFACTORER (P0, P4) |
| `projects.py` | 479 | Détail projet, settings, test Salesforce/Git | `models.*`, `services.environment_service`, `services.connection_validator` | `main.py` | ACTIF |
| `wizard.py` | 450 | Wizard de configuration projet (6 étapes) | `models.*`, `services.connection_validator`, `services.environment_service` | `main.py` | ACTIF |
| `business_requirements.py` | 416 | CRUD Business Requirements + validation + export | `models.business_requirement`, `schemas.business_requirement` | `main.py` | ACTIF |
| `change_requests.py` | 364 | CRUD Change Requests post-SDS | `services.change_request_service`, `models.change_request` | `main.py` | ACTIF |
| `quality_dashboard.py` | 358 | Dashboard qualité (métriques, trends, règles) | `services.quality_gate_service` | `main.py` | ACTIF |
| `deployment.py` | 322 | Package SFDX, snapshots, rollback, release notes | `services.sfdx_service`, `services.git_service`, `services.jordan_deploy_service` | `main.py` | ACTIF |
| `artifacts.py` | 284 | V2 Artifacts system (CRUD, gates, questions, graph) | `services.artifact_service`, `schemas.artifact` | `main.py` | ACTIF |
| `environments.py` | 283 | Environments SFDX, Git config, SDS templates | `services.environment_service`, `models.project_environment` | `main.py` | ACTIF |
| `leads.py` | 245 | Capture de leads + vérification email | `models.user` | `main.py` | ACTIF |
| `pm.py` | 227 | Routes V1 PM (dialogue, PRD, user stories, roadmap) | `pm_orchestrator_service` (V1) | **Non monté dans main.py** | DEAD_CODE |
| `sds_versions.py` | 219 | Versions SDS + download + approbation | `models.sds_version`, `services.sds_docx_generator_v3` | `main.py` | ACTIF |
| `blog.py` | 169 | Génération articles blog + Ghost CMS | `subprocess.run` (lance script externe) | `main.py` | ACTIF |
| `agent_tester.py` | 171 | Test agents individuels + logs | `services.agent_executor`, `subprocess.run` | `main.py` | ACTIF |
| `deliverables.py` | 163 | CRUD deliverables (agents → DB) | `services.deliverable_service`, `models.agent_deliverable` | `main.py` | ACTIF |
| `quality_gates.py` | 153 | CRUD quality gates + iterations + retry check | `services.quality_gate_service` | `main.py` | ACTIF |
| `subscription.py` | 135 | Tiers d'abonnement, upgrade, feature check | `models.subscription` | `main.py` | ACTIF |
| `auth.py` | 114 | Register, login, /me | `utils.auth`, `models.user` | `main.py` | ACTIF |
| `analytics.py` | 114 | Dashboard analytics (stats projets) | `models.*`, `database` | `main.py` | ACTIF |
| `project_chat.py` | 108 | Chat Sophie post-SDS (conversation) | `services.sophie_chat_service` | `main.py` | ACTIF |
| `__init__.py` | 9 | Package init | — | — | ACTIF |

**Note**: `pm.py` n'apparaît PAS dans les `include_router` de `main.py` — confirmé DEAD_CODE.

---

## Services (`backend/app/services/`)

| Fichier | Lignes | Rôle | Imports sortants clés | Importé par | Statut |
|---------|--------|------|----------------------|-------------|--------|
| `pm_orchestrator_service_v2.py` | 2477 | Orchestration SDS (phases 1-6) + BUILD | `agent_executor` (indirect via subprocess), `models.*`, `document_generator` | `pm_orchestrator.py` (routes) | À_REFACTORER (P0, P3, P4, P9) |
| `pm_orchestrator_service.py` | 1499 | Orchestration V1 — remplacée par V2 | `models.*` | `pm.py` uniquement (dead code) | DEAD_CODE |
| `sds_template_generator.py` | 1287 | Génération de templates SDS | `models.*` | Services | ACTIF |
| `incremental_executor.py` | 1285 | BUILD V1 — exécution incrémentale | `agent_executor`, `models.*` | `pm_orchestrator.py:1484`, `run_build.py`, tests | LEGACY |
| `sfdx_service.py` | 948 | Interactions Salesforce DX (deploy, retrieve) | `subprocess.run`, `salesforce_config` | `deployment.py` | ACTIF |
| `environment_service.py` | 786 | Gestion environnements SFDX + Git | `subprocess.run`, `models.project_environment` | `projects.py`, `wizard.py`, `environments.py` | ACTIF |
| `document_generator.py` | 785 | Génération de documents DOCX professionnels | `python-docx` | `pm_orchestrator_service_v2` | ACTIF |
| `git_service.py` | 769 | Opérations Git (clone, commit, push, PR) | `subprocess.run` | `deployment.py` | ACTIF |
| `phased_build_executor.py` | 736 | BUILD V2 — exécution par phases (Data Model → Logic → UI → Auto → Security → Data) | `phase_context_registry`, `phase_aggregator`, `jordan_deploy_service` | `pm_orchestrator.py` | ACTIF |
| `agent_executor.py` | 726 | Lance les agents via `subprocess.run()` | `subprocess.run`, `models.*`, `salesforce_config` | `pm_orchestrator_service_v2`, `agent_tester.py` | À_REFACTORER (P3) |
| `sds_docx_generator_v3.py` | 719 | Génération DOCX SDS V3 | `python-docx` | `sds_versions.py`, `pm_orchestrator.py` | ACTIF |
| `llm_router_service.py` | 718 | LLM Router V3 — routing multi-provider avec coût | `anthropic`, `openai`, `httpx`, `yaml` | Sous-utilisé (P6) | À_REFACTORER (P6) |
| `sf_admin_service.py` | 679 | Service admin Salesforce (metadata CRUD) | `sfdx_service`, `salesforce_config` | Routes deployment | ACTIF |
| `agent_integration.py` | 584 | Intégration agents → système | `agent_executor`, `models.*` | Services | ACTIF |
| `llm_service.py` | 562 | LLM V1 — OpenAI + Anthropic direct | `openai`, `anthropic` | Agents (via sys.path), `rag_service` | ACTIF (utilisé par agents) |
| `jordan_deploy_service.py` | 551 | Service déploiement Jordan (DevOps) | `sfdx_service`, `git_service` | `phased_build_executor` | ACTIF |
| `sds_synthesis_service.py` | 525 | Synthèse SDS (consolidation) | `models.*`, `llm_service` | `pm_orchestrator_service_v2` | ACTIF |
| `audit_service.py` | 475 | Service d'audit (log actions) | `models.audit`, `database` | `middleware`, `pm_orchestrator_service_v2` | ACTIF |
| `artifact_service.py` | 472 | CRUD artifacts V2 | `models.artifact`, `database` | `artifacts.py` | ACTIF |
| `phase_context_registry.py` | 434 | Registre de contexte par phase BUILD | `models.*` | `phased_build_executor` | ACTIF |
| `markdown_to_docx.py` | 424 | Conversion Markdown → DOCX | `python-docx`, `subprocess.run` (pandoc) | `sds_docx_generator_v3` | ACTIF |
| `quality_gates.py` | 385 | Logique quality gates | `models.quality_gate` | Routes | ACTIF |
| `change_request_service.py` | 383 | CRUD Change Requests | `models.change_request` | `change_requests.py` | ACTIF |
| `phase_aggregator.py` | 358 | Agrégation résultats par phase BUILD | `models.*` | `phased_build_executor` | ACTIF |
| `rag_service.py` | 330 | ChromaDB RAG V3 — 5 collections, reranking | `chromadb`, `openai` (embeddings) | Agents (via sys.path), `agent_executor` | ACTIF |
| `uc_analyzer_service.py` | 327 | Analyse Use Cases | `llm_service`, `models.*` | `pm_orchestrator_service_v2` | ACTIF |
| `connection_validator.py` | 322 | Validation connexions Salesforce/Git | `subprocess.run` | `wizard.py`, `projects.py` | ACTIF |
| `sophie_chat_service.py` | 287 | Chat avec Sophie (PM) post-SDS | `llm_service`, `models.project_conversation` | `project_chat.py` | ACTIF |
| `agent_test_logger.py` | 279 | Logger pour tests agents | `models.*` | `agent_executor`, `agent_tester.py` | ACTIF |
| `quality_gate_service.py` | 262 | Service quality gates V2 | `models.quality_gate` | Routes quality | ACTIF |
| `notification_service.py` | 214 | Service notifications temps réel | `asyncio` | `main.py`, `pm_orchestrator_service_v2` | ACTIF |
| `sds_template_service.py` | 170 | Service templates SDS | `models.sds_template` | `environments.py` | ACTIF |
| `llm_logger.py` | 165 | Logger interactions LLM (INFRA-002) | `models.llm_interaction` | Agents, services | ACTIF |
| `deliverable_service.py` | 154 | CRUD deliverables | `models.agent_deliverable` | `deliverables.py` | ACTIF |
| `file_processor.py` | 89 | Traitement fichiers uploadés | — | Services | ACTIF |
| `__init__.py` | 8 | Package init | — | — | ACTIF |

### Sous-module `salesforce/`
| Fichier | Lignes | Rôle | Statut |
|---------|--------|------|--------|
| `metadata_preprocessor.py` | 740 | Préprocesseur metadata Salesforce | ACTIF |
| `metadata_fetcher.py` | 412 | Récupération metadata via SFDX CLI | ACTIF |
| `marcus_as_is_v2.py` | 270 | Analyse as-is pour Marcus (Architect) | ACTIF |
| `__init__.py` | 25 | Package init | ACTIF |

### Fichiers backup (à archiver puis supprimer)
| Fichier | Lignes | Original | Statut |
|---------|--------|----------|--------|
| `agent_executor_backup_20251207_1345.py` | — | agent_executor.py | BACKUP |
| `llm_service_backup_20251207_1346.py` | — | llm_service.py | BACKUP |
| `rag_service_backup_20251206.py` | — | rag_service.py | BACKUP |
| `rag_service_backup_20251207_1344.py` | — | rag_service.py | BACKUP |

---

## Models (`backend/app/models/`)

| Fichier | Lignes | Rôle | Statut |
|---------|--------|------|--------|
| `wbs_task_type.py` | 453 | Types de tâches WBS + config automatable | ACTIF |
| `artifact.py` | 252 | ExecutionArtifact, ValidationGate, AgentQuestion | ACTIF |
| `__init__.py` | 191 | Registre central — importe tous les models | ACTIF |
| `subscription.py` | 185 | SubscriptionTier, TIER_FEATURES, limites | ACTIF |
| `audit.py` | 176 | AuditLog, ActorType, ActionCategory | ACTIF |
| `project.py` | 159 | Project, ProjectStatus, ProjectType | ACTIF |
| `sds_template.py` | 136 | SDSTemplate, DEFAULT_SDS_TEMPLATE | ACTIF |
| `task_execution.py` | 107 | TaskExecution, TaskStatus (BUILD) | ACTIF |
| `project_git_config.py` | 94 | ProjectGitConfig, GitProvider, BranchStrategy | ACTIF |
| `uc_requirement_sheet.py` | 88 | UCRequirementSheet (fiches exigences) | ACTIF |
| `change_request.py` | 86 | ChangeRequest, CRStatus, CRCategory | ACTIF |
| `project_environment.py` | 82 | ProjectEnvironment, EnvironmentType, AuthMethod | ACTIF |
| `business_requirement.py` | 80 | BusinessRequirement, BRStatus, BRPriority | ACTIF |
| `execution.py` | 77 | Execution, ExecutionStatus | ACTIF |
| `deliverable_item.py` | 62 | DeliverableItem | ACTIF |
| `user.py` | 58 | User (SQLAlchemy) | ACTIF |
| `training_content.py` | 57 | TrainingContent, ContentStatus | ACTIF |
| `document_fusion.py` | 50 | DocumentFusion, FusionStatus | ACTIF |
| `pm_orchestration.py` | 49 | PMOrchestration, PMStatus | ACTIF |
| `agent_iteration.py` | 48 | AgentIteration, IterationStatus | ACTIF |
| `quality_gate.py` | 47 | QualityGate, GateStatus | ACTIF |
| `llm_interaction.py` | 46 | LLMInteraction (logging) | ACTIF |
| `project_credential.py` | 41 | ProjectCredential, CredentialType | ACTIF |
| `agent_deliverable.py` | 38 | AgentDeliverable | ACTIF |
| `execution_agent.py` | 34 | ExecutionAgent, AgentExecutionStatus | ACTIF |
| `project_conversation.py` | 31 | ProjectConversation | ACTIF |
| `output.py` | 29 | Output | ACTIF |
| `sds_version.py` | 28 | SDSVersion | ACTIF |
| `agent.py` | 24 | Agent | ACTIF |

---

## Schemas (`backend/app/schemas/`)

| Fichier | Lignes | Rôle | Statut |
|---------|--------|------|--------|
| `wbs_schema.py` | 327 | Schemas WBS (tâches, phases) | ACTIF |
| `artifact.py` | 237 | Schemas V2 artifacts, gates, questions, graph | ACTIF |
| `business_requirement.py` | 110 | Schemas BR (CRUD + validation + export) | ACTIF |
| `execution.py` | 99 | Schemas execution (start, result, progress) | ACTIF |
| `pm_orchestration.py` | 93 | Schemas PM orchestration | ACTIF |
| `change_request.py` | 91 | Schemas Change Requests | ACTIF |
| `project.py` | 88 | Schemas Project (create, update, detail) | ACTIF |
| `quality_gate.py` | 76 | Schemas quality gates | ACTIF |
| `__init__.py` | 69 | Package init — exporte tous les schemas | ACTIF |
| `deliverable.py` | 65 | Schemas deliverables | ACTIF |
| `user.py` | 57 | Schemas User + Token | ACTIF |
| `document_fusion.py` | 51 | Schemas document fusion | ACTIF |
| `sds_version.py` | 46 | Schemas SDS versions | ACTIF |
| `project_conversation.py` | 43 | Schemas conversation Sophie | ACTIF |
| `agent.py` | 41 | Schemas Agent | ACTIF |
| `output.py` | 39 | Schemas Output | ACTIF |

---

## Utils (`backend/app/utils/`)

| Fichier | Lignes | Rôle | Statut |
|---------|--------|------|--------|
| `feature_access.py` | 302 | Contrôle d'accès par tier d'abonnement | ACTIF |
| `json_cleaner.py` | 292 | Nettoyage JSON (repair, extract) | ACTIF |
| `encryption.py` | 155 | Chiffrement/déchiffrement (credentials) | ACTIF |
| `dependencies.py` | 154 | Dépendances FastAPI (get_current_user, get_db) | ACTIF |
| `auth.py` | 86 | JWT encode/decode, password hashing | ACTIF |
| `cost_calculator.py` | 79 | Calcul coûts LLM par agent | ACTIF |
| `__init__.py` | 0 | Package init (vide) | ACTIF |

---

## Config & Core (`backend/app/`)

| Fichier | Lignes | Rôle | Statut |
|---------|--------|------|--------|
| `main.py` | 178 | Point d'entrée FastAPI — monte 16 routers, CORS, middleware, lifecycle | À_REFACTORER (P2: chemin hardcodé L175) |
| `config.py` | 88 | Pydantic Settings — DB, JWT, API, CORS, OpenAI, AGENTS_DIR | À_REFACTORER (P2: AGENTS_DIR hardcodé) |
| `database.py` | 33 | Engine SQLAlchemy + SessionLocal + get_db() | ACTIF |
| `salesforce_config.py` | 60 | Config SFDX (paths workspace) | À_REFACTORER (P2: chemins hardcodés) |
| `rate_limiter.py` | 74 | SlowAPI rate limiting | ACTIF |
| `__init__.py` | 0 | Package init | ACTIF |

### Middleware
| Fichier | Lignes | Rôle | Statut |
|---------|--------|------|--------|
| `middleware/audit_middleware.py` | 163 | Log toutes les requêtes HTTP | ACTIF |
| `middleware/__init__.py` | 4 | Exporte AuditMiddleware | ACTIF |

### API (hors routes)
| Fichier | Lignes | Rôle | Statut |
|---------|--------|------|--------|
| `api/audit.py` | 140 | Routes audit (logs, timeline, history) | ACTIF |
| `api/__init__.py` | 0 | Package init | ACTIF |
| `api/routes/__init__.py` | 9 | Package init | ACTIF |

---

## Agents (`backend/agents/roles/`)

| Fichier | Lignes | Agent ID | Persona | Rôle SDS/BUILD | Statut |
|---------|--------|----------|---------|----------------|--------|
| `salesforce_research_analyst.py` | 1259 | `research_analyst` / `emma` | Emma | SDS: Phases 2.5, 3.3, 5 (analyze, validate, write_sds) | À_REFACTORER (P3, P9) |
| `salesforce_solution_architect.py` | 952 | `architect` / `marcus` | Marcus | SDS: Phase 3 (as_is, gap, design, wbs) | À_REFACTORER (P3) |
| `salesforce_admin.py` | 887 | `admin` / `raj` | Raj | BUILD: Foundations + Quality review | À_REFACTORER (P3) |
| `salesforce_developer_apex.py` | 628 | `apex` / `diego` | Diego | BUILD: Backend (Apex classes/triggers/tests) | À_REFACTORER (P3) |
| `salesforce_qa_tester.py` | 595 | `qa` / `elena` | Elena | SDS: Phase 4 (Test Strategy) + BUILD: Quality | À_REFACTORER (P3) |
| `salesforce_developer_lwc.py` | 525 | `lwc` / `zara` | Zara | BUILD: Frontend (LWC components) | À_REFACTORER (P3) |
| `salesforce_data_migration.py` | 435 | `data` / `aisha` | Aisha | SDS: Phase 4 (Data Migration Strategy) | À_REFACTORER (P3) |
| `salesforce_pm.py` | 429 | `pm` / `sophie` | Sophie | SDS: Phase 1 (extract_br) + consolidate | À_REFACTORER (P3) |
| `salesforce_business_analyst.py` | 414 | `ba` / `olivia` | Olivia | SDS: Phase 2 (Use Cases par BR) | À_REFACTORER (P3) |
| `salesforce_trainer.py` | 389 | `trainer` / `lucas` | Lucas | SDS: Phase 4 (Training Strategy) + BUILD: Deployment | À_REFACTORER (P3) |
| `salesforce_devops.py` | 280 | `devops` / `jordan` | Jordan | SDS: Phase 4 (CI/CD Strategy) + BUILD: Deployment | À_REFACTORER (P3) |
| `__init__.py` | 1 | — | — | Package init | ACTIF |

**Pattern commun agents**: Lancés via `subprocess.run()` par `agent_executor.py`. Reçoivent des args JSON en stdin/fichier temp. Importent `llm_service` et `rag_service` via `sys.path.insert(0, "/app")`. Retournent JSON sur stdout.

---

## Tests (`backend/tests/`)

| Fichier | Lignes | Rôle | Statut |
|---------|--------|------|--------|
| `e2e/test_sds_workflow_e2e.py` | 556 | E2E workflow SDS complet | ACTIF |
| `test_full_flow.py` | 319 | Test flow complet (utilise incremental_executor) | LEGACY |
| `test_flow_steps.py` | 306 | Test étapes du flow | ACTIF |
| `services/test_phase_context_registry.py` | 302 | Tests phase context registry | ACTIF |
| `test_emma_phase3.py` | 296 | Tests Emma phase 3 (hardcoded paths) | À_REFACTORER (P2) |
| `test_wizard_phase5.py` | 264 | Tests wizard phase 5 (hardcoded paths) | À_REFACTORER (P2) |
| `test_wbs_task_types.py` | 227 | Tests WBS task types (hardcoded paths) | À_REFACTORER (P2) |
| `test_emma_write_sds.py` | 206 | Tests Emma write_sds (hardcoded paths) | À_REFACTORER (P2) |
| `services/test_phase_aggregator.py` | 191 | Tests phase aggregator | ACTIF |
| `test_auth.py` | 166 | Tests authentification | ACTIF |
| `services/test_sf_admin_service.py` | 134 | Tests admin service | ACTIF |
| `services/test_diego_corrections.py` | 127 | Tests corrections Diego | ACTIF |
| `services/test_zara_corrections.py` | 125 | Tests corrections Zara | ACTIF |
| `services/test_elena_corrections.py` | 120 | Tests corrections Elena | ACTIF |
| `services/test_raj_prompts.py` | 104 | Tests prompts Raj | ACTIF |
| `services/test_jordan_deploy_service.py` | 101 | Tests deploy service | ACTIF |
| `services/test_git_extensions.py` | 45 | Tests extensions Git | ACTIF |
| `services/test_sfdx_extensions.py` | 35 | Tests extensions SFDX | ACTIF |
| `conftest.py` | 61 | Fixtures pytest | ACTIF |
| `__init__.py` | 0 | Package init | ACTIF |

---

## Standalone Scripts (`backend/`)

| Fichier | Lignes | Rôle | Statut |
|---------|--------|------|--------|
| `direct_wbs.py` | 97 | Lancement WBS direct | ACTIF |
| `fix_wbs.py` | 75 | Correction WBS | ACTIF |
| `gen_wbs_direct.py` | 66 | Génération WBS directe | ACTIF |
| `gen_wbs.py` | 61 | Génération WBS | ACTIF |
| `run_build.py` | 41 | Lancement BUILD (utilise incremental_executor) | LEGACY |

### Alembic Migrations
| Fichier | Lignes | Rôle | Statut |
|---------|--------|------|--------|
| `alembic/env.py` | 96 | Config Alembic | ACTIF |
| `alembic/versions/001_add_pm_orchestrator_tables.py` | 182 | Migration tables PM orchestrator | ACTIF |
| `alembic/versions/002_add_artifacts_system.py` | 110 | Migration système artifacts | ACTIF |
| `alembic/versions/003_add_audit_logs.py` | 103 | Migration audit logs | ACTIF |
| `alembic/versions/004_add_project_config_fields.py` | 74 | Migration config projet | ACTIF |
| `alembic/versions/005_add_environments_git_tables.py` | 126 | Migration environments/git | ACTIF |
| `alembic/versions/ddbbd5fb...py` | 163 | Migration champs PM orchestrator | ACTIF |
| `alembic/versions/b959e262...py` | 26 | Merge migration heads | ACTIF |

---

## Frontend (`frontend/src/`)

| Fichier | Lignes | Rôle |
|---------|--------|------|
| `pages/ProjectWizard.tsx` | 859 | Wizard création projet (6 étapes) |
| `pages/ProjectDetailPage.tsx` | 680 | Vue détaillée projet |
| `pages/BRValidationPage.tsx` | 563 | Validation Business Requirements |
| `components/ProjectSettingsModal.tsx` | 510 | Modal settings projet |
| `pages/BuildMonitoringPage.tsx` | 475 | Monitoring BUILD en temps réel |
| `pages/ExecutionMonitoringPage.tsx` | 418 | Monitoring exécution SDS |
| `pages/AgentTesterPage.tsx` | 338 | Test agents individuels |
| `pages/pm/UserStoriesBoard.jsx` | 274 | Board user stories |
| `services/api.ts` | 262 | Service API principal |
| `pages/pm/RoadmapPlanning.jsx` | 256 | Planning roadmap |
| `pages/Pricing.tsx` | 250 | Page pricing/abonnements |
| `components/BuildPhasesPanel.tsx` | 246 | Panel phases BUILD |
| `pages/ExecutionPage.tsx` | 220 | Page exécution |
| `pages/pm/PMDialogue.jsx` | 219 | Dialogue avec Sophie PM |
| `pages/NewProject.tsx` | 217 | Création nouveau projet |
| `pages/ProjectDefinitionPage.tsx` | 197 | Définition projet |
| `components/AgentThoughtModal.tsx` | 195 | Modal pensées agent |
| `pages/pm/PRDReview.jsx` | 193 | Review PRD |
| `pages/Dashboard.tsx` | 191 | Dashboard principal |
| `components/SDSv3Generator.tsx` | 183 | Générateur SDS V3 |
| `pages/Projects.tsx` | 180 | Liste projets |
| `lib/constants.ts` | 174 | Constantes app |
| `components/WorkflowEditor.tsx` | 163 | Éditeur workflow |
| `hooks/useExecutionProgress.ts` | 147 | Hook SSE progress |
| `components/SubscriptionBadge.tsx` | 147 | Badge abonnement |
| `types/constants.ts` | 133 | Types constantes |
| `App.tsx` | 124 | Root component (routing) |
| `services/pmService.js` | 112 | Service PM |
| `pages/LoginPage.tsx` | 112 | Page login |
| `services/qualityGateService.js` | 94 | Service quality gates |
| `components/Navbar.tsx` | 71 | Barre navigation |
| `services/deliverableService.js` | 64 | Service deliverables |
| `services/projectsService.js` | 52 | Service projets |

---

## Statistiques globales

| Métrique | Valeur |
|----------|--------|
| **Fichiers Python backend** | ~139 (hors venv, __pycache__, backup) |
| **Fichiers frontend** | ~38 (.tsx/.ts/.jsx/.js) |
| **Total lignes Python** | ~38,500 |
| **Total lignes frontend** | ~9,700 |
| **Fichiers DEAD_CODE** | 2 (pm.py: 227L, pm_orchestrator_service.py: 1499L) = **1,726 lignes** |
| **Fichiers LEGACY** | 2 (incremental_executor.py: 1285L, run_build.py: 41L) = **1,326 lignes** |
| **Fichiers BACKUP** | 5 (4 services + 1 Dockerfile) |
| **Fichiers À_REFACTORER** | ~25 (routes P0/P4, agents P3, config P2, services P3/P6/P9) |
| **Fichiers ACTIF** | ~110 |
