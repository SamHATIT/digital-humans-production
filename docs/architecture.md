# Architecture

*Last reviewed: 2026-04-18 (session 3 refonte: Agents A+B+C+D merged).*

## One-paragraph summary

Digital Humans is a FastAPI backend that orchestrates 11 specialised LLM agents to turn a business description into Salesforce metadata. The orchestrator (Sophie) drives a 6-phase SDS pipeline (PM → BA → Architect → Research → Experts → Write-up), then a 5-phase BUILD pipeline produces deployable Apex/LWC/config. A React/Vite frontend calls the backend over REST; a Postgres 16 DB stores executions, deliverables, and audit logs; a ChromaDB RAG (70K chunks) grounds every LLM call.

## High-level diagram

```
                                   ┌──────────────────────┐
                                   │   Frontend (React)   │
                                   │  Vite :3000          │
                                   └──────────┬───────────┘
                                              │ REST + WebSocket
                                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           FastAPI backend :8002                          │
│                                                                          │
│  Middlewares (LIFO):                                                     │
│     BuildEnabledMiddleware (C-4) ── ExecutionContextMiddleware (D-2)     │
│     ── AuditMiddleware (CORE-001) ── CORS ── SlowAPI rate limiter        │
│                                                                          │
│   Routes (prefix /api):                                                  │
│    ├── auth                                                              │
│    ├── pm-orchestrator   → 36 routes — SDS + BUILD orchestration         │
│    │     ├─ orchestrator/sds_v3_routes.py                                │
│    │     └─ orchestrator/_helpers.py                                     │
│    ├── projects, artifacts, analytics                                    │
│    ├── hitl              → contextual chat, CR lifecycle, versions/diff  │
│    ├── audit             → immutable audit log query                     │
│    ├── deployment, quality-dashboard, wizard, subscription               │
│    ├── documents         → P3 RAG isolation                              │
│    ├── config            → /api/config/capabilities (C-4 frontend hint)  │
│    └── leads, blog                                                       │
│                                                                          │
│   Services (40+):                                                        │
│    ├── agents_registry        → YAML-driven, single source of truth (B)  │
│    ├── pm_orchestrator_service_v2  → SDS phases 1-6                      │
│    ├── phased_build_executor  → BUILD 5 phases                           │
│    ├── agent_executor         → dispatch to agent classes (direct import)│
│    ├── llm_router_service     → 2 tiers × 3 profiles (C-0..C-5)          │
│    ├── budget_service         → real Anthropic pricing from YAML (C-3)   │
│    ├── rag_service            → ChromaDB 70K chunks                      │
│    ├── sds_synthesis_service  → Claude SDS synthesis (SDS v3)            │
│    ├── sds_docx_generator_v3  → DOCX export                              │
│    └── audit_service          → append-only action log                   │
└──────────────────────────────────────────────────────────────────────────┘
          │                      │                       │
          ▼                      ▼                       ▼
  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
  │ PostgreSQL   │        │ ChromaDB     │        │ Anthropic /  │
  │ :5432        │        │ (embedded)   │        │ Ollama       │
  │  executions  │        │  70K chunks  │        │  LLM calls   │
  │  deliverables│        │  5 collecs   │        │              │
  │  audit_log   │        └──────────────┘        └──────────────┘
  └──────────────┘
```

## Pipelines

### SDS (Solution Design Specification) — 6 phases

```
 Phase 1   Sophie    extract_br         → atomic Business Requirements  (user validates)
 Phase 2   Olivia×N  1 call per BR      → Use Cases
 Phase 2.5 Emma      analyze            → UC Digest
 Phase 3   Marcus×4  as_is/gap/design/wbs → Solution Design + WBS
 Phase 3.3 Emma      validate           → Coverage Report (<95% → Marcus revises)
 Phase 4   Parallel  Elena, Jordan, Lucas, Aisha → expert specs
 Phase 5   Emma      write_sds          → SDS markdown (P9: sectioned)
 Phase 6   ——        export             → DOCX via sds_docx_generator_v3.py
```

Parallelism flags live in `pm_orchestrator_service_v2.PARALLEL_MODE`.

