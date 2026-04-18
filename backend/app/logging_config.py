"""
Centralized logging configuration for Digital Humans backend.

Call setup_logging() once at application startup (in main.py) before
importing other app modules.

Two output formats are supported, selected via DH_LOG_FORMAT:
- "json"  (default) — structured JSON to stderr, suitable for ELK / Loki.
- "plain"           — single-line human readable, for local dev.

Both formats inject the following fields from contextvars when set by
ExecutionContextMiddleware (see app.middleware.execution_context):
- execution_id
- agent_id
- request_id

P5 / D-2: replaces 47 print(file=sys.stderr) calls across 10 files and
unifies the per-agent log prefixes.
"""

import json
import logging
import logging.config
import os
from datetime import datetime, timezone

from app.middleware.execution_context import (
    agent_id_var,
    execution_id_var,
    request_id_var,
)


def _context_fields() -> dict:
    """Return the subset of contextvars that are actually set."""
    fields: dict[str, object] = {}
    exec_id = execution_id_var.get()
    if exec_id is not None:
        fields["execution_id"] = exec_id
    agent_id = agent_id_var.get()
    if agent_id is not None:
        fields["agent_id"] = agent_id
    req_id = request_id_var.get()
    if req_id is not None:
        fields["request_id"] = req_id
    return fields


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        log_entry.update(_context_fields())
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    """Human-readable single-line format with optional execution context."""

    BASE = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    def __init__(self) -> None:
        super().__init__(fmt=self.BASE)

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        ctx = _context_fields()
        if ctx:
            suffix = " ".join(f"{k}={v}" for k, v in ctx.items())
            line = f"{line} [{suffix}]"
        return line


def _build_config(fmt: str, level: str) -> dict:
    formatter = "json" if fmt == "json" else "plain"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": JSONFormatter},
            "plain": {"()": PlainFormatter},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": formatter,
                "stream": "ext://sys.stderr",
            },
        },
        "root": {
            "level": level,
            "handlers": ["console"],
        },
        "loggers": {
            "agents": {"level": level},
            "app": {"level": level},
            "uvicorn": {"level": "WARNING"},
            "uvicorn.access": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
        },
    }


def setup_logging() -> None:
    """
    Apply the centralized logging configuration.

    Must be called before any ``logging.getLogger()`` calls from
    application modules so that the formatter is active from the start.

    Format and level are driven by DH_LOG_FORMAT / DH_LOG_LEVEL env vars,
    with defaults in app.config.settings.
    """
    fmt = os.environ.get("DH_LOG_FORMAT", "json").lower()
    level = os.environ.get("DH_LOG_LEVEL", "INFO").upper()
    logging.config.dictConfig(_build_config(fmt, level))
