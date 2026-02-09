#!/usr/bin/env bash
# install.sh — Install and activate Digital Humans systemd services
# Replaces manual nohup launches with proper service management.
#
# Usage (on VPS as root):
#   cd /root/workspace/digital-humans-production/deploy/systemd
#   chmod +x install.sh && ./install.sh
#
# What this does:
#   1. Kills any existing manual uvicorn/vite processes
#   2. Copies .service files to /etc/systemd/system/
#   3. Reloads systemd, enables and starts both services
#   4. Verifies services are running and endpoints respond

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICES=("digital-humans-backend" "digital-humans-frontend")

echo "=== Digital Humans — systemd service installer ==="

# --- Pre-checks ---
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root." >&2
    exit 1
fi

if ! command -v systemctl &>/dev/null; then
    echo "ERROR: systemctl not found. Is systemd available?" >&2
    exit 1
fi

# --- Step 1: Kill manual processes ---
echo ""
echo "[1/5] Stopping manual processes..."

if pgrep -f "uvicorn app.main:app.*8002" &>/dev/null; then
    kill "$(pgrep -f 'uvicorn app.main:app.*8002')" 2>/dev/null || true
    echo "  Killed manual uvicorn process"
else
    echo "  No manual uvicorn process found"
fi

if pgrep -f "vite.*3000" &>/dev/null; then
    kill "$(pgrep -f 'vite.*3000')" 2>/dev/null || true
    echo "  Killed manual vite process"
else
    echo "  No manual vite process found"
fi

sleep 2

# --- Step 2: Copy service files ---
echo ""
echo "[2/5] Installing service files..."
for svc in "${SERVICES[@]}"; do
    cp "${SCRIPT_DIR}/${svc}.service" "/etc/systemd/system/${svc}.service"
    echo "  Installed ${svc}.service"
done

# --- Step 3: Reload and enable ---
echo ""
echo "[3/5] Reloading systemd and enabling services..."
systemctl daemon-reload

for svc in "${SERVICES[@]}"; do
    systemctl enable "${svc}"
    echo "  Enabled ${svc}"
done

# --- Step 4: Start services ---
echo ""
echo "[4/5] Starting services..."
for svc in "${SERVICES[@]}"; do
    systemctl start "${svc}"
    echo "  Started ${svc}"
done

sleep 3

# --- Step 5: Verify ---
echo ""
echo "[5/5] Verifying..."

ALL_OK=true

for svc in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "${svc}"; then
        echo "  [OK] ${svc} is active"
    else
        echo "  [FAIL] ${svc} is NOT active"
        systemctl status "${svc}" --no-pager || true
        ALL_OK=false
    fi
done

# Wait a bit for services to fully start
sleep 3

if curl -sf http://localhost:8002/health &>/dev/null; then
    echo "  [OK] Backend health check passed (port 8002)"
else
    echo "  [WARN] Backend health check failed — may still be starting"
    ALL_OK=false
fi

if curl -sf http://localhost:3000 &>/dev/null; then
    echo "  [OK] Frontend responding (port 3000)"
else
    echo "  [WARN] Frontend check failed — may still be starting"
    ALL_OK=false
fi

echo ""
if $ALL_OK; then
    echo "=== All services installed and running ==="
else
    echo "=== Installation complete with warnings — check output above ==="
fi

echo ""
echo "Useful commands:"
echo "  systemctl status digital-humans-backend"
echo "  systemctl status digital-humans-frontend"
echo "  journalctl -u digital-humans-backend -f        # live backend logs"
echo "  journalctl -u digital-humans-frontend -f       # live frontend logs"
echo "  journalctl -u digital-humans-backend --since '1 hour ago'"
echo "  systemctl restart digital-humans-backend"
echo "  systemctl restart digital-humans-frontend"
