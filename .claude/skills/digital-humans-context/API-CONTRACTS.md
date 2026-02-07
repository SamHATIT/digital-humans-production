# API-CONTRACTS — Digital Humans

> Généré: 2026-02-07 | Agent: Architect Phase 1
> Source: Analyse de main.py (montage routers) + 21 fichiers de routes + grep exhaustif des décorateurs

---

## Montage des routers (main.py L62-99)

| # | Préfixe main.py | Préfixe router | Chemin effectif | Fichier | Tags | Statut |
|---|----------------|----------------|-----------------|---------|------|--------|
| 1 | `/api` | `/auth` | `/api/auth` | `auth.py` | Authentication | ACTIF |
| 2 | `/api/pm-orchestrator` | (aucun) | `/api/pm-orchestrator` | `pm_orchestrator.py` | PM Orchestrator | À_REFACTORER |
| 3 | `/api` | `/projects` | `/api/projects` | `projects.py` | projects | ACTIF |
| 4 | (aucun) | `/api/analytics` | `/api/analytics` | `analytics.py` | analytics | ACTIF |
| 5 | (aucun) | `/api/v2` | `/api/v2` | `artifacts.py` | V2 Artifacts | ACTIF |
| 6 | `/api` | `/agent-tester` | `/api/agent-tester` | `agent_tester.py` | Agent Tester | ACTIF |
| 7 | (aucun) | `/api/br` | `/api/br` | `business_requirements.py` | Business Requirements | ACTIF |
| 8 | (aucun) | `/api/projects` | `/api/projects` | `project_chat.py` | project-chat | ACTIF |
| 9 | (aucun) | `/api/projects` | `/api/projects` | `sds_versions.py` | sds-versions | ACTIF |
| 10 | (aucun) | `/api/projects` | `/api/projects` | `change_requests.py` | change-requests | ACTIF |
| 11 | `/api` | `/audit` | `/api/audit` | `audit.py` | audit | ACTIF |
| 12 | `/api` | `/deployment` | `/api/deployment` | `deployment.py` | Deployment | ACTIF |
| 13 | `/api` | `/quality` | `/api/quality` | `quality_dashboard.py` | Quality | ACTIF |
| 14 | `/api` | `/wizard` | `/api/wizard` | `wizard.py` | Wizard | ACTIF |
| 15 | `/api/subscription` | (aucun) | `/api/subscription` | `subscription.py` | subscription | ACTIF |
| 16 | `/api` | `/leads` | `/api/leads` | `leads.py` | leads | ACTIF |
| 17 | `/api` | `/blog` | `/api/blog` | `blog.py` | blog | ACTIF |

### Routers NON montés dans main.py
| Fichier | Préfixe router | Raison |
|---------|----------------|--------|
| `pm.py` | `/pm` | DEAD_CODE (V1 routes) |
| `environments.py` | (aucun) | Non importé — routes orphelines |
| `deliverables.py` | `/deliverables` | Non importé — routes orphelines |
| `quality_gates.py` | `/quality-gates` | Non importé — routes orphelines |

---

## Routes — pm_orchestrator.py (36 routes — À_REFACTORER P0/P4)

Préfixe effectif: `/api/pm-orchestrator`

### Gestion de projets

| # | Méthode | Path | Fonction (ligne) | async def | Async nécessaire | Auth | Service appelé |
|---|---------|------|-------------------|-----------|-----------------|------|---------------|
| 1 | POST | `/projects` | `create_project` (L39) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 2 | GET | `/projects` | `list_projects` (L78) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 3 | GET | `/dashboard/stats` | `get_dashboard_stats` (L103) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 4 | GET | `/projects/{project_id}` | `get_project` (L176) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 5 | PUT | `/projects/{project_id}` | `update_project` (L199) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 6 | DELETE | `/projects/{project_id}` | `delete_project` (L232) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |

### Exécution SDS

