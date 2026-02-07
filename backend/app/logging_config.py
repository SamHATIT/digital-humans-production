"""
Centralized logging configuration for Digital Humans backend.

Provides JSON-structured logging output to stderr for all modules.
Call setup_logging() once at application startup (in main.py) before
importing other app modules.

P5: Replaces 47 print(file=sys.stderr) calls across 10 files.
"""

import logging
import logging.config
import json
import sys
from datetime import datetime, timezone


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
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": JSONFormatter,
        },
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stderr",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "agents": {"level": "INFO"},
        "app": {"level": "INFO"},
        "uvicorn": {"level": "WARNING"},
        "uvicorn.access": {"level": "WARNING"},
        "httpx": {"level": "WARNING"},
    },
}


def setup_logging() -> None:
    """
    Apply the centralized logging configuration.

    Must be called before any ``logging.getLogger()`` calls from
    application modules so that the JSON formatter is active from the start.
    """
    logging.config.dictConfig(LOGGING_CONFIG)