### BUILD — 5 phases

`phased_build_executor.py` (sandbox 2-user concurrency limit → sequential):

```
 Foundations   Raj           permissions, record types, layouts
 Backend       Diego         Apex classes, triggers, tests
 Frontend      Zara          LWC components
 Quality       Elena, Raj    tests + config review
 Deployment    Jordan, Lucas CI/CD + adoption material
```

## Cross-cutting concerns (session 3 refonte)

| Concern | Owner | Landing place |
|---------|-------|---------------|
| Event-loop unblocking (sync routes) | A (P0)  | `pm_orchestrator.py` — 22 routes converted `async def` → `def` |
| Budget tracking (per execution, every agent) | A (P7) | `budget_service.py` — consumes `llm_routing.yaml` pricing |
| RAG health probe at boot | A (P11) | `main.py` startup event — `[RAG HEALTH]` log line |
| Single agents registry | B | `backend/config/agents_registry.yaml` + `app.services.agents_registry` |
| HITL contracts (CR, chat, versions) | B | `app/api/routes/hitl_routes.py` + `app/schemas/hitl_*.py` |
| LLM Router V3 (2 tiers × 3 profiles) | C | `backend/config/llm_routing.yaml` + `llm_router_service.py` |
| Feature gate — freemium BUILD | C (C-4)| `BuildEnabledMiddleware` + `/api/config/capabilities` |
| Env-driven paths | D (D-1) | `app/config.py` — DH_* env vars, defaults from `__file__` |
| Unified structured logging | D (D-2) | `logging_config.py` + `ExecutionContextMiddleware` |
| Secret rotation playbook | D (D-3) | `docs/operations/secrets-rotation.md` + `scripts/rotate_anthropic_key.sh` |
| Dead code purge (N19a, backups, archives) | D (D-5) | `git rm`, `.gitignore`, `ruff.toml` |

## Key file map

| Area | File | Role |
|------|------|------|
| App entry | `backend/app/main.py` | FastAPI app, middleware stack, startup/shutdown events |
| Config | `backend/app/config.py` | Pydantic settings, env-driven paths (D-1) |
| Logging | `backend/app/logging_config.py` | JSON/plain formatter (D-2) |
| Context | `backend/app/middleware/execution_context.py` | contextvars for `execution_id`/`agent_id`/`request_id` (D-2) |
| Routes | `backend/app/api/routes/pm_orchestrator.py` | Fat controller — 36 routes (P4 split pending) |
| Orchestration | `backend/app/services/pm_orchestrator_service_v2.py` | SDS phase state machine |
| BUILD | `backend/app/services/phased_build_executor.py` | 5-phase BUILD executor |
| Agents | `backend/agents/roles/*.py` | 11 agent scripts (P3 direct-import classes) |
| LLM | `backend/app/services/llm_router_service.py` | 2-tier × 3-profile router (C-0) |
| Registry | `backend/app/services/agents_registry.py` | YAML-driven contract lookup (B) |
| RAG | `backend/app/services/rag_service.py` | ChromaDB integration |
| Audit | `backend/app/api/routes/audit.py` + `app/services/audit_service.py` | Append-only action log |

## Non-goals (intentional scope limits)

- **No full P4 split of the Fat Controller** in session 3 — planned, but extracting 36 routes risks merge conflicts across 4 agent teams. Tagged for session 4.
- **No async SQLAlchemy migration** — current session converts blocking routes to `def` rather than going async.
- **No BaseAgent refactor (P10)** — each agent still implements its own `run()` signature. Contracts normalised via `agents_registry.yaml` header only.
- **No real Vault / AWS Secrets Manager integration** — `docs/operations/secrets-rotation.md` documents manual procedure. Auto-rotation is follow-up.

## Related

- `docs/agents.md` — the 11 agents in detail.
- `docs/deployment.md` — profiles + env vars.
- `docs/ADR-001-llm-strategy.md` — two tiers, three profiles.
- `docs/ADR-002-agents-registry.md` — YAML source of truth.
- `CHANGELOG.md` — session 3 release notes.
