"""Structured-ish JSON logging without third-party dependencies."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone


def redact(text: object) -> str:
    """Remove credentials from any error text before logging it."""
    return re.sub(r"://[^:@\s]+:[^@\s]+@", "://***:***@", str(text))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "fastembed", "onnxruntime"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_extra(**kwargs: object) -> dict[str, dict[str, object]]:
    return {"extra": {"extra_fields": kwargs}}
