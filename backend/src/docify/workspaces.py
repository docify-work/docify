"""Workspace domain helpers shared by routers and account deletion."""

from __future__ import annotations

import re
import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docify.db.models import Repository, Workspace
from docify.jobs.service import enqueue


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "workspace"
    if len(s) < 3:
        s = f"{s}-ws"
    return s


async def unique_slug(db: AsyncSession, base: str) -> str:
    slug = base
    for _ in range(20):
        exists = (await db.execute(select(func.count()).select_from(Workspace).where(Workspace.slug == slug)))\
            .scalar_one()
        if not exists:
            return slug
        slug = f"{base[:40]}-{secrets.token_hex(2)}"
    raise RuntimeError("could not allocate slug")


async def purge_workspace(db: AsyncSession, ws: Workspace) -> list[uuid.UUID]:
    """Queue repo_purge for every repo of a (soft-)deleted workspace. Caller commits + dispatches."""
    ids = []
    for repo in (await db.execute(select(Repository).where(Repository.workspace_id == ws.id,
                                                           Repository.status != "disconnected"))).scalars():
        ids.append((await enqueue(db, "repo_purge", workspace_id=ws.id, repo_id=repo.id,
                                  payload={"reason": "workspace_deleted"})).job_id)
    return ids