| # | Méthode | Path | Fonction (ligne) | async def | Async nécessaire | Auth | Service appelé |
|---|---------|------|-------------------|-----------|-----------------|------|---------------|
| 7 | POST | `/execute` | `start_execution` (L261) | oui | **OUI** (BackgroundTask + async service) | get_current_user | pm_orchestrator_service_v2 |
| 8 | POST | `/execute/{id}/resume` | `resume_execution` (L336) | oui | **OUI** (BackgroundTask) | get_current_user | pm_orchestrator_service_v2 |
| 9 | GET | `/execute/{id}/progress` | `get_execution_progress` (L422) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user_from_token_or_header | direct DB |
| 10 | GET | `/execute/{id}/progress/stream` | `stream_execution_progress` (L521) | oui | **OUI** (SSE generator) | token/header | StreamingResponse |
| 11 | GET | `/execute/{id}/result` | `get_execution_result` (L689) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 12 | GET | `/execute/{id}/download` | `download_sds_document` (L728) | oui | **NON** (sync DB + file) ⚠️ P0 | get_current_user | direct DB + FileResponse |
| 13 | GET | `/executions` | `list_executions` (L765) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 14 | GET | `/agents` | `list_available_agents` (L802) | oui | **NON** (static data) ⚠️ P0 | get_current_user | AGENT_CONFIG dict |

### Monitoring BUILD

| # | Méthode | Path | Fonction (ligne) | async def | Async nécessaire | Auth | Service appelé |
|---|---------|------|-------------------|-----------|-----------------|------|---------------|
| 15 | GET | `/execute/{id}/detailed-progress` | `get_detailed_execution_progress` (L829) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 16 | GET | `/execute/{id}/build-tasks` | `get_build_tasks` (L908) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 17 | GET | `/execute/{id}/build-phases` | `get_build_phases` (L988) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 18 | POST | `/projects/{id}/start-build` | `start_build_phase` (L1070) | oui | **OUI** (BackgroundTask BUILD) | get_current_user | phased_build_executor |

### Chat & WebSocket

| # | Méthode | Path | Fonction (ligne) | async def | Async nécessaire | Auth | Service appelé |
|---|---------|------|-------------------|-----------|-----------------|------|---------------|
| 19 | POST | `/chat/{id}` | `chat_with_pm` (L1116) | oui | **OUI** (async LLM call) | get_current_user | sophie_chat_service |
| 20 | WS | `/ws/{id}` | `websocket_endpoint` (L1173) | oui | **OUI** (WebSocket) | JWT in query | WebSocket |

### Retry & Control

| # | Méthode | Path | Fonction (ligne) | async def | Async nécessaire | Auth | Service appelé |
|---|---------|------|-------------------|-----------|-----------------|------|---------------|
| 21 | POST | `/execute/{id}/retry` | `retry_failed_execution` (L1308) | oui | **OUI** (BackgroundTask) | get_current_user | pm_orchestrator_service_v2 |
| 22 | GET | `/execute/{id}/retry-info` | `get_retry_info` (L1400) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 23 | POST | `/execute/{id}/pause-build` | `pause_build` (L1607) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 24 | POST | `/execute/{id}/resume-build` | `resume_build` (L1632) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |

### SDS V3 Pipeline

| # | Méthode | Path | Fonction (ligne) | async def | Async nécessaire | Auth | Service appelé |
|---|---------|------|-------------------|-----------|-----------------|------|---------------|
| 25 | POST | `/execute/{id}/microanalyze` | `microanalyze_ucs` (L1663) | oui | **OUI** (async LLM) | get_current_user | uc_analyzer_service |
| 26 | GET | `/execute/{id}/requirement-sheets` | `get_requirement_sheets` (L1822) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 27 | POST | `/execute/{id}/synthesize` | `synthesize_sds_v3` (L1886) | oui | **OUI** (async LLM) | get_current_user | sds_synthesis_service |
| 28 | GET | `/execute/{id}/sds-preview` | `preview_sds_v3` (L1993) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 29 | GET | `/execute/{id}/domains-summary` | `get_domains_summary` (L2100) | oui | **NON** (sync DB) ⚠️ P0 | get_current_user | direct DB |
| 30 | POST | `/execute/{id}/generate-docx` | `generate_sds_docx` (L2155) | oui | **OUI** (async doc gen) | get_current_user | sds_docx_generator_v3 |
| 31 | GET | `/execute/{id}/download-sds-v3` | `download_sds_v3` (L2298) | oui | **NON** (file read) ⚠️ P0 | get_current_user | FileResponse |
| 32 | POST | `/execute/{id}/generate-sds-v3` | `generate_sds_v3_full_pipeline` (L2355) | oui | **OUI** (full async pipeline) | get_current_user | multiple services |

