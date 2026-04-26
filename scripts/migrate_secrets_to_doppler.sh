#!/usr/bin/env bash
#
# migrate_secrets_to_doppler.sh — Track A2 helper.
#
# One-shot helper that runs on the VPS to perform the Doppler migration
# described in docs/SECURITY.md §3. Idempotent: re-running after a partial
# run is safe.
#
# What it does (each step is gated and logged):
#   1. Verifies the doppler CLI is installed and authenticated.
#   2. Backs up every .env file the audit found into /root/.secrets_backup_<stamp>/.
#   3. Imports each .env into Doppler (project digital-humans, config prod).
#   4. Diffs Doppler against each .env to confirm nothing was lost.
#   5. Replaces each .env with a placeholder that just notes "see SECURITY.md".
#   6. Prints the next manual step (apply systemd units + restart services).
#
# What it does NOT do (safety):
#   - Does NOT touch /etc/systemd/system/digital-humans-*.service. Apply the
#     templates from docs/operations/systemd-doppler/ manually.
#   - Does NOT restart any service.
#   - Does NOT rotate any external secret (Anthropic, OpenAI, GitHub PAT, …).
#   - Does NOT delete the original .env files — only replaces them with a
#     comment-only placeholder. Originals are kept in the timestamped backup.
#
# Usage:
#   sudo DOPPLER_TOKEN=<service-token> ./migrate_secrets_to_doppler.sh
#
# Dry-run (audits only, makes no changes):
#   sudo DOPPLER_TOKEN=<service-token> DRY_RUN=1 ./migrate_secrets_to_doppler.sh

set -euo pipefail

PROJECT="${DOPPLER_PROJECT:-digital-humans}"
CONFIG="${DOPPLER_CONFIG:-prod}"
DRY_RUN="${DRY_RUN:-0}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/root/.secrets_backup_${STAMP}"

# .env files to migrate (extend if Sam's audit (§6 of SECURITY_AUDIT) finds more)
ENV_FILES=(
    "/opt/digital-humans/backend/.env"
    "/opt/digital-humans/rag/.env"
)

log()  { echo "[$(date -u +%FT%TZ)] [MIGRATE] $*"; }
fail() { echo "[$(date -u +%FT%TZ)] [MIGRATE] ERROR: $*" >&2; exit 1; }

run() {
    if [ "${DRY_RUN}" = "1" ]; then
        log "DRY-RUN: $*"
    else
        eval "$@"
    fi
}

# 1. Pre-flight ---------------------------------------------------------------
[ "$(id -u)" -eq 0 ]              || fail "must run as root"
command -v doppler  >/dev/null    || fail "doppler CLI not on PATH (install: curl -Ls https://cli.doppler.com/install.sh | sudo sh)"
[ -n "${DOPPLER_TOKEN:-}" ]       || fail "DOPPLER_TOKEN env var not set"

log "doppler version: $(doppler --version)"
log "project=${PROJECT} config=${CONFIG} dry_run=${DRY_RUN}"

# Sanity check: token has access to the target config.
DOPPLER_TOKEN="${DOPPLER_TOKEN}" doppler secrets \
    --project "${PROJECT}" --config "${CONFIG}" --only-names >/dev/null \
    || fail "doppler token rejected for ${PROJECT}/${CONFIG}"
log "doppler token accepted"

# 2. Backup -------------------------------------------------------------------
log "creating backup directory ${BACKUP_DIR}"
run "install -d -m 0700 -o root -g root \"${BACKUP_DIR}\""
for f in "${ENV_FILES[@]}"; do
    if [ -f "${f}" ]; then
        dst="${BACKUP_DIR}/$(echo "${f}" | tr '/' '_').env"
        run "cp -p \"${f}\" \"${dst}\""
        run "chmod 600 \"${dst}\""
        log "backed up ${f} -> ${dst}"
    else
        log "skip (missing): ${f}"
    fi
done

# 3. Import into Doppler ------------------------------------------------------
for f in "${ENV_FILES[@]}"; do
    [ -f "${f}" ] || continue
    log "importing ${f} into doppler ${PROJECT}/${CONFIG}"
    run "DOPPLER_TOKEN=\"${DOPPLER_TOKEN}\" doppler secrets upload \"${f}\" \
            --project \"${PROJECT}\" --config \"${CONFIG}\" --silent"
done

# 4. Diff verification --------------------------------------------------------
log "verifying Doppler has every key from each .env"
for f in "${ENV_FILES[@]}"; do
    [ -f "${f}" ] || continue
    missing=""
    while IFS= read -r line; do
        # Skip comments and blanks
        case "${line}" in
            \#*|"") continue ;;
        esac
        key="${line%%=*}"
        # Remove leading 'export ' if present
        key="${key#export }"
        [ -n "${key}" ] || continue
        if ! DOPPLER_TOKEN="${DOPPLER_TOKEN}" doppler secrets get "${key}" \
                --project "${PROJECT}" --config "${CONFIG}" --plain >/dev/null 2>&1; then
            missing="${missing} ${key}"
        fi
    done < "${f}"
    if [ -n "${missing}" ]; then
        fail "Doppler is missing keys from ${f}:${missing}"
    fi
    log "OK: every key from ${f} is present in Doppler"
done

# 5. Replace .env with placeholder -------------------------------------------
for f in "${ENV_FILES[@]}"; do
    [ -f "${f}" ] || continue
    log "replacing ${f} with placeholder (original backed up at ${BACKUP_DIR})"
    if [ "${DRY_RUN}" = "1" ]; then
        log "DRY-RUN: would write placeholder to ${f}"
    else
        printf '# Secrets read via Doppler — see docs/SECURITY.md\n' > "${f}"
        chmod 600 "${f}"
    fi
done

# 6. Next steps ---------------------------------------------------------------
cat <<EOF
[$(date -u +%FT%TZ)] [MIGRATE] migration data complete.

Next manual steps (NOT automated by this script):
  1. Provision /etc/digital-humans/doppler.env on this VPS:
       sudo install -d -m 0700 /etc/digital-humans
       echo "DOPPLER_TOKEN=\${DOPPLER_TOKEN}" | sudo tee /etc/digital-humans/doppler.env >/dev/null
       sudo chmod 600 /etc/digital-humans/doppler.env

  2. Apply the systemd unit templates:
       sudo cp /etc/systemd/system/digital-humans-backend.service \\
               /etc/systemd/system/digital-humans-backend.service.bak-${STAMP}
       sudo cp docs/operations/systemd-doppler/digital-humans-backend.service.example \\
               /etc/systemd/system/digital-humans-backend.service
       # idem for worker + frontend

  3. Reload + restart:
       sudo systemctl daemon-reload
       sudo systemctl restart digital-humans-backend digital-humans-worker digital-humans-frontend

  4. Run the smoke test in docs/SECURITY.md §5.

  5. If a service refuses to start, restore from ${BACKUP_DIR}:
       sudo cp ${BACKUP_DIR}/_opt_digital-humans_backend_.env /opt/digital-humans/backend/.env
       sudo cp /etc/systemd/system/digital-humans-backend.service.bak-${STAMP} \\
               /etc/systemd/system/digital-humans-backend.service
       sudo systemctl daemon-reload
       sudo systemctl restart digital-humans-backend
EOF
