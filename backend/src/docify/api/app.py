"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from docify import __version__
from docify.api.errors import install_error_handlers
from docify.api.middleware import DocifyMiddleware
from docify.api.routers import auth, chat, dev, github, health, me, repos, workspaces
from docify.cache import close_valkey
from docify.config import get_settings
from docify.db.session import dispose_engine, init_engine
from docify.observability.logging import configure_logging, get_logger

log = get_logger("docify.api")


async def _queue_metrics_loop() -> None:
    """Poll SQS depth every 60 s for dashboards/alerts (§16.2). Cheap: 1 API call/min."""
    from docify.jobs.queue import get_queue
    from docify.observability.metrics import QUEUE_MESSAGES

    while True:
        with contextlib.suppress(Exception):
            counts = await get_queue().counts()
            QUEUE_MESSAGES.labels("events", "visible").set(counts["visible"])
            QUEUE_MESSAGES.labels("events", "inflight").set(counts["inflight"])
        await asyncio.sleep(60)


def create_app(*, start_background: bool = True) -> FastAPI:
    s = get_settings()
    configure_logging(level=s.log_level, json=s.log_json, service="api", env=s.env, version=s.version)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        init_engine()
        task = asyncio.create_task(_queue_metrics_loop()) if start_background and not s.is_local else None
        log.info("api.start", env=s.env, version=s.version)
        yield
        if task:
            task.cancel()
        await close_valkey()
        await dispose_engine()

    app = FastAPI(
        title="Docify API", version=__version__, lifespan=lifespan,
        docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json",
        description="Docify keeps documentation for your GitHub repositories up to date with AI.",
    )
    install_error_handlers(app)
    app.add_middleware(DocifyMiddleware)

    api = APIRouter(prefix="/api")
    for r in (health, auth, me, workspaces, github, repos, chat):
        api.include_router(r.router)
    if s.is_local:
        api.include_router(dev.router)
    app.include_router(api)
    return app
