# Security — Secrets management

*Owner*: DevOps (Jordan) + Sam (admin) · *Last reviewed*: 2026-04-26
*Companion documents*:
- [`SECURITY_AUDIT_2026_04.md`](./SECURITY_AUDIT_2026_04.md) — codebase audit (which secrets exist, where they leak)
- [`operations/secrets-rotation.md`](./operations/secrets-rotation.md) — manual rotation playbook (per-secret detail)

This document describes **how Digital Humans manages production secrets after
the migration to Doppler**. Manual `.env`-based operation remains documented
in `operations/secrets-rotation.md` as a fallback and as the source for
per-secret rotation procedures (Anthropic, OpenAI, DB, JWT, …).

---

## 1. Overview

All Digital Humans production secrets live in **Doppler**, project
`digital-humans`, config `prod`. The VPS holds a single bootstrap value —
`DOPPLER_TOKEN` — in `/etc/digital-humans/doppler.env` (mode `0600`,
owned by `root:root`). Each systemd unit wraps its `ExecStart` in
`doppler run` so the application processes inherit secrets as plain
environment variables; **no application code changes** are required.

```
┌──────────────────┐  doppler run    ┌──────────────────────┐
│ Doppler cloud    │ ─────────────►  │ digital-humans-      │
│ project: digital │  injects env    │  backend.service     │
│  -humans / prod  │                 │  worker.service      │
└──────────────────┘                 │  frontend.service    │
        ▲                            └──────────────────────┘
        │ doppler secrets set / API
        │
   Sam Hatit (admin), Jordan (devops)
```

`load_dotenv()` in `backend/app/main.py` and `pydantic_settings.BaseSettings`
in `backend/app/config.py` continue to work unchanged: when Doppler injects
env vars, Pydantic just reads them from the process environment instead of
from `.env`.

---

## 2. What lives in Doppler

| Secret | Owner | Rotation cadence | Notes |
|--------|-------|------------------|-------|
| `ANTHROPIC_API_KEY` | Anthropic console | 90 days | rotation script: `scripts/rotate_anthropic_key.sh` |
| `OPENAI_API_KEY` | OpenAI dashboard | 90 days | manual (low volume) |
| `MISTRAL_API_KEY` | Mistral console | 90 days | only if Mistral cloud is re-enabled |
| `DATABASE_URL` | derived from Postgres role password | on incident | full URL in Doppler |
| `POSTGRES_PASSWORD` | Postgres role `digital_humans` | on incident | kept alongside `DATABASE_URL` for `docker-compose` use |
| `SECRET_KEY` | self-generated (`secrets.token_urlsafe(32)`) | 180 days | rotating invalidates JWT sessions |
| `CREDENTIALS_ENCRYPTION_KEY` | Fernet key (`Fernet.generate_key()`) | only if leak | rotating requires DB re-encryption migration (`backend/app/utils/encryption.py` §SECRET KEY ROTATION) |
| `GITHUB_TOKEN` | GitHub fine-grained PAT | 90 days | only if Jordan deploy service is enabled |
| `SENDGRID_API_KEY` / `RESEND_API_KEY` | provider | 90 days | only if email is enabled |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Stripe dashboard | on rotation | reserved for Phase 3 — not yet provisioned |
| `DH_*` infra paths (`DH_PROJECT_ROOT`, `DH_CHROMA_PATH`, …) | infra | n/a | **not secrets**; kept in Doppler for parity |

The list of secrets *actually present* in `prod` is the source of truth; run
`doppler secrets --project digital-humans --config prod --only-names` to refresh
the table when adding a new key.

### Configs (Doppler "environments")

- `dev` — for engineers' laptops; values seeded from `backend/.env.example` and personal API keys.
- `prod` — production VPS (`72.61.161.222`).
- `ci` — GitHub Actions; only the subset CI needs (no LLM keys for unit tests).

---

## 3. Migration plan (one-shot, runs on the VPS)

**Pre-flight** : Sam validates the Doppler account (`Sam Hatit Consulting`,
free tier ≤ 5 devs) and shares the workplace token with the operator.

The migration is split into 6 steps. Each step is reversible until step 6.

### Step 1 — Install CLI on the VPS

```bash
curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh \
    | sudo sh
doppler --version    # expect 3.x
```

### Step 2 — Create the project + configs

```bash
# Authenticate as Sam (admin token, one-time)
doppler login

# Create the project and 3 configs
doppler projects create digital-humans
doppler environments create --project digital-humans dev
doppler environments create --project digital-humans prod
doppler environments create --project digital-humans ci
```

