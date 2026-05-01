"""Journal webhook endpoint.

Triggered by Ghost on post.{published,updated,deleted} (and manually via cron
fallback). Runs scripts/journal/build.py asynchronously so the request
returns fast.

Auth: shared secret in `?secret=` query param (Ghost can include it in URL).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/journal", tags=["webhooks"])

WEBHOOK_SECRET = os.environ.get("JOURNAL_WEBHOOK_SECRET", "")
BUILD_SCRIPT = Path("/root/workspace/digital-humans-production/scripts/journal/build.py")

# Simple in-memory rate limit / debounce: only run if last build > 5s ago.
_last_build_at: float = 0.0
_build_lock = asyncio.Lock()


async def _run_builder() -> tuple[int, str]:
    """Run build.py and return (rc, output)."""
    proc = await asyncio.create_subprocess_exec(
        "python3", str(BUILD_SCRIPT), "-v",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ},
    )
    stdout, _ = await proc.communicate()
    return proc.returncode, stdout.decode("utf-8", errors="replace")


@router.post("/rebuild")
async def rebuild(request: Request, secret: str = Query(default="")) -> dict:
    """Trigger a Journal rebuild. Called by Ghost webhook."""
    global _last_build_at

    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        logger.warning("journal webhook rejected: bad secret from %s", request.client.host if request.client else "?")
        raise HTTPException(status_code=403, detail="invalid secret")

    # Debounce: if a build ran in the last 5 seconds, skip
    now = time.time()
    if now - _last_build_at < 5.0:
        return {"status": "debounced", "last_build_age_s": round(now - _last_build_at, 2)}

    async with _build_lock:
        _last_build_at = time.time()
        rc, output = await _run_builder()
        success = rc == 0
        if not success:
            logger.error("journal build failed: rc=%s\n%s", rc, output)
        else:
            logger.info("journal build ok\n%s", output[-500:])
        return {"status": "ok" if success else "error", "rc": rc, "output_tail": output[-1000:]}


@router.get("/health")
async def health() -> dict:
    """No-auth health probe — verifies the route is reachable & build script exists."""
    return {
        "ok": True,
        "build_script": str(BUILD_SCRIPT),
        "build_script_exists": BUILD_SCRIPT.exists(),
        "secret_configured": bool(WEBHOOK_SECRET),
        "last_build_age_s": round(time.time() - _last_build_at, 2) if _last_build_at else None,
    }
