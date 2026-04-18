"""
BuildEnabledMiddleware — bloque les endpoints BUILD quand le profile actif le désactive.

C-4 (session3 / Agent C). Résout N35, N41.

Le profile actif vient de LLMRouterService.is_build_enabled(), qui lit
config/llm_routing.yaml > profiles.<profile>.build_enabled.

- cloud     → build_enabled: true   (production)
- on-premise → build_enabled: true   (client airgapped)
- freemium  → build_enabled: false  (démo publique, feature gate)
"""

import re
import logging
from typing import Callable, Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


# Patterns des routes BUILD bloquées en mode freemium.
# Compilés au chargement du module.
BUILD_PATH_PATTERNS: Iterable[re.Pattern] = [
    re.compile(r"^/api/projects/\d+/start-build/?$"),
    re.compile(r"^/api/execute/\d+/build-tasks/?$"),
    re.compile(r"^/api/execute/\d+/build-phases/?$"),
    re.compile(r"^/api/execute/\d+/pause-build/?$"),
    re.compile(r"^/api/execute/\d+/resume-build/?$"),
    re.compile(r"^/api/projects/\d+/build/?$"),
]


def _is_build_path(path: str) -> bool:
    return any(p.match(path) for p in BUILD_PATH_PATTERNS)


class BuildEnabledMiddleware(BaseHTTPMiddleware):
    """
    Reject BUILD requests with 403 when the active deployment profile has
    build_enabled=false (freemium).

    Read-only GETs on /api/config/capabilities are never blocked so the frontend
    can detect the state and adapt its UI.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        if not _is_build_path(request.url.path):
            return await call_next(request)

        try:
            from app.services.llm_router_service import get_llm_router
            router = get_llm_router()
            build_enabled = router.is_build_enabled()
            profile = router.get_active_profile()
        except Exception as exc:
            # Fail open : if we can't read the profile, let the route handle it.
            logger.error("BuildEnabledMiddleware: could not read profile — %s", exc)
            return await call_next(request)

        if build_enabled:
            return await call_next(request)

        logger.info(
            "BuildEnabledMiddleware: blocking %s %s (profile=%s, build_enabled=false)",
            request.method, request.url.path, profile,
        )
        return JSONResponse(
            status_code=403,
            content={
                "detail": "build_disabled",
                "code": "build_disabled",
                "profile": profile,
                "message": (
                    "La génération de code Salesforce (BUILD) n'est pas disponible "
                    "sur le profil freemium. Passez à une formule payante pour activer "
                    "cette fonctionnalité."
                ),
                "upgrade_url": "/pricing",
            },
        )
