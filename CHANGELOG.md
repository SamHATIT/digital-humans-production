# Changelog — Digital Humans Production

All notable changes to this project are documented in this file.
Format: [ID] Description | Commit | Date

---

## [2026-04-18] Session 3 — Agent C : LLM Modernization multi-profile

### Context
Consolidation de l'architecture LLM autour de 2 tiers logiques (orchestrator /
worker) et 3 deployment profiles (cloud / on-premise / freemium). Source de
vérité unique : `config/llm_routing.yaml`.

### TASKs deployed
| TASK | Description | Findings resolved |
|------|-------------|-------------------|
| C-1  | `llm_routing.yaml` refondu en format multi-profile (3 × 2 tiers)  | N21, N22, N42, N43 |
| C-1b | `LLMRouterService` profile-aware + `is_build_enabled` / `get_active_profile` | N23, N28, N31 |
| C-2  | Fallback chain scoped au profile actif — pas de fallback cloud depuis on-premise/freemium | N33 |
| C-3  | Continuation CRIT-02 (auto-continue sur `stop_reason=max_tokens`) portée dans le Router V3 | — |
| C-5  | `MODEL_PRICING` chargé depuis YAML (double-index par alias + model_id). Prix Opus réels : $15 in / $75 out | — |
| C-0  | Classe `LLMService` V1 (752 LOC) supprimée → `llm_service.py` réécrit en thin wrapper (212 LOC). Callers directs (`sophie_chat_service`, `change_request_service`, `hitl_routes`, `agent_tester`) migrés vers `generate_llm_response` | N45, N86, N41 |
| C-4  | `BuildEnabledMiddleware` bloque les endpoints BUILD en freemium (HTTP 403 `build_disabled`) + `GET /api/config/capabilities` expose profile actif | N35, N41 |

### Files touched
- `backend/config/llm_routing.yaml` (rewritten)
- `backend/app/services/llm_router_service.py` (rewritten — profile-aware + continuation)
- `backend/app/services/llm_service.py` (752 → 212 LOC thin wrapper)
- `backend/app/services/budget_service.py` (pricing from YAML)
- `backend/app/services/sophie_chat_service.py` (migrated away from LLMService())
- `backend/app/services/change_request_service.py` (migrated)
- `backend/app/api/routes/hitl_routes.py` (migrated)
- `backend/app/api/routes/agent_tester.py` (/llm/status uses router)
- `backend/app/api/routes/config.py` (new — /api/config/capabilities)
- `backend/app/middleware/build_enabled.py` (new — BuildEnabledMiddleware)
- `backend/app/middleware/__init__.py`
- `backend/app/main.py` (wire middleware + config route)
- `backend/tests/test_full_flow.py` (test_05 uses router)

### Behavior changes
- `DH_DEPLOYMENT_PROFILE=cloud|on-premise|freemium` switches routing entirely.
- In `freemium`, `POST /api/projects/{id}/start-build` returns HTTP 403 with code `build_disabled`.
- In `on-premise`, LLM errors are not masked by a cloud fallback (confidentiality).
- Continuations are logged via `continuations` field on `LLMResponse`.

---

## [2026-02-11] Session E2E #142 — First Complete Run

### Context
E2E #142 is the first execution to complete all 5 SDS phases (P1→P5).
Preceded by E2E #140 (P0+P1 only) and E2E #141 (crashed P5 on BUG-011/012).

### Fixes Deployed Before Run
| ID | Description | Commit | Impact |
|----|-------------|--------|--------|
| BUG-012 | Async LLM path for Phase 5 | e02f102 | Phase 5 no longer crashes |
| BUG-011 | phase3_complete transition in resume | e02f102 | Resume flow works |
| PROMPT-V4 | Enriched Marcus design/WBS prompts | e7f1451 | Better architecture quality |
| ARCH-001 | Revision feedback loop for Marcus | e7f1451 | Marcus gets revision context |
| BUG-006 | flush→commit DB fix | 86aa448 | DB state consistency |
| BUG-008 | Ghost job guard | 86aa448 | Prevents duplicate workers |
| BUG-010 | Auto-resume checkpoints | 86aa448 | Granular resume support |

### Fixes Applied During Run
| ID | Description | Commit | Status |
|----|-------------|--------|--------|
| ARCH-002 | Pass uc_digest + previous_design to Marcus revision | 84b33e0 | ✅ Deployed |
| ARCH-002b | Truncation limit 12K→40K for previous_design | 84b33e0 | ✅ Deployed |
| BUG-013 | HITL instead of crash when coverage < 70% | 84b33e0 | ✅ Deployed + validated |

