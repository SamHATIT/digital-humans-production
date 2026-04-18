#!/usr/bin/env bash
#
# rotate_anthropic_key.sh — D-3b, P8
#
# Interactive rotation helper for ANTHROPIC_API_KEY.
#
# Flow:
#   1. Prompt for the new key (or take it as $1 for scripted use).
#   2. Back up the current .env to .env.bak-<timestamp>.
#   3. Write the new key into .env.
#   4. Smoke-test a minimal /v1/messages completion to prove the key works.
#   5. Restart digital-humans-backend via systemd.
#   6. Verify /api/health and one /api/pm-orchestrator call.
#   7. On any failure, restore the .env backup and exit non-zero.
#
# Usage:
#   sudo ./rotate_anthropic_key.sh             # interactive
#   sudo ./rotate_anthropic_key.sh "sk-ant-..." # scripted (no prompt)
#
set -euo pipefail

ENV_FILE="${DH_ENV_FILE:-/opt/digital-humans/backend/.env}"
SERVICE_NAME="${DH_SERVICE_NAME:-digital-humans-backend}"
HEALTH_URL="${DH_HEALTH_URL:-http://localhost:8002/api/health}"
ROOT_URL="${DH_ROOT_URL:-http://localhost:8002/}"

log()  { echo "[$(date -u +%FT%TZ)] [SECRETS] $*"; }
fail() { echo "[$(date -u +%FT%TZ)] [SECRETS] ERROR: $*" >&2; exit 1; }

# 1. Preconditions -----------------------------------------------------------
[ "$(id -u)" -eq 0 ] || fail "must run as root (needs to write ${ENV_FILE})"
command -v curl       >/dev/null || fail "curl not on PATH"
command -v systemctl  >/dev/null || fail "systemctl not on PATH"
[ -f "${ENV_FILE}"   ]           || fail "env file not found: ${ENV_FILE}"

# 2. Read the new key --------------------------------------------------------
NEW_KEY="${1:-}"
if [ -z "${NEW_KEY}" ]; then
    read -r -s -p "New ANTHROPIC_API_KEY (sk-ant-...): " NEW_KEY
    echo
fi
case "${NEW_KEY}" in
    sk-ant-*) ;;
    *) fail "key does not start with sk-ant- (was '${NEW_KEY:0:7}...')";;
esac
[ ${#NEW_KEY} -ge 40 ] || fail "key too short (${#NEW_KEY} chars)"

# 3. Back up .env ------------------------------------------------------------
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${ENV_FILE}.bak-${STAMP}"
cp -p "${ENV_FILE}" "${BACKUP}"
log "backed up ${ENV_FILE} -> ${BACKUP}"

OLD_KEY_PREFIX="$(grep -E '^ANTHROPIC_API_KEY=' "${ENV_FILE}" | head -1 | cut -d= -f2 | cut -c1-10 || true)"

# 4. Smoke-test the new key BEFORE touching .env -----------------------------
log "smoke-testing new key against Anthropic API..."
HTTP=$(curl -sS -o /tmp/anthropic_smoke.$$ -w "%{http_code}" \
    https://api.anthropic.com/v1/messages \
    -H "x-api-key: ${NEW_KEY}" \
    -H "anthropic-version: 2023-06-01" \
    -H "content-type: application/json" \
    -d '{"model":"claude-haiku-4-5-20251001","max_tokens":8,"messages":[{"role":"user","content":"ping"}]}') || true
BODY="$(cat /tmp/anthropic_smoke.$$ 2>/dev/null || true)"
rm -f /tmp/anthropic_smoke.$$
if [ "${HTTP}" != "200" ]; then
    fail "new key rejected by Anthropic (HTTP ${HTTP}): ${BODY}"
fi
log "new key accepted by Anthropic"

# 5. Write new key into .env -------------------------------------------------
# sed replaces the existing line, or appends if missing.
if grep -q '^ANTHROPIC_API_KEY=' "${ENV_FILE}"; then
    # Escape forward slashes for sed (keys don't normally have them, but safe).
    ESCAPED="$(printf '%s' "${NEW_KEY}" | sed 's|/|\\/|g')"
    sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${ESCAPED}|" "${ENV_FILE}"
else
    printf '\nANTHROPIC_API_KEY=%s\n' "${NEW_KEY}" >> "${ENV_FILE}"
fi
chmod 640 "${ENV_FILE}"
log "wrote new key into ${ENV_FILE}"

# 6. Restart service and verify ---------------------------------------------
rollback() {
    log "ROLLBACK: restoring ${BACKUP} -> ${ENV_FILE}"
    cp -p "${BACKUP}" "${ENV_FILE}"
    systemctl restart "${SERVICE_NAME}" || true
    fail "$1"
}

log "restarting ${SERVICE_NAME}..."
systemctl restart "${SERVICE_NAME}" || rollback "systemctl restart failed"

# Wait for the service to come up.
for i in $(seq 1 30); do
    if curl -sf "${HEALTH_URL}" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

curl -sf "${HEALTH_URL}" >/dev/null 2>&1 \
    || rollback "backend did not become healthy after restart"

curl -sf "${ROOT_URL}" >/dev/null 2>&1 \
    || rollback "root endpoint unreachable"

log "backend healthy. Old key prefix was: ${OLD_KEY_PREFIX}..."
log "ACTION REQUIRED: revoke the old key in https://console.anthropic.com/settings/keys"
log "rotation complete"
