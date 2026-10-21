"""Health, readiness, version, public config, demo pointer."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from docify.api.deps import DB
from docify.api.schemas import DemoOut, PublicConfigOut, VersionOut
from docify.config import get_settings
from docify.db.models import Workspace

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness: the process is up")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness: DB reachable (internal only)")
async def ready(db: DB) -> JSONResponse:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ready"})


@router.get("/version", response_model=VersionOut)
async def version() -> VersionOut:
    s = get_settings()
    return VersionOut(version=s.version, env=s.env)


@router.get("/config", response_model=PublicConfigOut, summary="Feature flags the SPA needs")
async def public_config() -> PublicConfigOut:
    s = get_settings()
    return PublicConfigOut(env=s.env, version=s.version, github_enabled=s.github_configured,
                           google_enabled=s.google_configured, github_app_slug=s.github_app_slug or None,
                           demo_workspace_slug=s.demo_workspace_slug)


@router.get("/demo", response_model=DemoOut)
async def demo(db: DB) -> DemoOut:
    s = get_settings()
    ws = (await db.execute(select(Workspace.slug).where(Workspace.slug == s.demo_workspace_slug,
                                                        Workspace.is_public_demo.is_(True),
                                                        Workspace.deleted_at.is_(None)))).scalar_one_or_none()
    return DemoOut(workspace_slug=ws, available=ws is not None)