---

## Routes — auth.py (3 routes)

Préfixe effectif: `/api/auth`

| # | Méthode | Path | Fonction (ligne) | async | Async nécessaire | Auth |
|---|---------|------|-------------------|-------|-----------------|------|
| 1 | POST | `/register` | `register` (L17) | non | — | Non |
| 2 | POST | `/login` | `login` (L57) | non | — | Non |
| 3 | GET | `/me` | `get_me` (L103) | non | — | get_current_user |

---

## Routes — projects.py (5 routes)

Préfixe effectif: `/api/projects`

| # | Méthode | Path | Fonction (ligne) | async | Async nécessaire | Auth |
|---|---------|------|-------------------|-------|-----------------|------|
| 1 | GET | `/{project_id}` | `get_project_detail` (L60) | non | — | get_current_user |
| 2 | PATCH | `/{project_id}/status` | `update_project_status` (L115) | non | — | get_current_user |
| 3 | GET | `/{project_id}/settings` | `get_project_settings` (L176) | non | — | get_current_user |
| 4 | PUT | `/{project_id}/settings` | `update_project_settings` (L221) | non | — | get_current_user |
| 5 | POST | `/{project_id}/test-salesforce` | `test_salesforce_connection` (L295) | non | — | get_current_user |
| 6 | POST | `/{project_id}/test-git` | `test_git_connection` (L411) | non | — | get_current_user |

---

## Routes — wizard.py (10 routes)

Préfixe effectif: `/api/wizard`

| # | Méthode | Path | Fonction | async | Auth |
|---|---------|------|----------|-------|------|
| 1 | POST | `/create` | `wizard_create_project` (L93) | non | get_current_user |
| 2 | PUT | `/{project_id}/step/1` | `wizard_step1` (L132) | non | get_current_user |
| 3 | PUT | `/{project_id}/step/2` | `wizard_step2` (L161) | non | get_current_user |
| 4 | PUT | `/{project_id}/step/3` | `wizard_step3` (L183) | non | get_current_user |
| 5 | PUT | `/{project_id}/step/4` | `wizard_step4` (L204) | non | get_current_user |
| 6 | PUT | `/{project_id}/step/5` | `wizard_step5` (L237) | non | get_current_user |
| 7 | PUT | `/{project_id}/step/6` | `wizard_step6` (L270) | non | get_current_user |
| 8 | GET | `/{project_id}/progress` | `get_wizard_progress` (L297) | non | get_current_user |
| 9 | POST | `/{project_id}/test/salesforce` | `test_sf_connection` (L308) | non | get_current_user |
| 10 | POST | `/{project_id}/test/git` | `test_git_connection` (L356) | non | get_current_user |

---

## Routes — business_requirements.py (8 routes)

Préfixe effectif: `/api/br`

| # | Méthode | Path | Fonction (ligne) | async | Auth |
|---|---------|------|-------------------|-------|------|
| 1 | GET | `/{project_id}` | `list_business_requirements` (L39) | non | get_current_user |
| 2 | GET | `/item/{br_id}` | `get_business_requirement` (L94) | non | get_current_user |
| 3 | POST | `/{project_id}` | `create_business_requirement` (L117) | non | get_current_user |
| 4 | PUT | `/item/{br_id}` | `update_business_requirement` (L173) | non | get_current_user |
| 5 | DELETE | `/item/{br_id}` | `delete_business_requirement` (L219) | non | get_current_user |
| 6 | POST | `/{project_id}/validate-all` | `validate_all_requirements` (L250) | non | get_current_user |
| 7 | GET | `/{project_id}/export` | `export_requirements` (L299) | non | get_current_user |
| 8 | POST | `/{project_id}/reorder` | `reorder_requirements` (L376) | non | get_current_user |

