"""Structured, privacy-safe operational logging for the demo API."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock
from typing import Any


request_id_context: ContextVar[str | None] = ContextVar("request_id_context", default=None)


class RuntimeMetrics:
    """Process-local aggregates for HTTP status outcomes, never request content."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests_total = 0
        self._errors_by_status: dict[str, int] = {}

    def record_response(self, status_code: int) -> None:
        with self._lock:
            self._requests_total += 1
            if status_code >= 400:
                status = str(status_code)
                self._errors_by_status[status] = self._errors_by_status.get(status, 0) + 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            errors_total = sum(self._errors_by_status.values())
            return {
                "http_requests_total": self._requests_total,
                "http_errors_total": errors_total,
                "http_errors_by_status": dict(self._errors_by_status),
            }


class JsonFormatter(logging.Formatter):
    """Emit an allow-listed JSON record; request bodies and event payloads stay out."""

    _FIELDS = ("request_id", "case_id", "event_type", "path", "status_code", "duration_ms", "mode", "failure_type")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for field in self._FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("ai_intel_bureau")
    logger.setLevel(level.upper())
    logger.propagate = False
    if not any(getattr(handler, "_ai_intel_bureau_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._ai_intel_bureau_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("ai_intel_bureau")
