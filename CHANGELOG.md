# Changelog — Digital Humans Production

All notable changes to this project are documented in this file.
Format: [ID] Description | Commit | Date

---

## [2026-05-01] Session consolidation — Sprint 1+2 marketing + tier-routing complete + merges main

Tag : `v2026.05-may-1-consolidation` (post-merge main)

### Marketing site Sprints pre-launch (Mods 28-30)
- **Mod 28 — Sprint 1** (commit `cf86231`) : footer mailto live, CTAs pricing fonctionnels (Free → /signup, Pro/Team grisés "Bientôt"), 3 nouvelles routes SPA `/cgv` `/legal` `/privacy` avec contenu juridique boilerplate FR+EN (~3000 lignes, 10 sections CGV). Module legal.jsx (UUID `a1b2c3d4-...`, +12KB compressé) injecté dans le bundle preview.
- **Mod 29 — Sprint 2** (commit `3366d29`) : 700+ lignes CSS responsive mobile `<= 720px`, color contrast WCAG AA (`--bone-4: #76716A` → `#9A938A`), tap targets 44×44px, focus visible brass 2px, ARIA `role="tab"` aux seq-dot, SEO meta + OG + Twitter Card. **Lighthouse mobile : a11y 86→100, SEO 91→100, TBT −66%** (16690→5620ms).
- **Mod 30 — favicon SVG inline** (commit `18698e5`) : fix console error 404 `/favicon.ico`, "DH" italic Georgia brass sur ink rounded 4px en data URI, +341 bytes. **Best Practices 100/100**.

### Tier-based LLM routing (3 étapes)
- **Étape 1** (commit `19c53f9`) : Pro 49€ downgrade orchestrators (Sophie/Olivia/Emma en Sonnet, Marcus reste Opus pour quality SDS).
- **Étape 2** (commit `c1e1a17`) : auto-resolution tier via `_resolve_tier_for_execution(execution_id)` avec `lru_cache(512)`, helper `invalidate_tier_cache()` exposé. Branché dans webhook Stripe (`stripe_service._handle_subscription_change` + `_handle_subscription_deleted`). **Tests E2E 6/6 + 4/4**.
- **Étape 3** (commit `73fe8c5`) : Anthropic prompt caching auto-activé pour agents architectes (`marcus`/`architect`/`solution_architect`) sur tier paying. Format system block list avec `cache_control:ephemeral`, fallback string si <4096 chars. `LLMRequest.cache_system: bool`, `LLMResponse.cache_read_input_tokens` + `cache_creation_input_tokens`. **Tests E2E 5/5**. Économie ~$1+/SDS.
- Tag `v2026.05-tier-routing-complete` posé après tests.

### SignupPage refondue (parcours libre du bug du 1er mai)
- Premier essai (commit `8665b58`, **REVERTED**) : SignupPage créée sur feature/tier-based-routing en clonant le pattern LoginPage actuel de cette branche, qui était la version legacy purple/cyan. Le déploiement a écrasé le studio refondu en prod (rsync --delete sur /var/www/app-studio).
- Restauration immédiate depuis backup `/var/www/app-studio.pre-signup-page` (Apr 28 build = studio refondu intact).
- **Recréation propre sur feat/platform-studio** (commit `9dab8cb`) : 355 lignes, layout 2-col cover/form respect du pattern A5.1 Foundation, Cormorant italic H1 "Open your studio", JetBrains Mono eyebrows, palette ink/bone/brass strict, validation client visuelle, i18n FR/EN via LangProvider, workflow register+auto-login. Tests E2E backend OK (user 9 créé, JWT obtenu, cleanup OK).
- LoginPage modifiée : mailto "Request access" remplacé par `Link to="/signup"` ("Open your studio →"), mailto enterprise conservé en plus discret.
- Revert (commit `c363584`) : annulation du commit 8665b58 sur tier-based-routing.

### Bench LLM locaux 30 avril (R&D self-hosted)
- Commit `8f8370e` : 30 fichiers, 18,435 lignes, 3 MB dans `docs/benchmarks/local-llm-bench-2026-04-30/`. Test de modèles open-weights sur VPS Hostinger KVM 8 (8 vCPU AMD EPYC, 32 GB RAM, sans GPU).
- **Conclusion** : sur CPU 8 cœurs, **seuls les modèles MoE sont viables** pour des prompts longs. `gemma4:26b` (3.8B actifs) OK 23min Marcus / 7min Diego. `qwen3.5:27b`, `qwen3.6:27b`, `magistral:24b`, `devstral:24b`, `ministral-3:14b` tous KO timeout 1h (prefill trop long).
- À refaire sur Mac M-series (Metal + mémoire unifiée 5-10× plus rapide) ou VPS GPU (Hetzner GEX44 RTX 4000 SFF 20GB ~180-220€/mo).

