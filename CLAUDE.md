# CLAUDE.md — Digital Humans

## Project

Multi-agent AI platform automating Salesforce development. 11 specialized agents generate specifications (SDS) then deployable code (BUILD).

- **Stack**: FastAPI 0.104.1 (Python 3.12) + React/Vite + PostgreSQL 16 + ChromaDB RAG (70K chunks) + Ollama/Mistral + Ghost CMS
- **VPS**: 72.61.161.222 · Ubuntu 24.04 · Hostinger
- **Repo**: github.com/SamHATIT/digital-humans-production
- **Code**: ~174 Python files (49K lines) + 45 frontend files

## Directory Structure

```
digital-humans-production/
├── backend/
│   ├── agents/roles/           # 11 AI agent scripts (subprocess-launched)
│   ├── app/
│   │   ├── api/routes/         # FastAPI routes (21 files)
│   │   ├── models/             # SQLAlchemy models (29 files)
│   │   ├── services/           # Business logic (40+ files)
│   │   ├── schemas/            # Pydantic schemas (16 files)
│   │   ├── utils/              # Helpers (encryption, etc.)
│   │   ├── config.py           # App configuration (Pydantic Settings)
│   │   ├── database.py         # DB session management
│   │   └── main.py             # FastAPI app entry point
│   ├── tests/                  # 9 test files
│   └── venv/                   # Python virtual environment
├── frontend/src/
│   ├── pages/                  # Dashboard, Execution, Projects
│   ├── components/             # Reusable UI components
│   ├── services/               # API integration
│   └── types/                  # TypeScript types
├── docs/                       # 30+ session reports & specs
├── features.json               # 188 features tracker (dict: metadata, features, stats)
└── PROGRESS.log                # Session journal
```

## Critical Files

| File | Lines | Role |
|------|-------|------|
| `backend/app/api/routes/pm_orchestrator.py` | 2636 | Main route file (Fat Controller — P4). 36 routes, all `async def` |
| `backend/app/services/pm_orchestrator_service_v2.py` | 2477 | Core orchestration: SDS phases 1-6 + BUILD methods |
| `backend/app/services/agent_executor.py` | 726 | Launches agents via `subprocess.run()` (P3) |
| `backend/app/services/phased_build_executor.py` | 736 | BUILD v2 phase execution |
| `backend/app/services/incremental_executor.py` | 1285 | **Dead code** — replaced by PhasedBuildExecutor |
| `backend/app/services/pm_orchestrator_service.py` | 1499 | **Dead code** — V1, replaced by V2 |
| `backend/app/api/routes/pm.py` | 227 | **Dead code** — V1 routes, not used by frontend |
| `backend/app/services/rag_service.py` | — | ChromaDB RAG (CHROMA_PATH = `/opt/digital-humans/rag/chromadb_data`) |
| `backend/app/services/llm_service.py` | — | LLM calls V1 (still used by agents) |
| `backend/app/services/llm_router_service.py` | — | LLM router V3 (ready, underused — P6) |

## The 11 Agents

Source of truth: `AGENT_CONFIG` in `pm_orchestrator_service_v2.py`.

| Agent ID | Name | Role | File | Size | P3 Order |
|----------|------|------|------|------|----------|
| `pm` | Sophie | PM | `salesforce_pm.py` | 16K | 3rd |
| `ba` | Olivia | Business Analyst | `salesforce_business_analyst.py` | 16K | 4th |
| `research_analyst` | Emma | Research Analyst | `salesforce_research_analyst.py` | 46K | **11th — last** |
| `architect` | Marcus | Solution Architect | `salesforce_solution_architect.py` | 40K | 10th |
| `apex` | Diego | Apex Developer | `salesforce_developer_apex.py` | 23K | 8th |
| `lwc` | Zara | LWC Developer | `salesforce_developer_lwc.py` | 20K | 7th |
| `admin` | Raj | Salesforce Admin | `salesforce_admin.py` | 29K | 9th |
| `qa` | Elena | QA Tester | `salesforce_qa_tester.py` | 22K | 6th |
| `devops` | Jordan | DevOps | `salesforce_devops.py` | 10K | 2nd |
| `data` | Aisha | Data Migration | `salesforce_data_migration.py` | 16K | 5th |
| `trainer` | Lucas | Trainer | `salesforce_trainer.py` | 13K | **1st — pilot** |

