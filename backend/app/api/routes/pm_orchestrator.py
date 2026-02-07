"""
PM Orchestrator API routes — Thin wrapper.

P4 REFACTORED: This file was 2636 lines (Fat Controller anti-pattern).
All route logic has been extracted to app.api.routes.orchestrator/ package:

- orchestrator/project_routes.py    — Project CRUD (6 routes)
- orchestrator/execution_routes.py  — SDS execution lifecycle (8 routes)
- orchestrator/build_routes.py      — BUILD monitoring & start (4 routes)
- orchestrator/chat_ws_routes.py    — Chat & WebSocket (2 routes)
- orchestrator/retry_routes.py      — Retry, pause, resume (4 routes)
- orchestrator/sds_v3_routes.py     — SDS V3 pipeline (8 routes)
- orchestrator/build_executor.py    — execute_build_v2() background function
- orchestrator/_helpers.py          — Shared constants & utilities

This file now only re-exports the combined router for backwards compatibility
with main.py imports.
"""
from app.api.routes.orchestrator import router  # noqa: F401
