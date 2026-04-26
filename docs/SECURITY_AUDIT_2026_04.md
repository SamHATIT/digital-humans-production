# Security Audit — Secrets inventory (Track A2)

*Owner*: Claude Code · *Date*: 2026-04-26 · *Branch*: `claude/security-secrets-manager-CDrJk`
*Trigger*: post-rotation OpenAI key (Headless 360 audit), broaden scope to full secrets management.

This document is the **codebase audit** that precedes migration to a secrets
manager. It is the source of truth for which secrets exist, where they live,
and which ones already leak. The migration plan and rotation procedure live in
[`SECURITY.md`](./SECURITY.md).

The audit was performed inside the cloned repository (sandbox copy of the
production tree). Filesystem-level checks of the VPS (`/opt/digital-humans/`,
`/etc/systemd/system/`, journald output) **must still be run by Sam on the
VPS** — the commands are listed in §6 below.

---

## 1. Summary

| Item | Result |
|------|--------|
| `.env` files committed in repo | **None** (only `.env.example` templates) |
| Real LLM API keys (Anthropic/OpenAI) committed in repo | **None** (only short prefix placeholders in scripts/docs) |
| Hardcoded DB password (`DH_SecurePass2025!`) | **10 tracked files** — leaked in git history since `1aefe3a` (2026-02-10) |
| `.gitignore` coverage | Mostly OK; missing `secrets.yml`, `credentials.json`, `.doppler/` |
| `load_dotenv` callers | 1 (`backend/app/main.py:6`) |
| Env-var consumers (Python) | 14 modules across `app/` + `agents/` |
| Env-var consumers (compose) | 3 services (backend, db, frontend) |
| Existing rotation tooling | `scripts/rotate_anthropic_key.sh` + `docs/operations/secrets-rotation.md` |

**Verdict** : 1 hardcoded credential leak (DB password) requires action. No LLM
key is present in the codebase. Migration to Doppler is feasible without
rewriting git history; the leaked DB password must be **rotated in Postgres**
and the fallbacks removed from source — once that's done the leak is neutralised
even though it remains in history.

---

## 2. Secrets inventory (by source)

### 2.1 Files in the repo that reference secrets

| Path | Type | Real value present? |
|------|------|---------------------|
| `backend/.env.example` | template | placeholders only (`changeme`, `your-secret-key-must-be...`, `sk-your-openai-api-key-here`) |
| `frontend/.env.example` | template | empty (`VITE_API_URL=`) |
| `docker-compose.yml` | dev compose | uses `${DB_PASSWORD}`, `${SECRET_KEY}`, `${OPENAI_API_KEY}`, `${ANTHROPIC_API_KEY:-}` — **OK** |
| `docker-compose.prod.yml` | prod compose | **`DATABASE_URL: postgresql://digital_humans:DH_SecurePass2025!@127.0.0.1:5432/...`** ⚠️ hardcoded |
| `docker-compose.override.yml` | override | no secrets |
| `backend/config/llm_routing.yaml` | LLM router | references env vars only (`api_key_env: "ANTHROPIC_API_KEY"`) — **OK** |

`.env` files actually deployed on the VPS (`backend/.env`, `/opt/digital-humans/rag/.env`) are not in this sandbox; Sam must enumerate them on the VPS using the commands in §6.

### 2.2 Hardcoded DB password (`DH_SecurePass2025!`)

| File | Line | Context |
|------|------|---------|
| `backend/app/services/document_generator.py` | 40 | `os.getenv("DATABASE_URL", "postgresql://...DH_SecurePass2025!@127.0.0.1:5432/...")` |
| `backend/app/services/sds_template_generator.py` | 24 | identical fallback |
| `backend/app/api/routes/blog.py` | 16 | `os.getenv("DATABASE_URL", "postgresql://...DH_SecurePass2025!@localhost:5432/...")` |
| `backend/tests/test_wbs_task_types.py` | 179 | `password="DH_SecurePass2025!"` (test fixture) |
| `backend/tests/test_wizard_phase5.py` | 182 | `password="DH_SecurePass2025!"` (test fixture) |
| `backend/tests/e2e/test_sds_workflow_e2e.py` | 434 | `password="DH_SecurePass2025!"` (e2e test fixture) |
| `docker-compose.prod.yml` | 13 | inline `DATABASE_URL` |
| `SESSION_25NOV2025_SUMMARY.md` | — | session report mentions password |
| `docs/IMPACT_ANALYSIS_BR_VALIDATION_COMPLETE.md` | — | doc mentions password |
| `docs/RAPPORT_SESSION_01DEC2025.md` | — | doc mentions password |

