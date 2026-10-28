# SPDX-License-Identifier: Apache-2.0
"""One pure-ASGI middleware: request IDs, trace context, body limit, auth, rate limit, headers, access log."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import threading
import time
import uuid
from collections import OrderedDict, deque
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from vigil.api.errors import PROBLEM, problem_body
from vigil.config import Settings
from vigil.obs import request_id_var, trace_var

log = logging.getLogger("vigil.access")
_PROTECTED = ("/v1/", "/a2a/")
_RID_OK = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; font-src 'self'; connect-src 'self'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)


class _TooLarge(Exception):
    pass


class RateLimiter:
    """Sliding-window limiter (per process; use Cloud Armor / API Gateway for fleet-wide limits)."""

    def __init__(self, per_minute: int, max_keys: int = 20_000) -> None:
        """Creates a limiter."""
        self._n = per_minute
        self._max = max_keys
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> float:
        """Returns 0 if allowed, else seconds until the next slot."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                while len(self._hits) >= self._max:
                    self._hits.popitem(last=False)
                q = self._hits[key] = deque()
            self._hits.move_to_end(key)
            while q and now - q[0] >= 60:
                q.popleft()
            if len(q) >= self._n:
                return max(0.1, 60 - (now - q[0]))
            q.append(now)
            return 0.0


def _client_ip(scope: Scope, headers: dict[bytes, bytes], hops: int) -> str:
    if hops > 0:
        xff = headers.get(b"x-forwarded-for", b"").decode("latin-1").split(",")
        if len(xff) >= hops and xff[-hops].strip():
            return xff[-hops].strip()
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


def _trace(headers: dict[bytes, bytes]) -> str | None:
    raw = headers.get(b"x-cloud-trace-context", b"").decode("latin-1")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    m = re.match(r"^([0-9a-fA-F]{32})/", raw)
    return f"projects/{project}/traces/{m.group(1)}" if m and project else None


class SecurityMiddleware:
    """See module docstring."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        """Wraps ``app``."""
        self.app = app
        self.s = settings
        self.limiter = RateLimiter(settings.rate_limit_per_min)

    async def _reject(
        self, send: Send, status: int, title: str, detail: str, extra: dict[str, str] | None = None
    ) -> None:
        body = problem_body(status, title, detail)
        hdrs = [
            (b"content-type", PROBLEM.encode()),
            (b"content-length", str(len(body)).encode()),
            (b"x-content-type-options", b"nosniff"),
            (b"x-request-id", request_id_var.get().encode()),
        ]
        hdrs += [(k.encode(), v.encode()) for k, v in (extra or {}).items()]
        await send({"type": "http.response.start", "status": status, "headers": hdrs})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI entry point."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        headers: dict[bytes, bytes] = {k.lower(): v for k, v in scope["headers"]}
        rid_in = headers.get(b"x-request-id", b"").decode("latin-1")
        rid = rid_in if _RID_OK.match(rid_in) else uuid.uuid4().hex[:16]
        tok1, tok2 = request_id_var.set(rid), trace_var.set(_trace(headers))
        status_holder = {"status": 0}
        path: str = scope["path"]
        try:
            protected = path.startswith(_PROTECTED)
            caller = "public"
            if protected:
                if self.s.auth_mode == "apikey":
                    key = headers.get(b"x-api-key", b"").decode("latin-1")
                    digest = hashlib.sha256(key.encode()).hexdigest() if key else ""
                    ok = bool(digest) and any(
                        hmac.compare_digest(digest, d) for d in self.s.api_key_digests
                    )
                    if not ok:
                        status_holder["status"] = 401
                        await self._reject(
                            send,
                            401,
                            "Unauthorized",
                            "A valid X-API-Key header is required.",
                            {"www-authenticate": 'ApiKey realm="vigil"'},
                        )
                        return
                    caller = f"inst-{digest[:8]}"
                else:
                    hdr = headers.get(b"x-demo-institution", b"").decode("latin-1")
                    caller = re.sub(r"[^A-Za-z0-9_-]", "", hdr)[:24] or "demo"
                wait = self.limiter.check(
                    f"{caller}|{_client_ip(scope, headers, self.s.trusted_proxy_hops)}"
                )
                if wait:
                    status_holder["status"] = 429
                    await self._reject(
                        send,
                        429,
                        "Too many requests",
                        "Rate limit exceeded.",
                        {"retry-after": str(int(wait) + 1)},
                    )
                    return
            scope.setdefault("state", {})["caller"] = caller

            cl = headers.get(b"content-length")
            if cl and cl.isdigit() and int(cl) > self.s.max_body_bytes:
                status_holder["status"] = 413
                await self._reject(
                    send,
                    413,
                    "Payload too large",
                    f"Maximum body is {self.s.max_body_bytes} bytes.",
                )
                return

            seen = 0

            async def limited_receive() -> Message:
                nonlocal seen
                msg = await receive()
                if msg["type"] == "http.request":
                    seen += len(msg.get("body", b""))
                    if seen > self.s.max_body_bytes:
                        raise _TooLarge
                return msg

            started = False
            https = (
                headers.get(b"x-forwarded-proto", b"").lower() == b"https"
                or scope.get("scheme") == "https"
            )

            async def send_wrapper(message: Message) -> None:
                nonlocal started
                if message["type"] == "http.response.start":
                    started = True
                    status_holder["status"] = message["status"]
                    h: list[Any] = list(message.get("headers", []))
                    h += [
                        (b"x-request-id", rid.encode()),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-frame-options", b"DENY"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                        (b"cross-origin-opener-policy", b"same-origin"),
                    ]
                    if https:
                        h.append(
                            (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                        )
                    if path.startswith("/v1/"):
                        h.append((b"cache-control", b"no-store"))
                    elif not path.startswith("/a2a/"):
                        h.append((b"content-security-policy", _CSP.encode()))
                    message = {**message, "headers": h}
                await send(message)

            try:
                await self.app(scope, limited_receive, send_wrapper)
            except _TooLarge:
                if not started:
                    status_holder["status"] = 413
                    await self._reject(
                        send,
                        413,
                        "Payload too large",
                        f"Maximum body is {self.s.max_body_bytes} bytes.",
                    )
        finally:
            log.info(
                "request",
                extra={
                    "method": scope.get("method"),
                    "path": path,
                    "status": status_holder["status"],
                    "latency_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
            request_id_var.reset(tok1)
            trace_var.reset(tok2)