---

## Routes — artifacts.py (18 routes)

Préfixe effectif: `/api/v2`

| # | Méthode | Path | Fonction | Auth |
|---|---------|------|----------|------|
| 1 | POST | `/artifacts` | `create_artifact` (L24) | Non |
| 2 | GET | `/artifacts` | `list_artifacts` (L35) | Non |
| 3 | GET | `/artifacts/{code}` | `get_artifact` (L55) | Non |
| 4 | PUT | `/artifacts/{code}` | `update_artifact` (L70) | Non |
| 5 | PATCH | `/artifacts/{code}/status` | `update_artifact_status` (L86) | Non |
| 6 | GET | `/artifacts/next-code/{type}` | `get_next_code` (L102) | Non |
| 7 | GET | `/context/{agent_id}` | `get_agent_context` (L116) | Non |
| 8 | POST | `/gates/initialize` | `initialize_gates` (L130) | Non |
| 9 | GET | `/gates` | `list_gates` (L148) | Non |
| 10 | GET | `/gates/{num}` | `get_gate` (L160) | Non |
| 11 | POST | `/gates/{num}/submit` | `submit_gate` (L170) | Non |
| 12 | POST | `/gates/{num}/approve` | `approve_gate` (L181) | Non |
| 13 | POST | `/gates/{num}/reject` | `reject_gate` (L192) | Non |
| 14 | POST | `/questions` | `create_question` (L213) | Non |
| 15 | GET | `/questions` | `list_questions` (L224) | Non |
| 16 | GET | `/questions/{code}` | `get_question` (L244) | Non |
| 17 | POST | `/questions/{code}/answer` | `answer_question` (L254) | Non |
| 18 | GET | `/graph` | `get_dependency_graph` (L280) | Non |

**Note**: Routes V2 artifacts n'ont PAS d'auth — potentiel problème de sécurité.

---

## Routes — deployment.py (10 routes)

Préfixe effectif: `/api/deployment`

| # | Méthode | Path | Fonction (ligne) | Auth |
|---|---------|------|-------------------|------|
| 1 | POST | `/package/generate` | `generate_package` (L48) | Non |
| 2 | GET | `/package/{id}/files` | `get_package_files` (L81) | Non |
| 3 | POST | `/snapshot/create` | `create_snapshot` (L119) | Non |
| 4 | POST | `/rollback` | `rollback` (L140) | Non |
| 5 | GET | `/snapshots` | `list_snapshots` (L161) | Non |
| 6 | POST | `/release-notes/generate` | `generate_release_notes` (L193) | Non |
| 7 | GET | `/release-notes/{id}` | `get_release_notes` (L215) | Non |
| 8 | GET | `/environments` | `list_environments` (L271) | Non |
| 9 | POST | `/promote` | `promote_to_environment` (L293) | Non |
| 10 | POST | `/validate` | `validate_deployment` (L316) | Non |

---

## Routes — Autres routers actifs (résumé)

### analytics.py — `/api/analytics` (1 route)
| GET | `` | `get_analytics` (L27) | get_current_user |

### project_chat.py — `/api/projects` (3 routes)
| POST | `/{id}/chat` | `chat_with_sophie` (L22) | get_current_user |
| GET | `/{id}/chat/history` | `get_chat_history` (L56) | get_current_user |
| DELETE | `/{id}/chat/history` | `delete_chat_history` (L86) | get_current_user |

### sds_versions.py — `/api/projects` (5 routes)
| GET | `/{id}/sds-versions` | `list_sds_versions` (L22) | get_current_user |
| GET | `/{id}/sds-versions/current/download` | `download_current_sds` (L61) | get_current_user |
| GET | `/{id}/sds-versions/{num}` | `get_sds_version` (L100) | get_current_user |
| GET | `/{id}/sds-versions/{num}/download` | `download_sds_version` (L133) | get_current_user |
| POST | `/{id}/approve-sds` | `approve_sds` (L171) | get_current_user |

