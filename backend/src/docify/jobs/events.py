"""GitHub event message → jobs, deduped by delivery id in the same transaction (rule 6, §9.4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from docify.db.models import GithubInstallation, Repository
from docify.jobs.service import enqueue
from docify.observability.logging import get_logger

log = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


async def record_delivery(db: AsyncSession, delivery_id: str, event: str) -> bool:
    """True if this delivery is new; False for a duplicate (F3)."""
    row = (await db.execute(text(
        "INSERT INTO webhook_deliveries (delivery_id, event, processed_at) VALUES (:d, :e, now()) "
        "ON CONFLICT (delivery_id) DO NOTHING RETURNING delivery_id"
    ), {"d": delivery_id, "e": event})).first()
    return row is not None


async def _repo_by_github_id(db: AsyncSession, github_repo_id: Any) -> Repository | None:
    if github_repo_id is None:
        return None
    return (await db.execute(select(Repository).where(Repository.github_repo_id == int(github_repo_id),
                                                      Repository.status != "disconnected"))).scalar_one_or_none()


async def handle_event(db: AsyncSession, msg: dict[str, Any]) -> list[uuid.UUID]:
    """Apply one normalised event inside the caller's transaction. Returns job ids to dispatch after commit."""
    if not await record_delivery(db, str(msg.get("delivery_id") or uuid.uuid4()), str(msg.get("event"))):
        log.info("event.duplicate", delivery_id=msg.get("delivery_id"))
        return []
    event, action = msg.get("event"), msg.get("action")
    inst_id = msg.get("installation_id")
    jobs: list[uuid.UUID] = []

    async def job(job_type: str, repo: Repository | None = None, **payload: Any) -> None:
        r = await enqueue(db, job_type, workspace_id=repo.workspace_id if repo else None,
                          repo_id=repo.id if repo else None,
                          installation_id=int(inst_id) if job_type == "installation_sync" and inst_id else None,
                          payload=payload)
        jobs.append(r.job_id)

    if event == "push":
        repo = await _repo_by_github_id(db, msg.get("repo_id"))
        if repo is None or repo.status == "suspended":
            return jobs
        if msg.get("forced"):
            await job("repo_index", repo, reason="force_push", after=msg.get("after"))
        else:
            await job("repo_sync", repo, reason="push", after=msg.get("after"))

    elif event == "installation" and inst_id is not None:
        if action == "deleted":
            await db.execute(update(GithubInstallation).where(GithubInstallation.installation_id == int(inst_id))
                             .values(deleted_at=_now()))
            for repo in (await db.execute(select(Repository).where(
                    Repository.installation_id == int(inst_id), Repository.status != "disconnected"))).scalars():
                await job("repo_purge", repo, reason="uninstalled")
        elif action == "suspend":
            await db.execute(update(GithubInstallation).where(GithubInstallation.installation_id == int(inst_id))
                             .values(suspended_at=_now()))
            await db.execute(update(Repository).where(Repository.installation_id == int(inst_id),
                                                      Repository.status != "disconnected").values(status="suspended"))
        else:  # created / unsuspend / new_permissions_accepted
            await job("installation_sync", reason=str(action))

    elif event == "installation_repositories" and inst_id is not None:
        for gid in msg.get("repos_removed") or []:
            repo = await _repo_by_github_id(db, gid)
            if repo is not None and repo.installation_id == int(inst_id):
                await job("repo_purge", repo, reason="access_removed")
        await job("installation_sync", reason="repositories_changed")

    elif event == "repository":
        repo = await _repo_by_github_id(db, msg.get("repo_id"))
        if repo is None:
            return jobs
        if action == "deleted":
            await job("repo_purge", repo, reason="repo_deleted")
        elif action in ("renamed", "transferred"):
            full_name = msg.get("full_name")
            if full_name and "/" in full_name:
                repo.full_name = full_name
                repo.owner, repo.name = full_name.split("/", 1)
        elif action == "edited":
            await job("repo_index", repo, reason="default_branch_changed")
        elif action in ("archived", "unarchived"):
            repo.archived = action == "archived"
            if action == "unarchived":
                await job("repo_sync", repo, reason="unarchived")
        elif action in ("privatized", "publicized"):
            repo.private = action == "privatized"
    return jobs
