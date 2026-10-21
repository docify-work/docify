"""ASGI middleware: request id, access log + metrics, origin check, CSRF header check.

Pure ASGI (not BaseHTTPMiddleware) so SSE streaming and contextvars keep working.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from docify.auth.tokens import constant_time_equals
from docify.config import get_settings
from docify.observability.logging import get_logger
from docify.observability.metrics import HTTP_DURATION, HTTP_REQUESTS

log = get_logger("docify.http")

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = b"x-docify-csrf"
ORIGIN_HEADER = b"x-origin-verify"
# Called by machines, not browsers: no CSRF header possible.
CSRF_EXEMPT = ("/api/dev/webhook",)
ORIGIN_EXEMPT = ("/api/health", "/api/ready")
_REQ_ID_OK = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def _header(scope: Scope, name: bytes) -> str | None:
    for k, v in scope.get("headers", []):
        if k == name:
            return str(v.decode("latin-1"))
    return None


async def _send_problem(send: Send, status: int, title: str, detail: str, code: str, request_id: str) -> None:
    body = json.dumps({"type": f"https://docify.work/problems/{code}", "title": title, "status": status,
                       "detail": detail, "code": code, "request_id": request_id}).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/problem+json"),
                            (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


def _route_label(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return str(path) if path else "unmatched"


class DocifyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.settings = get_settings()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _header(scope, b"x-request-id")
        request_id = incoming if incoming and _REQ_ID_OK.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        path: str = scope["path"]
        method: str = scope["method"]
        start = time.perf_counter()
        status_holder: dict[str, Any] = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            # 1) Origin check: in the cloud only CloudFront knows this secret header (§4.2).
            expected = self.settings.origin_verify_header
            got = _header(scope, ORIGIN_HEADER)
            if path == "/api/ready" and got is not None:
                await _send_problem(send_wrapper, 404, "Not found", "Not found.", "not_found", request_id)
                return
            if expected and path.startswith("/api") and path not in ORIGIN_EXEMPT and not (
                got and constant_time_equals(got, expected.get_secret_value())
            ):
                await _send_problem(send_wrapper, 403, "Forbidden", "Direct origin access is not allowed.",
                                    "origin_forbidden", request_id)
                return

            # 2) CSRF: unsafe methods need a custom header that cross-site forms/fetches can't set
            #    without CORS (and we enable no CORS) (§10.5).
            if method in UNSAFE and path.startswith("/api") and path not in CSRF_EXEMPT \
                    and _header(scope, CSRF_HEADER) != "1":
                await _send_problem(send_wrapper, 403, "Forbidden", "Missing X-Docify-CSRF header.",
                                    "csrf", request_id)
                return

            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            route = _route_label(scope)
            status = status_holder["status"]
            if path not in ("/api/health", "/api/ready"):
                HTTP_REQUESTS.labels(route, method, str(status)).inc()
                HTTP_DURATION.labels(route, method).observe(elapsed)
                log.info("http.request", method=method, route=route, status=status,
                         duration_ms=round(elapsed * 1000, 1))
            structlog.contextvars.unbind_contextvars("request_id", "user_id", "workspace_id")
