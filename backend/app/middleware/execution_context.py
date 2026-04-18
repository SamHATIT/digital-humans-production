"""
ExecutionContextMiddleware — D-2.

Sets `execution_id`, `request_id`, and (when available) `agent_id` in
contextvars so that logging_config formatters and downstream services
(e.g. audit_service, llm_logger) can attach consistent context to every
log line and DB write without threading the values through every call
site.

Usage: add once in app.main, after CORS / rate limiter, before the
business middlewares:

    from app.middleware.execution_context import ExecutionContextMiddleware
    app.add_middleware(ExecutionContextMiddleware)

The middleware is fire-and-forget: any request whose path does not match
an ``/execute/{id}`` pattern simply gets a request_id but no
execution_id. Agent code that wants to attach an ``agent_id`` to its
log lines can call ``set_agent_id(agent_id)`` at the start of its run()
and ``reset_agent_id(token)`` in a finally block.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar, Token
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

execution_id_var: ContextVar[Optional[int]] = ContextVar("execution_id", default=None)
agent_id_var: ContextVar[Optional[str]] = ContextVar("agent_id", default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

_EXECUTION_ID_PATTERN = re.compile(r"/execute/(\d+)")


def set_agent_id(agent_id: str) -> Token:
    """Set agent_id for the current task context. Returns a reset token."""
    return agent_id_var.set(agent_id)


def reset_agent_id(token: Token) -> None:
    agent_id_var.reset(token)


class ExecutionContextMiddleware(BaseHTTPMiddleware):
    """Populate request_id + execution_id contextvars for every request."""

    async def dispatch(self, request: Request, call_next):
        request_token = request_id_var.set(uuid.uuid4().hex)
        exec_token: Optional[Token] = None
        match = _EXECUTION_ID_PATTERN.search(request.url.path)
        if match:
            exec_token = execution_id_var.set(int(match.group(1)))
        try:
            return await call_next(request)
        finally:
            if exec_token is not None:
                execution_id_var.reset(exec_token)
            request_id_var.reset(request_token)
