"""Structured JSON logging (structlog) with request/job context.

Rule (Master Doc §16.1): never log tokens, cookies, auth headers, passwords,
OAuth codes, file contents or prompts — only ids, sizes and counts.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_SENSITIVE_KEYS = {"password", "token", "cookie", "authorization", "code", "secret", "api_key", "private_key"}


def _scrub(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in list(event_dict):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(*, level: str = "INFO", json: bool = True, service: str = "api", env: str = "local",
                      version: str = "dev") -> None:
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="ts"),
        _scrub,
    ]
    renderer: Any = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[*shared, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelNamesMapping().get(level, 20)),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service, env=env, version=version)

    # Route stdlib logging (uvicorn, sqlalchemy, botocore) through the same output.
    logging.basicConfig(stream=sys.stdout, level=level, format="%(message)s", force=True)
    for noisy in ("botocore", "boto3", "urllib3", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True  # we log requests ourselves


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
