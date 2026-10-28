# SPDX-License-Identifier: Apache-2.0
"""RFC 9457 problem+json responses. Errors never echo request bodies (they may hold PII)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from vigil.obs import request_id_var

log = logging.getLogger(__name__)
PROBLEM = "application/problem+json"


def problem_body(status: int, title: str, detail: str = "", **extra: Any) -> bytes:
    """Serialises a problem document."""
    doc = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": request_id_var.get(),
        **extra,
    }
    return json.dumps(doc, ensure_ascii=False).encode()


def problem(
    status: int, title: str, detail: str = "", headers: dict[str, str] | None = None, **extra: Any
) -> Response:
    """Builds a problem response."""
    return Response(
        problem_body(status, title, detail, **extra),
        status_code=status,
        media_type=PROBLEM,
        headers=headers,
    )


def install_handlers(app: FastAPI) -> None:
    """Registers handlers that return problem+json."""

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> Response:
        errors = [
            {"loc": [str(x) for x in e.get("loc", [])], "msg": e.get("msg", "invalid")}
            for e in exc.errors()
        ][:10]
        return problem(
            422,
            "Invalid request",
            "The request body or parameters failed validation.",
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> Response:
        return problem(
            exc.status_code, "Request failed", str(exc.detail), headers=dict(exc.headers or {})
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> Response:
        log.error("unhandled_error", extra={"error": type(exc).__name__}, exc_info=exc)
        return problem(
            500, "Internal error", "Something went wrong. Quote the request_id when reporting."
        )