### Fixes Identified, Committed Post-Run (not yet active in E2E #142)
| ID | Description | Commit | Status |
|----|-------------|--------|--------|
| BUG-015 | uc_digest extraction: `.get("digest")` → `.get("content")` directly | fe0cb64 | Committed, needs deploy |
| BUG-016 | Section writer max_tokens 16K→16384 | f225baf | Committed, needs deploy |
| BUG-007 | Accumulate LLM cost on execution | 861d24d | Committed, needs deploy |
| BUG-014 | Granular progress updates Phase 5 | 61fb0f2 | Committed, needs deploy |

### Bugs Discovered (Backlog)
| ID | Description | Severity | Status |
|----|-------------|----------|--------|
| BUG-014b | Resume phase3 replays Phase 2 (checkpoint_map not checked) | MEDIUM | Backlog |
| BUG-016b | Gap analysis mode uses 16K max_tokens (not in 32K list) | MEDIUM | Backlog |
| UX-003 | Coverage gaps show only severity, no detail text | MINOR | Backlog |
| UX-004 | Active Agent uses .find() — only shows 1 agent in parallel | MINOR | Backlog |
| COST-001 | Cost counter always $0.00 (tokens_used=0 everywhere) | MINOR | Backlog |
| COST-002 | Budget $50 hardcoded | MINOR | Backlog |
| PROMPT-001 | Emma recommends Einstein Bots (hallucination) | MINOR | Backlog |
| ROUTER-001 | Phase 4 experts mix models (Haiku/Sonnet4/Sonnet4.5) | MINOR | Backlog |

### Results
- **Status**: COMPLETED (sds_complete, 98%)
- **SDS**: 2,884 paragraphs, 0 tables, 0 placeholders
- **Coverage score**: 61.2% (approved via HITL)
- **API cost**: ~$13.59 (Feb 11 total)
- **Duration**: ~2h40 (10:18→12:57 UTC)

---

## [2026-02-10] E2E #141 — Phase 4 Pass, Phase 5 Crash

### Fixes Applied
| ID | Description | Commit |
|----|-------------|--------|
| BUG-009 | TypeError in coverage gap join | bc38da1 |
| BUG-005 | _map_to_legacy_status returns enum | 860993e |