### change_requests.py — `/api/projects` (8 routes)
| GET | `/{id}/change-requests` | `list_change_requests` (L35) | get_current_user |
| POST | `/{id}/change-requests` | `create_change_request` (L84) | get_current_user |
| GET | `/{id}/change-requests/{cr_id}` | `get_change_request` (L129) | get_current_user |
| PUT | `/{id}/change-requests/{cr_id}` | `update_change_request` (L165) | get_current_user |
| POST | `/{id}/change-requests/{cr_id}/submit` | `submit_change_request` (L203) | get_current_user |
| POST | `/{id}/change-requests/{cr_id}/approve` | `approve_change_request` (L256) | get_current_user |
| POST | `/{id}/change-requests/{cr_id}/reject` | `reject_change_request` (L317) | get_current_user |
| DELETE | `/{id}/change-requests/{cr_id}` | `delete_change_request` (L342) | get_current_user |

### quality_dashboard.py — `/api/quality` (4 routes)
| GET | `/execution/{id}` | `get_quality_report` (L38) | Non |
| GET | `/file` | `get_file_quality` (L112) | Non |
| GET | `/trends/{project_id}` | `get_quality_trends` (L129) | Non |
| GET | `/rules` | `get_quality_rules` (L171) | Non |

### subscription.py — `/api/subscription` (6 routes)
| GET | `/tiers` | `get_subscription_tiers` (L28) | Non |
| GET | `/compare` | `compare_tiers` (L49) | Non |
| GET | `/my-subscription` | `get_my_subscription` (L57) | get_current_user |
| GET | `/check-feature/{name}` | `check_feature` (L79) | get_current_user |
| GET | `/can-create-project` | `can_create_project` (L90) | get_current_user |
| POST | `/upgrade-to/{tier}` | `upgrade_to_tier` (L102) | get_current_user |

### agent_tester.py — `/api/agent-tester` (8 routes)
| GET | `/agents` | `list_agents` (L43) | Non |
| GET | `/agents/{id}` | `get_agent_detail` (L55) | Non |
| GET | `/org/query` | `query_org` (L61) | Non |
| POST | `/test/{id}/stream` | `test_agent_stream` (L71) | Non |
| GET | `/workspace/files` | `get_workspace_files` (L102) | Non |
| GET | `/llm/status` | `get_llm_status` (L111) | Non |
| GET | `/logs` | `get_test_logs` (L122) | Non |
| GET | `/logs/{test_id}` | `get_test_log_detail` (L132) | Non |
| GET | `/logs/{test_id}/step/{num}` | `get_test_step` (L150) | Non |

### leads.py — `/api/leads` (3 routes)
| POST | `` | `capture_lead` (L37) | Non |
| GET | `/verify` | `verify_email` (L74) | Non |
| GET | `/count` | `get_leads_count` (L110) | Non |

### blog.py — `/api/blog` (3 routes)
| POST | `/generate-batch` | `generate_blog_batch` (L117) | Non |
| GET | `/pending-topics` | `get_pending_topics` (L142) | Non |
| GET | `/approved-topics` | `get_approved_topics` (L156) | Non |

### audit.py — `/api/audit` (5 routes)
| GET | `/logs` | `get_audit_logs` (L50) | get_current_user |
| GET | `/executions/{id}/timeline` | `get_execution_timeline` (L101) | get_current_user |
| GET | `/tasks/{id}/history` | `get_task_history` (L116) | get_current_user |
| GET | `/actions` | `list_actions` (L131) | get_current_user |
| GET | `/actor-types` | `list_actor_types` (L137) | get_current_user |

---

## Routes DEAD_CODE — pm.py (9 routes)

Préfixe: `/api/pm` (NON monté dans main.py)