**First commit introducing the value** : `1aefe3a` (2026-02-10, "docs: Emma coverage analysis…").
**Status** : password is therefore visible in git history and presumed compromised.
**Fix path** (recommended order):

1. Sam rotates the Postgres role: `ALTER USER digital_humans WITH PASSWORD 'NEW_VALUE';`
2. Store new value in Doppler under `POSTGRES_PASSWORD` and `DATABASE_URL`.
3. Replace the three `os.getenv("DATABASE_URL", "postgresql://…")` fallbacks with a hard error (`raise RuntimeError("DATABASE_URL not set")`). Tests use a separate `TEST_DATABASE_URL` fixture or the real one via Doppler.
4. Replace `docker-compose.prod.yml` line 13 with `DATABASE_URL: ${DATABASE_URL}` (already the pattern in `docker-compose.yml`).
5. Leave the historical session reports as-is (rewriting history is out of scope per brief §6).

Steps 3 and 4 are **out of scope for this branch** (the brief restricts file modifications to `.gitignore` + this audit + `SECURITY.md`); they are tracked here so Sam can schedule them.

### 2.3 LLM API keys

| Pattern searched | Files matching | Real key present? |
|------------------|----------------|-------------------|
| `sk-ant-api03-[A-Za-z0-9_-]{50,}` | 0 | **No** |
| `sk-proj-[A-Za-z0-9]{30,}` | 0 | **No** |
| `sk-ant-` (short) | 6 (3 docs, 3 lines in `rotate_anthropic_key.sh`) | placeholders only |
| `sk-proj-NEWVALUE` | 1 (`docs/operations/secrets-rotation.md:79`) | placeholder |
| `ghp_xxxxx` / `ghp_••••` | 2 (frontend UI placeholders) | not a real token |

**Verdict** : no Anthropic, OpenAI, or GitHub token committed.

### 2.4 Other potential secret env vars

Not currently referenced in source (searches returned 0 hits):
`JWT_SECRET`, `REDIS_PASSWORD`, `SENDGRID_API_KEY`, `RESEND_API_KEY`,
`MISTRAL_API_KEY`, `STRIPE_*`, `GITHUB_TOKEN` (referenced by name in
`docs/operations/secrets-rotation.md` §7 but the codepath
`jordan_deploy_service` is not in the current tree). Sam should confirm
these are also absent from the deployed `backend/.env`.

---

## 3. Env-loading patterns in source

### 3.1 `load_dotenv()`

Single call: `backend/app/main.py:6` → loads from CWD `.env`.
After Doppler bascule (Option A — systemd wrapper), `.env` becomes empty
on the VPS and `load_dotenv()` becomes a no-op. **No code change required.**

### 3.2 `os.environ.get` / `os.getenv` consumers

Catalogued from `grep -rn "os.environ\|os.getenv" backend/ --include="*.py"`:

| Module | Reads | Notes |
|--------|-------|-------|
| `app/main.py` | (via `load_dotenv`) | — |
| `app/config.py` | `DH_LOG_FORMAT`, `DH_LOG_LEVEL`, `DH_PROJECT_ROOT`, `DH_BACKEND_ROOT`, `DH_OUTPUT_DIR`, `DH_METADATA_DIR`, `DH_CHROMA_PATH`, `DH_RAG_ENV_PATH`, `DH_LLM_CONFIG_PATH`, `DH_SFDX_PROJECT_PATH`, `DH_FORCE_APP_PATH`, `DH_AGENTS_DIR` | infra paths, **not secrets** |
| `app/logging_config.py` | `DH_LOG_FORMAT`, `DH_LOG_LEVEL` | not secrets |
| `app/services/llm_router_service.py` | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (configurable env name) | **secrets** |
| `app/services/rag_service.py` | `OPENAI_API_KEY` | **secret** |
| `app/services/llm_service.py` | `AGENT_TEST_LOG_FILE` | not secret |
| `app/services/document_generator.py` | `DATABASE_URL` | **secret** (with hardcoded fallback ⚠️) |
| `app/services/sds_template_generator.py` | `DATABASE_URL` | **secret** (with hardcoded fallback ⚠️) |
| `app/api/routes/blog.py` | `DATABASE_URL` | **secret** (with hardcoded fallback ⚠️) |
| `app/services/agent_integration.py` | passes `OPENAI_API_KEY` to subprocess env | **secret** (forwarder) |
| `app/services/agent_executor.py` | passes `os.environ` to agents | forwarder |
| `app/services/environment_service.py`, `connection_validator.py` | passes `os.environ` to git subprocess (`GIT_TERMINAL_PROMPT=0`) | not secret access |
| `app/utils/encryption.py` | `CREDENTIALS_ENCRYPTION_KEY` (preferred), fallback to `SECRET_KEY` | **secret** (Fernet key) |
| `agents/roles/salesforce_solution_architect.py`, `salesforce_research_analyst.py` | `ANTHROPIC_API_KEY`, `ANTHROPIC_FALLBACK_MODEL` | **secret** (LLM key) |

### 3.3 Pydantic Settings (`backend/app/config.py`)

Reads env via `pydantic_settings.BaseSettings` with `env_file = ".env"`:
- `DATABASE_URL` (default `postgresql://user:password@…` — placeholder, harmless)
- `SECRET_KEY` (auto-generated in DEBUG, hard-required in prod)
- `OPENAI_API_KEY` (default `""`)

After Doppler bascule, env vars are injected by `doppler run` and Pydantic
picks them up the same way it picks them up from `.env`. **No code change required.**

### 3.4 Salesforce credentials

Stored encrypted in Postgres (`project_credentials` table) using Fernet via
`backend/app/utils/encryption.py`. The Fernet key itself is the secret:

- Primary source: `CREDENTIALS_ENCRYPTION_KEY` env var.
- Fallback: derives Fernet key from `SECRET_KEY` (SHA-256 of bytes).

Both must be present in Doppler post-migration. **Critical**: if
`CREDENTIALS_ENCRYPTION_KEY` ever changes, every encrypted credential in the
DB becomes unrecoverable — handle as a hot rotation per
`backend/app/utils/encryption.py:6` instructions.

---

## 4. `.gitignore` audit

Current `.gitignore` covers (line numbers in `.gitignore`):

- `.env`, `.env.local`, `.env.production`, `*.env` (lines 2–5) — **OK**
- `*.bak*` (line 60) — **OK**
- `backend/.env.pre-refonte-backup` (line 76) — explicit
- `tasks/` (line 91) — explicit

**Missing** (added on this branch):

- `**/secrets.yml`
- `**/credentials.json`
- `.doppler/`
- `*.env.bak-*` (rotation backups produced by `rotate_anthropic_key.sh`)

Patch applied: see commit on `claude/security-secrets-manager-CDrJk`.

---

## 5. Git history audit

Commands run:

```bash
git log --all --diff-filter=A --pretty="%H %s" -- '*.env'
# → no .env file ever committed

git log --all --pretty="%H %s" -S "DH_SecurePass"
# → 3 commits introduce/touch the password literal:
#   1aefe3a (2026-02-10) docs: Emma coverage analysis
#   61fb0f2 (2026-02-12) fix(BUG-014): granular progress updates
#   579cb19 (2026-02-12) feat(HITL-4): DiffViewer

git log --all --pretty="%H %s" -S "sk-ant-api03"
# → only the rotation playbook commit (a5f482a, placeholder strings)

git log --all --pretty="%H %s" -S "sk-proj-"
# → only the rotation playbook commit (a5f482a, placeholder strings)
```

**Findings**