### Results
- Phase 4 experts all completed successfully
- Phase 5 crashed: BUG-011 (phase3_complete missing) + BUG-012 (sync LLM in async)
- Coverage: 62% (same ceiling as E2E #140)
- State documented in docs/e2e-tests/E2E_141_STATE.json

---

## [2026-02-10] E2E #140 — First Post-Refactoring Test

### Context
First execution after Horizons 2+3 merge (10 parallel streams).

### Results
- Phase 0+1 completed successfully
- State documented in docs/e2e-tests/E2E_140_STATE.json

---

## [2026-02-09 → 2026-02-10] Sprint H — Horizons 2+3 Merge

### Major Changes
Merged 10 parallel development streams into main:

| Stream | Description | Commit |
|--------|-------------|--------|
| Sprint 0 | P0 async fix + P1 dead code + P2 path centralization | 0559a76 |
| Sprint 1 | P3 subprocess→import (11/11 agents) | 943a8c2 |
| Sprint 2 | P4 fat controller split + P7 atomic transactions | f0eeafd |
| Sprint 3 | P5 logging + P6 LLM router bridge + P8 secrets | c80e942 |
| I1.1+I1.3 | ARQ workers for async execution | 708d32e |
| I1.2 | State machine (24 states, 45 tests) | 6324165 |
| P1.1+P1.2 | BudgetService + CircuitBreaker | 4c28752 |
| I1.4+I2 | Frontend async state + BUILD ARQ | 7840844 |
| P1.3+P1.4 | Static analysis PMD+ESLint | c099ff5 |
| P2-Full | Configurable validation gates | ccfe3d9 |
| P3 | RAG dynamic isolation | 85aad21 |
| UX1 | Timeline stepper + deliverable viewer | e8372c6 |

---

## [2026-02-08] Sprint I — E2E Preparation

### Changes
- H1+H2+H15+H21: Orchestrator data quality + progress + zombie cleanup
- H13: UCs moved to Annexe A with sub-batching
- H12: Coverage score display + auto-revision loop
- H14+H17: Service cleanup + greenfield template
- H15-FE: Phase 5 progress + HITL polish

---

## [2026-02-07] Pre-E2E Wiring

### Changes
- State Machine integration (25 transitions)
- Budget tracking (11 agents)
- CircuitBreaker activation
- UC_BATCH_SIZE 35→100


## [2026-02-12] E2E #144 Analysis + Plan V2

### Analysis
- E2E #144 revealed 30 bugs: SDS docx empty (wrong key), cost 262% under-reported, safe_content() truncated 93-96%, 13 hardcoded models, WBS parse errors
- Root causes mapped to 9 backend + 6 frontend + 6 mixed issues

### Changes
- fix: SDS key `document` → `raw_markdown` (commit 6cf0798)
- fix: agent_complexity_map + Marcus max_tokens 64K (commit 7b07ca0)
- plan: Consolidated V2 — 3 parallel tracks + 2 sequential sprints + E2E #145

---

## [2026-02-13] Track A+B+C + Sprint 4+5

### Track A — Backend Cleanup (commit baeaed3)
- B2+B3: Fix 4 key mismatches orchestrator→Emma (qa_specs→qa_plan, devops_specs→devops_plan, training_specs→training_plan, data_specs→data_migration_plan) + add gap_analysis
- B4: Increase safe_content() limits (archi 10K→60K, wbs 6K→30K, experts 3K→15K) + Emma max_tokens 16K→32K
- B5: Fix MODEL_PRICING (Opus $15/$75→$5/$25, Haiku $0.25/$1.25→$1/$5) + add claude-opus-4-6
- B6: Remove ALL 13 hardcoded claude-sonnet-4-20250514 from 8 agents → all use YAML agent_type routing
- B8: Anti-markdown-in-JSON rules in Marcus prompts (design, gap, wbs, fix_gaps)

### Track B — Architecture Viewer (commit 767efd1)
- Rewrite ArchitectureReviewPanel: parse Marcus JSON directly (not Markdown headings)
- Generate ERD Mermaid diagrams from data_model.custom_objects + relationships
- Generate flowchart Mermaid from automation_design.flows with expandable accordions
- Connect WBS JSON phases/tasks to GanttChart component
- Security tab: OWD/sharing model summary, MasterDetail vs Lookup counts
- Display gap descriptions (what_is_missing) instead of just [severity]

### Track C — Deliverable Viewer (commit 28121aa)
- New StructuredRenderer: routes JSON to type-specific UI (BRs→table, coverage→grid, gaps→collapsible, QA→table, DevOps→pipeline, Training→table, Data→mapping)
- DeliverableViewer detects JSON vs Markdown vs Mermaid and routes accordingly

### Sprint 4 — Multi-Agent Chat (commit cc74168)
- Backend: extend /executions/{id}/chat with agent_id param, 9 AGENT_CHAT_PROFILES with role-specific system prompts
- Auto-load agent's own deliverables as context
- Per-agent conversation history (agent_id column added to project_conversations)
- New endpoints: GET /agents (available list), GET /chat/history?agent_id=
- Frontend: ChatSidebar with agent picker dropdown, color-coded per agent

### Sprint 5 — Revision Fix (commit 4d89129)
- B9: Revision now uses mode='fix_gaps' instead of mode='design' (incremental, not full regen)
- get_fix_gaps_prompt: format gaps with what_is_missing + fix_instruction
- solution_json limit 15K→50K chars
- Both auto-revision loop AND manual resume paths fixed

### Files Modified (19 total)
- 8 agent files, pm_orchestrator_service_v2.py, budget_service.py, llm_routing.yaml, marcus_architect.yaml
- hitl_routes.py, project_conversation.py (model)
- ArchitectureReviewPanel.tsx (rewrite), StructuredRenderer.tsx (new), DeliverableViewer.tsx, ChatSidebar.tsx (rewrite)


## [2026-02-14] Pre-E2E #145 Bug Fixes

### P3 — Subprocess → Direct Import (commit 7aa5db9)
- Replace `_run_agent` subprocess (`asyncio.create_subprocess_exec`) with direct class import
- Uses `MIGRATED_AGENTS` registry from `agent_executor.py` (all 11 agents)
- `asyncio.to_thread(agent_instance.run, task_data)` for blocking LLM calls
- Eliminates 3-5s overhead per agent call, no more temp file I/O
- Added "pm" alias to MIGRATED_AGENTS for orchestrator compatibility

### COST-001 — Full Cost Tracking (commit 7aa5db9)
- All 10 agents now propagate `cost_usd` from LLM router (Marcus already had it)
- `self._total_cost` accumulated across multiple LLM calls per agent
- Orchestrator `_track_agent_cost` now gets real cost instead of heuristic for all agents

### H4 — Standard Object Names in DOCX (commit 7aa5db9)
- `document_generator.py` now checks `label → api_name → object → name` (was only `object`)
- Marcus outputs `api_name` + `label` per YAML template; generator now matches

### P1-b — Dead Scripts Removed (commit 7aa5db9)
- Deleted 4 unreferenced debug scripts: direct_wbs.py, fix_wbs.py, gen_wbs.py, gen_wbs_direct.py