### Tech debt — F823 + F402 lint fixes
- Commit `1281e9a` : audit ruff complet sur `app/` + `agents/`. **0 F821 confirmé** (les 22 du 18 avril ont été fixées entre-temps). 2 vrais bugs latents fixés :
  - **F823** dans `execution_routes.py:289` : faux positif sur closure async, fix défensif (pré-init `use_notifications=False` + `# noqa: F823` documenté).
  - **F402** dans `sf_admin_service.py:591` : variable de loop `field` shadowait `dataclasses.field`. Renommage `field` → `field_name` (3 occurrences).
- Reste cosmétique : F541 (56), F841 (21), F401 (4), zéro risque runtime.

### Merges main (consolidation totale)
- **Merge `feat/platform-studio` → `main`** (commit `8bc569c`, tag `v2026.05-platform-studio-merged`) : 99 fichiers, +9272 / −5521 lignes, **0 conflit auto-merge**. La refonte Studio Sprint A5.1 → A5.4 + suite est désormais dans main. Pricing.tsx A5.4 retenu (405 lignes, 4 tiers + FAQ + ZDR), strictement plus riche que la Mod 23 sur main (250 lignes).
- **Rebase `feature/tier-based-routing` sur le nouveau main** : 10 commits → 8 commits propres (drop des 2 commits SignupPage legacy + revert qui s'annulaient mutuellement) via `GIT_SEQUENCE_EDITOR` automatisé. 0 conflit lors du replay.
- **Fix `frontend_pages.yaml`** (commit `48ae96a`) : ajout SignupPage + AppShell post-merge platform-studio (le hook post-commit qui rebuild la doc admin plantait sur `BuildError: Composants présents dans App.tsx mais absents`). Description Pricing mise à jour (legacy "Starter/Pro/Enterprise" → "Free/Pro/Team/Enterprise + FAQ + ZDR").
- **Merge `feature/tier-based-routing` → `main`** (commit `2f72f5c`, tag `v2026.05-may-1-consolidation`) : 45 fichiers, +54072 / −183 lignes (gros volumes = audits Lighthouse JSON + bench LLM outputs + contenu juridique CGV).

### Effet structurel
Le code source du studio refondu est maintenant **DANS main**. Toute future branche feature partira d'un main brand-coherent. Le bug du 1er mai (commit basé sur du code legacy) ne peut plus se reproduire.


## [2026-04-29] Session — Stripe Phase 3 S3.3 + fin Sprint A5 marketing

### Stripe billing backend (Phase 3 S3.3)
- Commit `b8e4f82` : `stripe_service.py` avec checkout sessions, customer portal, webhook handlers (subscription.created/updated/deleted, invoice.payment_succeeded/failed). Routes `/billing/checkout`, `/billing/portal`, `/billing/webhook`. Hook signup pour créer customer Stripe automatiquement.
- Commit `c801873` : timeline doc refonte mise à jour.
- Commit `3ae9425` : fin de session avec Stripe webhook E2E validé.

### Marketing site finalisation pricing
- Commit `d679652` : **Mod 23 — Section prix UI** (3 colonnes Free/Pro/Team + Enterprise band). Section narrative `№ 04 · The pact / Le pacte` ajoutée dans le bundle preview entre OurWork et CTA. CTA renuméroté №04 → №05.
- Commit `12ec705` : timeline doc.

### Pro tier ajustements
- Commit `4bc1875` : bump quota Pro 2k→15k crédits, Opus allowed_tiers étendu à 'pro,team'.
- Commit `0e88784` : doc Pro tier nuance — Marcus en Opus + 2 SDS/mois inclus.


## [2026-04-28] Session — Refactor freemium 4-tier + concierge Sophie public

### Freemium realignment
- Commit `e538605` : refactor 3-tier (free/premium/enterprise) → **4-tier (free/pro/team/enterprise)**. Modifs sur subscription model, llm_routing.yaml, allowed_tiers, quota_credits, etc.
- Commit `32223f6` : merge feature/freemium-realignment dans main.

### Concierge Sophie public
- Commit `6bbc643` : widget chat public Sophie sur le marketing site. Nouveau service `sophie_concierge_service.py` (avec `func.coalesce(...)` pour limite quotidienne). Endpoint `/api/public/concierge/talk` accessible sans auth. Intégré dans le bundle preview.

### Marketing site
- Commit `a41c240` : nouvelles sections (marketing-site + pricing-billing) ajoutées à la doc refonte.
- Commit `d1fb657` : timeline 28-29 avril — Mods 17-22 + pricing finalisé + Stripe.


## [2026-04-27] Session — Refonte Studio Sprint A5 + features connexes

### Sprint A5 Platform Studio (refonte complète frontend)
- Commit `eab203f` : **A5.1 Foundation** — design tokens (`tokens.css` ink/bone/brass + 5 acte accents), AppShell + StudioHeader + StudioFooter + StudioPlaceholderCover, LoginPage refondue (Cormorant italic, AUTONOMOUS STUDIO MMXXV), Dashboard refondu ("Welcome back, Admin." + № 01 STUDIO + № 02 REPERTOIRE + cards productions GD/L/SC).
- Commit `928aed5` : **A5.2 Casting** — ProjectWizard 5-act, NewProject welcome page, BR validation Studio, StudioInput/Select/Tabs/Stepper/Textarea/RadioGroup/Timeline, WizardActHeader.
- Commit `1abb6d8` + `03d554c` : **A5.3 Theatre** — ExecutionMonitoringPage refondue (AgentStage, AgentLivePreview, CurtainOverlay, EnsembleDisplay, ExecutionMetricsStudio, ChatSidebarStudio).
- Commit `4979cd2` : **A5.4 Pages connexes** — Projects, ProjectDetail, AgentTester, Pricing refondus + composants projects/ (ChangeRequestCard, ChangeRequestModal, DeliverableCard, ProjectActivityFeed, ProjectHealthCard) + cleanup legacy (Navbar.tsx, App.jsx, main.jsx, pmService.js supprimés au profit de AppShell, App.tsx, main.tsx, pmService.ts).
- Commit `25598be` : **perf** — route-level React.lazy, bundle initial **1.46 MB → 269 KB (-82%)**.
- Commits `c7d0777`, `8832ce5`, `f10c91a` : avatars regen (1024 sources), fix monitoring revisionCount, wizard Healthcare + Agentforce options.
- Commits `a35f7b6`, `3ff7e6a`, `56a7924`, `db171e9`, `b0ee6dc` : deliverable download redirect SDS HTML, admin link /admin/, JWT cookie auth_request nginx, deploy script, agent photos chat.

### BUILD pipeline fixes
- Commit `de52d0b` : fix state-machine + build unblock BUILD pipeline post-SDS.
- Commit `018f34e` : fix initialize PhasedBuildExecutor before execute_build.

### SDS templating
- Commit `0d05d25` : fix sds-templates replace LogiFleet hardcodes with dynamic context.

### Doc admin
- Commit `30f6ea2` : deploy doc admin to `/var/www/app-docs/` accessible via app.digital-humans.fr/admin/docs/.
- Commits `f42bfef`, `4ecc177`, `10fe2cb`, `0fc1708` : briefs A5 (Round 3 + Foundation + cleanup).

---


## [Unreleased] — Session 3 refonte · Agent A (Backend Bloquants)

Runtime bugs that prevented BUILD from running, plus P0/P7/P11 stabilization.

| ID | Description | Files |
|----|-------------|-------|
| A-1 | Elena `generate_test`: fix `response` used before assignment, replace broken `getattr(self, ...)` cost lookup, add defensive `criteria_text` fallback (non-list input), switch to `agent_type="qa_tester"` routing, default verdict → FAIL on parse anomaly | `agents/roles/salesforce_qa_tester.py` |
| A-2 | `QATesterAgent.run()` now dispatches `"test"` mode (was silently returning None) | `agents/roles/salesforce_qa_tester.py` |
| A-3 | Aisha: new module-level `generate_build()` so `phased_build_executor` can dispatch data-migration BUILD work, plus `run()` handles `"build"` | `agents/roles/salesforce_data_migration.py` |
| A-4 | `phased_build_executor._elena_review` no longer fail-opens on crash: Elena exception → verdict=FAIL with structured issue (was silently PASS) | `app/services/phased_build_executor.py` |
| A-5 | F821 fixes Diego / Zara / Raj: `self._total_cost`/`getattr(self, ...)` in module functions replaced with local `cost_usd`; Zara `model_used = response.get(...)` before call reordered | `salesforce_developer_apex.py`, `salesforce_developer_lwc.py`, `salesforce_admin.py` |
| A-6 | F821 services: `import time` added in `sfdx_service.py`; `ChangeRequest` / `SDSVersion` imported; stale `sf_cfg` reference replaced with global `salesforce_config`. Pre-existing f-string nested-quote SyntaxError fixed (file no longer compiled on 3.11) | `sfdx_service.py`, `pm_orchestrator_service_v2.py` |
| A-7 | P0 execution_routes: `start_execution` + `resume_execution` keep `async` for Redis enqueue but offload sync ORM work via `asyncio.to_thread(...)`; SSE and worker health remain async (allowlisted) | `app/api/routes/orchestrator/execution_routes.py` |
| A-8 | P0 batch: converted 36 event-loop-blocking `async def` routes to `def` across 7 files; `projects.test-sf` and `projects.test-git` keep `async` for `httpx` but DB ops are now `asyncio.to_thread`'d | `change_requests.py`, `projects.py`, `business_requirements.py`, `sds_versions.py`, `wizard.py`, `environments.py`, `analytics.py` |
| A-9 | P7 `BudgetService.record_cost()` now commits by default (opt-out via `commit=False`). Previously the auto-created session in `generate_llm_response` never committed, so `executions.total_cost` stayed at 0 | `app/services/budget_service.py` |
| A-10 | P11 RAG health: new `rag_health_check()` probes ChromaDB at startup and logs `[RAG HEALTH] OK — N chunks` or ERROR on empty/failure; silent RAG query failures promoted from `warning` to `error` | `app/services/rag_service.py`, `app/main.py` |
| A-11 | Hygiene: removed 12 redundant imports / shadowed names in `pm_orchestrator_service_v2.py` (F401/F811) | `app/services/pm_orchestrator_service_v2.py` |

**Breaking for regressions**: Elena QA review now defaults to FAIL (not PASS) when Elena crashes or returns an unparseable verdict. Expected and desired — callers that relied on the silent fail-open must surface FAIL to HITL.

**F821 baseline**: 22 → 0 across `agents/` and `app/services/`.

## [Unreleased] — Session 3 refonte · Agent C (LLM Modernization multi-profile)

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

## [Unreleased] — Session 3 refonte · Agent B (Contracts)

### Context
Six overlapping Python dicts (`AGENT_CONFIG`, `AGENT_COLLECTIONS`,
`CATEGORY_AGENT_MAP`, `agent_artifact_needs`, `AGENT_CHAT_PROFILES`,
`AGENT_COSTS`) consolidated into a single YAML registry. Each agent declaration
now carries every piece of metadata the rest of the backend needs, accessed via
one Python accessor (`app.services.agents_registry`).

### TASKs deployed
| TASK | Description | Finding |
|------|-------------|---------|
| B-1 | `backend/config/agents_registry.yaml` — new, 11 agents with canonical ids + aliases | — |
| B-2 | `app.services.agents_registry` accessor (YAML loader, Pydantic validation, cache) | — |
| B-3 | 6 legacy dicts removed; callers migrated to `agents_registry.get_agent()` / `resolve_agent_id()` | — |
| B-4 | HITL contracts in `app/schemas/hitl_*.py` aligned with the registry | — |
| B-5 | Regression test suite `tests/session3_regression/agent_b/` — guards against drift back into code | — |

### Files touched
- `backend/config/agents_registry.yaml` (new)
- `backend/app/services/agents_registry.py` (new)
- `backend/app/services/pm_orchestrator_service_v2.py` (AGENT_CONFIG removed)
- `backend/app/services/rag_service.py` (AGENT_COLLECTIONS removed)
- `backend/app/services/change_request_service.py` (CATEGORY_AGENT_MAP + AGENT_COSTS removed)
- `backend/app/services/artifact_service.py` (agent_artifact_needs removed)
- `backend/app/api/routes/hitl_routes.py` (AGENT_CHAT_PROFILES removed)

### Behavior changes
- Agent aliases (`pm`, `architect`, `apex_developer`, …) continue to resolve to canonical ids.
- Adding a 12th agent now requires one YAML block + one script + one prompt pack — no service edits.

## [Unreleased] — Session 3 refonte · Agent D (Hygiene & Cleanup)

### Context
Maintenance debt consolidation around the refonte: hardcoded paths made
env-driven, logs unified, secrets rotation playbook shipped, dead fallback
prompts removed, F401 lint baseline at zero, backup files purged from git,
onboarding docs + ADRs for sessions A/B/C choices.

### TASKs deployed
| TASK | Description | Finding |
|------|-------------|---------|
| D-1a | `app/config.py` rewritten with env-driven paths (`DH_PROJECT_ROOT`, `DH_OUTPUT_DIR`, `DH_CHROMA_PATH`, `DH_LLM_CONFIG_PATH`, `DH_LOG_FORMAT`, …). Defaults derive from `__file__`. | P2 |
| D-2  | `logging_config.py` refactored with JSON/plain formatter toggle; new `ExecutionContextMiddleware` injects `execution_id` / `agent_id` / `request_id` into every log line via `contextvars`. Preserves A-10 `rag_health_check` at startup. | P5, N72 |
| D-3a | `docs/operations/secrets-rotation.md` — inventory + procedure for 6 critical secrets (Anthropic, OpenAI, Postgres, JWT, GitHub PAT, Salesforce JWT). | P8 |
| D-3b | `scripts/rotate_anthropic_key.sh` — interactive rotation with live smoke call, auto-rollback on failure, systemd restart + health check. | P8 |
| D-4  | **SDS V3 Mistral PASS 1 pipeline removed in full** — option 1 / max cleanup per Sam decision. Tag `legacy/sds_v3_synthesis_before_removal` applied first; then deleted: `sds_synthesis_service.py` (528 LOC), `sds_docx_generator_v3.py`, `uc_analyzer_service.py`, `sds_v3_routes.py` (8 endpoints). Frontend: `SDSv3Generator.tsx`, `generateSDSv3` / `downloadSDSv3` / `getSDSv3Preview` API helpers, conditional render in `ExecutionMonitoringPage.tsx`. The `UCRequirementSheet` ORM model + table are intentionally left in place — drop in a follow-up migration when orphan data is no longer needed. | Décision Sam |
| D-5a | 78 backup files removed (`frontend-backup-working-20251125_120110/`, `.backup-pre-avatars`). Tag `legacy/backup-files-20260418` applied. | Méta-3 |
| D-5b | `.gitignore` now excludes `archives/CONTEXT_*.md`; 14 tracked CONTEXT files untracked. | Méta-5 |
| D-5c | N19a dead `# FALLBACK: original f-string prompt` blocks removed from Lucas trainer (232 LOC). | N19a |
| D-5d | `docs/architecture.md`, `docs/agents.md`, `docs/deployment.md`, ADR-001, ADR-002 — new onboarding docs. | Méta-2 |
| D-5f | `ruff.toml` at repo root + 162 auto-fixed F401 across 69 files. `ruff check --select F401 …` = all passed. | Méta-4 |

### Files touched
- `backend/app/config.py` (paths refactor)
- `backend/app/logging_config.py` (refactor)
- `backend/app/middleware/execution_context.py` (new)
- `backend/app/middleware/__init__.py` (export)
- `backend/app/main.py` (wire middleware)
- `backend/agents/roles/salesforce_trainer.py` (dead code removed)
- `backend/app/services/agent_executor.py` (F401 noqa for RAG probe)
- `ruff.toml` (new)
- `.gitignore` (archives)
- `docs/architecture.md`, `docs/agents.md`, `docs/deployment.md` (new)
- `docs/ADR-001-llm-strategy.md`, `docs/ADR-002-agents-registry.md` (new)
- `docs/operations/secrets-rotation.md` (new)
- `scripts/rotate_anthropic_key.sh` (new)
- 69 files across `backend/` (F401 trim)

### Behavior changes
- `DH_LOG_FORMAT=plain` switches away from JSON logs for local dev.
- Execution context (`execution_id`, `request_id`, `agent_id`) now appears in every log line when present.
- No more `/root/workspace/...` literals in `backend/app` — the backend boots on any host without patching.

### Tags applied
- `legacy/backup-files-20260418` — snapshot before `git rm` of the 78 backup files.
- `legacy/sds_v3_synthesis_before_removal` — snapshot before D-4 SDS V3 deletion (8 endpoints + 3 services + frontend component).

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