### SDS Pipeline (from `pm_orchestrator_service_v2.py`)

```
Phase 1:   Sophie (PM)       → extract_br → atomic Business Requirements → user validates
Phase 2:   Olivia (BA)       → called N times (1 per BR) → generates Use Cases
Phase 2.5: Emma (Research)   → analyze mode → generates UC Digest
Phase 3:   Marcus (Architect) → 4 sequential calls: as_is, gap, design, wbs → Solution Design
Phase 3.3: Emma (Research)   → validate mode → coverage check (if <95%, Marcus revises)
Phase 4:   SDS Experts       → parallel: Elena(QA), Jordan(DevOps), Lucas(Trainer), Aisha(Data)
Phase 5:   Emma (Research)   → write_sds → assembles all inputs into final SDS markdown
                                ⚠️ Currently truncates inputs ([:N] slicing) — P9 fixes this
Phase 6:   Export            → DOCX conversion via sds_docx_generator_v3.py
```

Phase 4 experts (`ALL_SDS_EXPERTS = ["data", "trainer", "qa", "devops"]`) run in parallel when `PARALLEL_MODE["sds_experts"] = True`.

### BUILD Pipeline

BUILD agents (Diego/Apex, Zara/LWC, Raj/Admin) are orchestrated by `PhasedBuildExecutor` in 5 phases: Foundations (Raj) → Backend (Diego) → Frontend (Zara) → Quality (Elena, Raj) → Deployment (Jordan, Lucas). BUILD runs sequentially (`PARALLEL_MODE["build_agents"] = False`, sandbox 2-user limit).

## Commands

```bash
# === START ===
cd /root/workspace/digital-humans-production/backend && source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload > /tmp/backend.log 2>&1 &
cd /root/workspace/digital-humans-production/frontend
nohup npm run dev -- --host 0.0.0.0 > /tmp/frontend.log 2>&1 &

# === TEST ===
cd /root/workspace/digital-humans-production/backend && source venv/bin/activate
pytest tests/ -v --tb=short

# === VERIFY ===
curl -s localhost:8002/docs && echo 'Backend OK' || echo 'Backend KO'
curl -s localhost:3000 && echo 'Frontend OK' || echo 'Frontend KO'

# === STOP ===
fuser -k 8002/tcp && pkill -f 'vite'

# === LOGS ===
tail -100 /tmp/backend.log | grep -i error
```

## ⛔ Architectural Problems — MUST READ

### P0 — Event Loop Blocking (CRITICAL · S)
All 36 routes in `pm_orchestrator.py` are `async def` but call synchronous SQLAlchemy ORM (`db.query().all()`). Blocks entire event loop.
**Fix**: `async def` → `def` for ~22 routes doing sync DB access. Keep `async def` for WebSocket, SSE, and async LLM routes only.

### P1 — Split Brain / Dead Code (CRITICAL · S)
V1 (`pm.py` + `pm_orchestrator_service.py` + `incremental_executor.py`) coexists with V2. V1 is dead code. Plus 95 backup files.
**Fix**: Verify with grep, then delete. Archive backups first.

### P2 — 52 Hardcoded Paths (CRITICAL · S)
Absolute paths (`/root/workspace/...`, `/app/...`, `/opt/digital-humans/...`) scattered across 22+ files.
**Fix**: Add `PROJECT_ROOT`, `APP_ROOT`, `DATA_ROOT` to `config.py`. Replace all with `pathlib.Path`.

### P3 — Subprocess Architecture (CRITICAL · XL)
`agent_executor.py` launches agents via `subprocess.run()`. 3-5s overhead per call. 50+ calls in BUILD = 3-4 min wasted.
**Fix**: Transform 11 agents into importable classes with `run(task_data) -> dict`. Migrate simplest first (Trainer → DevOps → PM → ... → Research Analyst).

### P4 — Fat Controller (MAJOR · L)
`pm_orchestrator.py` = 2636 lines mixing HTTP, WS, retry, background tasks.
**Fix**: Extract to `execution_manager.py`, `retry_service.py`, `ws_manager.py`, `sds_service.py`. Target: <600 lines.