- No `.env` ever committed. ✅
- No real Anthropic / OpenAI / Stripe / GitHub key in history. ✅
- DB password `DH_SecurePass2025!` present in history since 2026-02-10. ❌ Treat as compromised → rotate.

**Decision** : do **not** rewrite history (`git filter-repo` / `git filter-branch`)
per brief §6. The rotation in §2.2 fix path is sufficient: once Postgres has a
new password, the historical leak refers to a value that no longer grants
access.

---

## 6. VPS-side checks (must run on `72.61.161.222`)

The repo audit can't see `/opt/`, `/etc/systemd/system/`, or journald. Sam
should run the following on the VPS and append the results below before
declaring the audit complete:

```bash
# A. Inventory of .env files actually deployed
sudo find /root /opt /etc -type f \
    \( -name ".env" -o -name ".env.*" -o -name "secrets.yml" -o -name "credentials.json" \) \
    2>/dev/null | grep -v node_modules

# B. Keys (not values) in each .env
for f in $(sudo find /root /opt -name ".env*" -type f 2>/dev/null); do
    echo "=== $f ==="
    sudo grep -E "^[A-Z_]+=" "$f" | cut -d= -f1
    echo
done

# C. systemd units that inject env
sudo grep -rE "Environment=|EnvironmentFile=" /etc/systemd/system/digital-humans*.service 2>/dev/null

# D. Recent journald scan for accidental key leaks (last 7 days)
sudo journalctl -u digital-humans-backend --since "7 days ago" 2>/dev/null \
    | grep -iE "sk-ant-api03-[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}" \
    | head -5
sudo journalctl -u digital-humans-worker  --since "7 days ago" 2>/dev/null \
    | grep -iE "sk-ant-api03-[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}" \
    | head -5

# E. Permissions on env files (should be 600 or 640)
sudo ls -l /opt/digital-humans/rag/.env /opt/digital-humans/backend/.env \
    /root/workspace/digital-humans-production/backend/.env 2>/dev/null
```

### Results to fill in (Sam)

| Check | Output | Notes |
|-------|--------|-------|
| A | _to fill_ | expected: `/opt/digital-humans/rag/.env`, `/opt/digital-humans/backend/.env` (and possibly `backend/.env` in workspace) |
| B | _to fill_ | list of keys; values redacted |
| C | _to fill_ | look for `EnvironmentFile=…` lines |
| D | _to fill_ | expected: empty |
| E | _to fill_ | expected: `0600` or `0640`, owned by `root:root` (or service user) |

---

## 7. Recommended rotations

| Secret | Reason | Priority | Done by |
|--------|--------|----------|---------|
| `OPENAI_API_KEY` | rotated 2026-04-26 by Sam (Headless 360 audit) | done | Sam |
| `POSTGRES_PASSWORD` (`digital_humans` role) | leaked in git history since 2026-02-10 | **HIGH** | Sam (requires Postgres maintenance window — see `docs/operations/secrets-rotation.md` §5) |
| `ANTHROPIC_API_KEY` | preventive (90-day cadence per playbook) | medium | Sam (`scripts/rotate_anthropic_key.sh`) |
| `SECRET_KEY` (JWT) | preventive (180-day cadence) | low | Sam |
| `CREDENTIALS_ENCRYPTION_KEY` | only if leak suspected — rotation requires DB re-encryption migration | low | Sam (with migration plan from `backend/app/utils/encryption.py`) |
| `GITHUB_TOKEN` | only if Sam confirms it exists in `backend/.env` (not seen in repo) | conditional | Sam |

**Claude Code did NOT rotate any external key** (per brief §6 garde-fous) —
all rotations require Sam's hands on the provider consoles.

---

## 8. References

- `docs/SECURITY.md` — Doppler migration plan + ongoing rotation procedure (this audit's companion).
- `docs/operations/secrets-rotation.md` — manual rotation playbook (kept; Doppler procedure cross-references it).
- `scripts/rotate_anthropic_key.sh` — interactive Anthropic key rotator (no changes; will be invoked behind `doppler secrets set` post-migration).
- `SECURITY_TASKS.md` — historical security backlog (SEC-001/2/3 already resolved).

---

*Audit produced by Claude Code · 2026-04-26.*
