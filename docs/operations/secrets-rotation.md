# Secrets Rotation — Operational Playbook

*Owner*: DevOps (Jordan) · *Last reviewed*: 2026-04-18 · *Trigger to rerun*: every 90 days or after any incident with suspected key leakage.

This document describes the **manual** rotation procedure for every secret the Digital Humans backend depends on. Full integration with a secret manager (Vault / AWS Secrets Manager) is tracked as a follow-up in `docs/BACKLOG.md` and is **out of scope** for session 3 refonte.

---

## 1. Inventory of critical secrets

| Name | Where it lives | Blast radius if leaked | Rotation cadence |
|------|----------------|-----------------------|------------------|
| `ANTHROPIC_API_KEY` | `backend/.env` + systemd unit env file | All Claude LLM calls — leak = uncontrolled spend. | 90 days |
| `OPENAI_API_KEY` | `backend/.env` | Embeddings + fallback LLM. Lower priority than Anthropic. | 90 days |
| `DATABASE_URL` | `backend/.env` (password component) | Full DB access. | On incident only |
| `SECRET_KEY` | `backend/.env` | JWT signing — rotating invalidates all sessions. | 180 days |
| `GITHUB_TOKEN` | `backend/.env` (used by `jordan_deploy_service`) | Push access to the deployment repo. | 90 days |
| `SALESFORCE_ACCESS_TOKEN` | SFDX JWT auth file (per-org, not checked into git) | Full Salesforce metadata R/W. | Auto (JWT expiry) |

Keys marked **90 days** have a **hard expiry** reminder in the team calendar. Keys marked **On incident only** rotate only in response to a confirmed leak (rotating a live `DATABASE_URL` requires a maintenance window).

---

## 2. General rotation contract

Every rotation **must**:

1. Produce a new value from the provider's UI or CLI.
2. Place it in the env file *alongside* the old one (e.g. `ANTHROPIC_API_KEY_NEW=...`).
3. Run a validation call against the provider.
4. Promote `*_NEW` → canonical name (overwriting the old value).
5. Restart the service.
6. Verify the backend comes up healthy (`/api/health`) **and** one end-to-end LLM call succeeds.
7. Revoke the *old* value at the provider.
8. Update the "last rotated" date in this document.

If step 6 fails, the rollback path is always: restore the previous env value, restart, and file an incident.

---

## 3. ANTHROPIC_API_KEY — step by step

This is the highest-volume secret. A dedicated helper script is shipped at `scripts/rotate_anthropic_key.sh` (see `D-3b`).

```bash
# 1. Create a new key in https://console.anthropic.com/settings/keys
#    Give it a description like "digital-humans-prod-2026-Q2".

# 2. Run the helper (interactive prompt for the new key):
sudo /opt/digital-humans/scripts/rotate_anthropic_key.sh

# 3. The helper will:
#    - Back up the current .env to .env.bak-YYYYMMDD-HHMMSS
#    - Write the new key into .env
#    - Run a smoke-test completion call via curl
#    - Restart digital-humans-backend
#    - curl /api/health and one /api/pm-orchestrator call to verify
#    - Print the old key prefix so you can revoke it in the console

# 4. Revoke the old key in the Anthropic console (manual — intentional,
#    so a human always confirms the replacement actually works end-to-end).
```

The script refuses to proceed unless:
- It is run as root (to write protected env files).
- The new key starts with the `sk-ant-` prefix.
- `curl` and `systemctl` are available on PATH.

If the smoke-test step fails, the script **automatically restores the backup** and exits non-zero.

---

## 4. OPENAI_API_KEY

No helper script (lower volume). Manual rotation:

```bash
sudo cp /opt/digital-humans/backend/.env /opt/digital-humans/backend/.env.bak-$(date +%Y%m%d-%H%M%S)
sudo sed -i 's|^OPENAI_API_KEY=.*|OPENAI_API_KEY=sk-proj-NEWVALUE|' /opt/digital-humans/backend/.env
sudo systemctl restart digital-humans-backend
curl -sf http://localhost:8002/api/health && echo "backend healthy"
# Trigger an embedding call (e.g. small RAG search) and check logs:
sudo journalctl -u digital-humans-backend -f | grep -i openai
# If OK, revoke the old key at https://platform.openai.com/api-keys
```

---

## 5. DATABASE_URL (password)

Requires a short maintenance window (connections drop during Postgres role update):

```bash
# 1. Announce maintenance.
# 2. In psql:
ALTER USER digital_humans WITH PASSWORD 'NEWPASSWORD';

# 3. Update the backend env and restart:
sudo sed -i 's|://digital_humans:[^@]*@|://digital_humans:NEWPASSWORD@|' /opt/digital-humans/backend/.env
sudo systemctl restart digital-humans-backend

# 4. Verify.
curl -sf http://localhost:8002/api/health
```

---

## 6. SECRET_KEY (JWT)

**Warning**: rotating the JWT secret invalidates every existing user session immediately. Schedule for a low-traffic window and notify users.

```bash
NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
sudo sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${NEW_KEY}|" /opt/digital-humans/backend/.env
sudo systemctl restart digital-humans-backend
```

---

## 7. GITHUB_TOKEN (deployment)

Used by `jordan_deploy_service` to push generated artifacts.

1. Create a fine-grained PAT in https://github.com/settings/personal-access-tokens with `contents: write` on `SamHATIT/digital-humans-sf-customer-*`.
2. Replace in `.env` as above.
3. Trigger a dry-run deploy in a non-prod project to verify.
4. Delete the old PAT.

---

## 8. SALESFORCE_ACCESS_TOKEN

These are short-lived JWTs minted from the `JWT_KEY_FILE` + consumer key. Rotation of the underlying consumer key is a **customer-initiated** operation (they re-auth their org from the UI) — there is nothing to rotate server-side beyond deleting the cached token file:

```bash
rm -f /opt/digital-humans/sfdx-auth/<org-alias>.json
# Next API call will force re-auth via the UI.
```

---

## 9. Audit & compliance

Every rotation leaves two artifacts:

- A timestamped `.env.bak-*` backup next to the live env file (kept 30 days, then pruned by cron).
- A log entry in `journalctl -u digital-humans-backend` tagged `[SECRETS] rotated <NAME>` (emitted by the rotation script).

For SOC-2 evidence, export `journalctl --since="90 days ago" | grep "\[SECRETS\]" > audit/secrets-rotation-Q$(date +%q).log` at the end of each quarter.

---

## 10. Next steps (out of scope)

- Integrate Vault or AWS Secrets Manager; remove `.env` as a source of secrets.
- Auto-rotate 90-day keys from a scheduled GitHub Action.
- Hook the rotation script into PagerDuty for failure alerts.