### Step 3 — Import existing secrets

For each `.env` discovered in [`SECURITY_AUDIT_2026_04.md`](./SECURITY_AUDIT_2026_04.md) §6
(after Sam has filled in the VPS-side check results), run:

```bash
doppler secrets upload /opt/digital-humans/backend/.env \
    --project digital-humans --config prod
doppler secrets upload /opt/digital-humans/rag/.env \
    --project digital-humans --config prod   # OPENAI_API_KEY etc.
```

Then verify (names only, never the values):

```bash
doppler secrets --project digital-humans --config prod --only-names
```

### Step 4 — Provision the bootstrap token on the VPS

Generate a **service token** (read-only, scoped to `prod`) from the Doppler UI
or CLI:

```bash
doppler configs tokens create vps-bootstrap \
    --project digital-humans --config prod --plain > /tmp/dt
sudo install -m 0600 -o root -g root /dev/null /etc/digital-humans/doppler.env
echo "DOPPLER_TOKEN=$(cat /tmp/dt)" | sudo tee /etc/digital-humans/doppler.env >/dev/null
shred -u /tmp/dt
sudo chmod 600 /etc/digital-humans/doppler.env
```

### Step 5 — Switch services to `doppler run`

The systemd unit templates live at
[`docs/operations/systemd-doppler/`](./operations/systemd-doppler/) (this branch
ships them as `*.service.example`). Each one wraps the original `ExecStart`:

```ini
[Service]
EnvironmentFile=/etc/digital-humans/doppler.env
ExecStart=/usr/local/bin/doppler run \
    --project digital-humans --config prod \
    --token "${DOPPLER_TOKEN}" \
    -- /opt/digital-humans/backend/venv/bin/python -m uvicorn app.main:app \
       --host 0.0.0.0 --port 8002
```

Apply on the VPS:

```bash
sudo cp docs/operations/systemd-doppler/digital-humans-backend.service.example \
    /etc/systemd/system/digital-humans-backend.service
sudo cp docs/operations/systemd-doppler/digital-humans-worker.service.example \
    /etc/systemd/system/digital-humans-worker.service
sudo cp docs/operations/systemd-doppler/digital-humans-frontend.service.example \
    /etc/systemd/system/digital-humans-frontend.service
sudo systemctl daemon-reload
sudo systemctl restart digital-humans-backend digital-humans-worker digital-humans-frontend
sudo systemctl status digital-humans-backend --no-pager
```

### Step 6 — Cleanup `.env` on disk

Once all three services come up healthy and pass the smoke test (§5):

```bash
STAMP=$(date +%Y%m%d-%H%M%S)
sudo install -d -m 0700 /root/.secrets_backup_${STAMP}
sudo cp /opt/digital-humans/backend/.env /root/.secrets_backup_${STAMP}/backend.env
sudo cp /opt/digital-humans/rag/.env     /root/.secrets_backup_${STAMP}/rag.env
sudo chmod 600 /root/.secrets_backup_${STAMP}/*

# Replace the live .env files by an empty placeholder. We DO NOT delete them
# because some legacy paths still call load_dotenv() and a missing file emits
# a noisy warning.
echo "# Secrets are read via Doppler — see docs/SECURITY.md" \
    | sudo tee /opt/digital-humans/backend/.env >/dev/null
echo "# Secrets are read via Doppler — see docs/SECURITY.md" \
    | sudo tee /opt/digital-humans/rag/.env >/dev/null
sudo chmod 600 /opt/digital-humans/backend/.env /opt/digital-humans/rag/.env
```

The backup directory is the rollback escape hatch: if a service refuses to
start, restore the corresponding `.env` and `systemctl restart`.

---

## 4. Routine rotation procedure (post-migration)

For any secret already in Doppler:

1. **Generate the new value** at the provider (Anthropic console, OpenAI dashboard, GitHub PAT settings, …). For self-generated secrets:
   - `SECRET_KEY` → `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`
   - `CREDENTIALS_ENCRYPTION_KEY` → `python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`
2. **Stage** the new value in Doppler:
   ```bash
   doppler secrets set ANTHROPIC_API_KEY="<new>" \
       --project digital-humans --config prod
   ```
3. **Restart** the consumers:
   ```bash
   sudo systemctl restart digital-humans-backend digital-humans-worker
   ```
4. **Verify** :
   ```bash
   curl -sf http://localhost:8002/api/health
   sudo journalctl -u digital-humans-backend -f --since "1 minute ago" | head -50
   ```