| # | Méthode | Path | Fonction (ligne) | Importé | Statut |
|---|---------|------|-------------------|---------|--------|
| 1 | POST | `/dialogue` | `create_dialogue` (L25) | Non | DEAD_CODE |
| 2 | POST | `/generate-prd` | `generate_prd` (L46) | Non | DEAD_CODE |
| 3 | GET | `/projects/{id}/prd` | `get_prd` (L71) | Non | DEAD_CODE |
| 4 | PUT | `/projects/{id}/prd` | `update_prd` (L89) | Non | DEAD_CODE |
| 5 | POST | `/projects/{id}/generate-user-stories` | `generate_stories` (L119) | Non | DEAD_CODE |
| 6 | POST | `/projects/{id}/generate-roadmap` | `generate_roadmap` (L142) | Non | DEAD_CODE |
| 7 | GET | `/projects/{id}/user-stories` | `get_stories` (L165) | Non | DEAD_CODE |
| 8 | GET | `/projects/{id}/roadmap` | `get_roadmap` (L186) | Non | DEAD_CODE |
| 9 | POST | `/orchestration` | `run_orchestration` (L204) | Non | DEAD_CODE |

---

## Résumé P0 — Routes à convertir async→def

**22 routes** dans `pm_orchestrator.py` qui sont `async def` mais ne font que du sync DB:

| # | Route | Ligne | Raison conversion |
|---|-------|-------|-------------------|
| 1 | POST /projects | L39 | sync DB: db.add(), db.commit() |
| 2 | GET /projects | L78 | sync DB: db.query() |
| 3 | GET /dashboard/stats | L103 | sync DB: db.query().count() |
| 4 | GET /projects/{id} | L176 | sync DB: db.query().filter() |
| 5 | PUT /projects/{id} | L199 | sync DB: db.query(), db.commit() |
| 6 | DELETE /projects/{id} | L232 | sync DB: db.delete(), db.commit() |
| 7 | GET /execute/{id}/progress | L422 | sync DB: db.query() |
| 8 | GET /execute/{id}/result | L689 | sync DB: db.query() |
| 9 | GET /execute/{id}/download | L728 | sync DB + file read |
| 10 | GET /executions | L765 | sync DB: db.query() |
| 11 | GET /agents | L802 | static dict return |
| 12 | GET /execute/{id}/detailed-progress | L829 | sync DB |
| 13 | GET /execute/{id}/build-tasks | L908 | sync DB |
| 14 | GET /execute/{id}/build-phases | L988 | sync DB |
| 15 | GET /execute/{id}/retry-info | L1400 | sync DB |
| 16 | POST /execute/{id}/pause-build | L1607 | sync DB |
| 17 | POST /execute/{id}/resume-build | L1632 | sync DB |
| 18 | GET /execute/{id}/requirement-sheets | L1822 | sync DB |
| 19 | GET /execute/{id}/sds-preview | L1993 | sync DB |
| 20 | GET /execute/{id}/domains-summary | L2100 | sync DB |
| 21 | GET /execute/{id}/download-sds-v3 | L2298 | file read |

## Routes à garder async def

**10 routes** qui nécessitent réellement async:

| # | Route | Ligne | Raison |
|---|-------|-------|--------|
| 1 | POST /execute | L261 | BackgroundTask + async orchestration |
| 2 | POST /execute/{id}/resume | L336 | BackgroundTask |
| 3 | GET /execute/{id}/progress/stream | L521 | SSE StreamingResponse |
| 4 | POST /projects/{id}/start-build | L1070 | BackgroundTask BUILD |
| 5 | POST /chat/{id} | L1116 | async LLM call |
| 6 | WS /ws/{id} | L1173 | WebSocket |
| 7 | POST /execute/{id}/retry | L1308 | BackgroundTask |
| 8 | POST /execute/{id}/microanalyze | L1663 | async LLM |
| 9 | POST /execute/{id}/synthesize | L1886 | async LLM |
| 10 | POST /execute/{id}/generate-docx | L2155 | async doc gen |
| 11 | POST /execute/{id}/generate-sds-v3 | L2355 | full async pipeline |

---

## Statistiques

| Métrique | Valeur |
|----------|--------|
| Total routes montées | ~130 |
| Routes pm_orchestrator | 32 (+ 1 WS) |
| Routes dead code (pm.py) | 9 |
| Routes orphelines (non montées) | ~30 (environments, deliverables, quality_gates) |
| Routes sans auth | ~50 (artifacts, deployment, quality, agent_tester, leads, blog) |
| Routes P0 à convertir | 21-22 |
| Routes à garder async | 10-11 |
