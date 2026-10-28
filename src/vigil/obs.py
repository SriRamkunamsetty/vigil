# SPDX-License-Identifier: Apache-2.0
"""Structured JSON logging compatible with Google Cloud Logging.

Cloud Run forwards stdout to Cloud Logging, which parses ``severity``,
``message`` and the ``logging.googleapis.com/*`` fields. Audit events use the
``vigil.audit`` logger so a Log Router sink can export them to BigQuery.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
from typing import Any

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
trace_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace", default=None)

_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class CloudJsonFormatter(logging.Formatter):
    """Formats records as single-line JSON in Cloud Logging's schema."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialises ``record``."""
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "request_id": request_id_var.get(),
        }
        trace = trace_var.get()
        if trace:
            payload["logging.googleapis.com/trace"] = trace
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Installs the JSON formatter on the root logger (idempotent)."""
    root = logging.getLogger()
    root.setLevel(level)
    if any(isinstance(h.formatter, CloudJsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudJsonFormatter())
    root.handlers = [handler]
    logging.getLogger("uvicorn.access").disabled = True


audit_logger = logging.getLogger("vigil.audit")
