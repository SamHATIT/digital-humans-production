"""
PM Orchestrator routes package.

P4: Split from the 2636-line pm_orchestrator.py fat controller into
focused route modules. Each module handles one concern.

Module map:
- project_routes:   6 routes — Project CRUD
- execution_routes: 8 routes — SDS execution lifecycle
- build_routes:     4 routes — BUILD monitoring & start
- chat_ws_routes:   2 routes — Chat & WebSocket
- retry_routes:     4 routes — Retry, pause, resume
- sds_v3_routes:    8 routes — SDS V3 pipeline (microanalyze → DOCX)
- build_executor:   execute_build_v2() background function
- _helpers:         Shared constants & utilities
"""
from fastapi import APIRouter

from app.api.routes.orchestrator.project_routes import router as project_router
from app.api.routes.orchestrator.execution_routes import router as execution_router
from app.api.routes.orchestrator.build_routes import router as build_router
from app.api.routes.orchestrator.chat_ws_routes import router as chat_ws_router
from app.api.routes.orchestrator.retry_routes import router as retry_router
from app.api.routes.orchestrator.sds_v3_routes import router as sds_v3_router

# Combined router — preserves the same API surface as the original pm_orchestrator.py
router = APIRouter(tags=["PM Orchestrator"])

router.include_router(project_router)
router.include_router(execution_router)
router.include_router(build_router)
router.include_router(chat_ws_router)
router.include_router(retry_router)
router.include_router(sds_v3_router)
