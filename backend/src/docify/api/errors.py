"""RFC 9457 problem+json errors (Master Doc §7)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from docify.cache import RateLimited
from docify.observability.logging import get_logger

log = get_logger(__name__)

PROBLEM = "application/problem+json"


class Problem(Exception):
    def __init__(self, status: int, title: str, detail: str | None = None, *, code: str | None = None,
                 headers: dict[str, str] | None = None, extra: dict[str, Any] | None = None) -> None:
        super().__init__(detail or title)
        self.status, self.title, self.detail = status, title, detail
        self.code = code or title.lower().replace(" ", "_")
        self.headers = headers or {}
        self.extra = extra or {}


def not_found(what: str = "Resource") -> Problem:
    return Problem(404, "Not found", f"{what} not found.", code="not_found")


def unauthorized(detail: str = "Please sign in.") -> Problem:
    return Problem(401, "Unauthorized", detail, code="unauthorized")


def forbidden(detail: str = "You don't have permission to do that.") -> Problem:
    return Problem(403, "Forbidden", detail, code="forbidden")


def conflict(detail: str, code: str = "conflict") -> Problem:
    return Problem(409, "Conflict", detail, code=code)


def bad_request(detail: str, code: str = "bad_request") -> Problem:
    return Problem(400, "Bad request", detail, code=code)


def _body(request: Request, status: int, title: str, detail: str | None, code: str,
          extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": f"https://docify.work/problems/{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "request_id": getattr(request.state, "request_id", None),
    }
    if extra:
        body.update(extra)
    return body


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def _problem(request: Request, exc: Problem) -> JSONResponse:
        return JSONResponse(_body(request, exc.status, exc.title, exc.detail, exc.code, exc.extra),
                            status_code=exc.status, media_type=PROBLEM, headers=exc.headers)

    @app.exception_handler(RateLimited)
    async def _limited(request: Request, exc: RateLimited) -> JSONResponse:
        return JSONResponse(
            _body(request, 429, "Too many requests", "Slow down and try again later.", "rate_limited",
                  {"retry_after": exc.retry_after}),
            status_code=429, media_type=PROBLEM, headers={"Retry-After": str(exc.retry_after)},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": [str(p) for p in e.get("loc", [])], "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(_body(request, 422, "Invalid request", "Some fields are invalid.", "validation_error",
                                  {"errors": errors}), status_code=422, media_type=PROBLEM)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = {404: "Not found", 405: "Method not allowed"}.get(exc.status_code, "Error")
        return JSONResponse(_body(request, exc.status_code, title, str(exc.detail), title.lower().replace(" ", "_")),
                            status_code=exc.status_code, media_type=PROBLEM)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("http.unhandled", error=type(exc).__name__)
        return JSONResponse(_body(request, 500, "Internal error", "Something went wrong on our side.", "internal"),
                            status_code=500, media_type=PROBLEM)