5. **Revoke** the old value at the provider (Anthropic console, OpenAI dashboard, etc.).
6. **Log** the rotation in this document's §6 ("Rotation log").

For per-secret nuances (DB password requires `ALTER USER` + maintenance window;
JWT rotation invalidates sessions; …), see
[`operations/secrets-rotation.md`](./operations/secrets-rotation.md). That
document is the source for **what** to rotate; this one is the source for
**where** the value flows.

### Failed rotation — rollback

If `/api/health` fails after a restart:

```bash
# Restore the previous value from Doppler version history
doppler secrets versions --project digital-humans --config prod ANTHROPIC_API_KEY
doppler secrets versions rollback <version> ANTHROPIC_API_KEY \
    --project digital-humans --config prod
sudo systemctl restart digital-humans-backend
```

If Doppler itself is unreachable, the systemd unit will fail to start. Last
resort fallback: copy the `.env` from `/root/.secrets_backup_<stamp>/` back
into `/opt/digital-humans/backend/.env`, swap the unit's `ExecStart` back to
the pre-migration form, and `systemctl restart`.

---

## 5. Smoke test checklist

Run this after **any** secret change (rotation or migration):

```bash
# A. Services are up
systemctl is-active digital-humans-backend digital-humans-worker digital-humans-frontend

# B. Health endpoints
curl -sf http://localhost:8002/api/health   && echo "backend OK"
curl -sf http://localhost:8002/             && echo "root OK"

# C. LLM call (uses ANTHROPIC_API_KEY) — if a /api/llm/test endpoint exists
curl -sf -X POST http://localhost:8002/api/llm/test || echo "(skip: no test endpoint)"

# D. RAG (uses OPENAI_API_KEY for embeddings)
curl -sf http://localhost:8002/api/rag/health || echo "(skip: no rag endpoint)"

# E. No secret leaks in the log
sudo journalctl -u digital-humans-backend --since "5 minutes ago" \
    | grep -iE "sk-ant-api03-[A-Za-z0-9_-]{20,}|sk-proj-[A-Za-z0-9]{20,}|DH_SecurePass" \
    | head -3   # expected: empty
```

All five checks must pass before the rotation/migration is declared done.

---

## 6. Rotation log

| Date (UTC) | Secret | Trigger | Operator | Notes |
|------------|--------|---------|----------|-------|
| 2026-04-26 | `OPENAI_API_KEY` | Headless 360 audit | Sam | rotated; old key revoked. Pre-Doppler. |
| 2026-04-26 | (audit) | Track A2 — secrets manager planning | Claude Code | inventory in `SECURITY_AUDIT_2026_04.md`; no rotation performed by Claude. |
| _next_     | `POSTGRES_PASSWORD` | leak in git history (2026-02-10) | Sam (planned) | requires Postgres maintenance window. |

Append one row per rotation. Do **not** record secret values, only metadata.

---

## 7. Pre-deploy checklist

Before any deploy that touches secrets or services:

- [ ] No secret in plain text in any committed file (`git diff origin/main -- ':(exclude)docs' ':(exclude)*.md' | grep -iE 'sk-ant-api03|sk-proj|DH_Secure|password\s*='`)
- [ ] `.gitignore` covers `.env*`, `secrets.yml`, `credentials.json`, `.doppler/`
- [ ] `DOPPLER_TOKEN` is configured in `/etc/digital-humans/doppler.env` on the target VPS
- [ ] Smoke test from §5 passes against the target environment
- [ ] Rotation log §6 has the latest entry

---

## 8. Access control

| Person | Role | Doppler scope |
|--------|------|---------------|
| Sam Hatit | admin | all projects, all configs |
| _to fill_ | devops | `digital-humans/prod` (read+write) |
| _to fill_ | dev | `digital-humans/dev` only |
| CI pipeline | service-token | `digital-humans/ci` (read-only) |
| VPS bootstrap | service-token | `digital-humans/prod` (read-only) — `/etc/digital-humans/doppler.env` |

Service tokens are revocable individually from the Doppler UI; if a VPS is
suspected compromised, revoke its bootstrap token before any other action.

---

## 9. References

- Doppler docs: https://docs.doppler.com/docs/install-cli, https://docs.doppler.com/docs/service-tokens
- Companion: [`SECURITY_AUDIT_2026_04.md`](./SECURITY_AUDIT_2026_04.md), [`operations/secrets-rotation.md`](./operations/secrets-rotation.md)
- Systemd unit templates: [`operations/systemd-doppler/`](./operations/systemd-doppler/)
- Ongoing checklist: §7 above
