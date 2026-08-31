"""Structured logging configuration for Kairos backend.

JSON logs in production (machine-parseable for log aggregation),
human-readable console format in development.
"""
import json
import logging
import sys
from datetime import datetime, timezone

from app.config import settings

_RESERVED = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Emits one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = repr(value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Configures root logging once per process."""
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if settings.is_production
        else logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    # Quiet third-party noise that buries our own signals
    for noisy in ("httpx", "httpcore", "asyncio", "mcp", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