### P5–P8
P5: Unified structured logging (M, depends P3). P6: Migrate to LLM Router V3 (M, depends P3). P7: Atomic transactions with `db.begin()` (M). P8: Secret rotation (L, depends P3).

### P9 — SDS Sectioned Generation (MAJOR · M)
Emma `write_sds` (Phase 5) currently receives all inputs in one LLM call with brutal `[:N]` char truncation. Measured losses on 395 deliverables: Coverage Report ~77% lost, Trainer specs ~50%, DevOps specs ~46%.

**Fix**: Replace single mega-call with 11 sequential section calls. Each call generates one SDS section loading full deliverables from `agent_deliverables` table — zero truncation. New service `sds_section_writer.py` + configurable `sds_template.py`. Final consolidation call (#11) produces intro, conclusion, cross-references, and table of contents from section summaries.

Key benefits: granular error recovery (retry single section), full expert specs in SDS, better BUILD task granularity from complete WBS. Estimated cost: ~$0.65/SDS extra.

**Depends on**: P0 (required), P3 + P4 (recommended). **Effort**: 4 days. **Position**: Sprint 2, parallel to P4/P5.
**Files impacted**: `pm_orchestrator_service_v2.py` (Phase 5 replacement), new `sds_section_writer.py`, new `sds_template.py`.

### Dependency Chain
```
P0 → P3 → P5, P6, P8, P9
P1 → P2 → P3
P0 → P4, P7, P9
```

## Anti-Regression Rules — NON-NEGOTIABLE

1. **Never commit to main.** One branch per task (`fix/P0-async-sync`). Merge after full validation.
2. **Tag before/after each sprint.** `pre-sprint-X` / `post-sprint-X`
3. **One change at a time.** Never two refactorings on same branch.
4. **Smoke test after every merge:** backend boots → `curl /api/health` → `curl :3000` → `pytest` same results → logs clean 30s.
5. **Never "done" without proof.** Show output, curl results, log excerpts.
6. **Verify before deleting.** `grep -rn "import.*<module>" backend/ --include="*.py" | grep -v __pycache__ | grep -v backup`
7. **Document changes** in CHANGELOG.md: files touched, reason, tests.

## Git Workflow

```bash
git tag pre-sprint-X
git checkout -b fix/P0-async-sync
# ... atomic commits: fix(P0): convert sync DB routes to def
git checkout main && git merge --no-ff fix/P0-async-sync
git tag post-P0-async-fix
```

## Code Conventions

- English for code/filenames/commits. French for user-facing docs.
- Absolute imports: `from app.services.x import Y` (not relative)
- All paths via `config.py` / `.env` — never hardcoded
- Type hints encouraged. Follow existing patterns.

## Agent Teams — File Ownership

**Never edit the same file from two teammates.** Use task dependencies.

| Teammate | Files Owned | Tasks |
|----------|------------|-------|
| Stabilizer | `pm_orchestrator.py` routes, dead code files, `config.py` | P0, P1, P2 |
| Refactorer | `agents/roles/*.py`, `agent_executor.py` | P3 |
| Modernizer | Extract new services from `pm_orchestrator.py`, transaction fixes | P4, P7 |

## RAG System

- **Production**: `/opt/digital-humans/rag/chromadb_data/` (2.4 GB, 70,251 chunks)
- **Obsolete**: `backend/chroma_db/` (164 KB, empty — ignore)
- **Collections**: technical (29K), operations (17K), business (16K), lwc (6K), apex (1.5K)
- **Embeddings**: OpenAI `text-embedding-3-large` (docs) + Nomic local (code)

## Environment

`backend/.env` contains: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEBUG`, `BACKEND_CORS_ORIGINS`, `AGENTS_DIR`, `UPLOAD_DIR`

## Services

| Service | Port | Auto |
|---------|------|------|
| PostgreSQL | 5432 | ✅ |
| Nginx | 80/443 | ✅ |
| Ghost CMS | 2368 | ✅ (Docker) |
| Backend | 8002 | ❌ manual |
| Frontend | 3000 | ❌ manual |
| Ollama | 11434 | ❌ optional (SDS v3 local) |
| N8N | 5678 | ❌ not used in prod |
