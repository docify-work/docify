"""Reconciler — the source of truth (D06). Runs every 15 min + at worker start (§8.4).

Webhooks are only an optimisation; this pass catches missed/oversized webhooks,
long sleeps (> 14 d SQS retention), crashed workers and the outbox gap.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select

from docify.ai.budget import spent_this_month, spent_today
from docify.config import get_settings
from docify.db.models import GithubInstallation, Job, Repository
from docify.db.session import session_scope
from docify.github.client import GitHubApp, GitHubNotFound
from docify.jobs import service
from docify.jobs.errors import JobError
from docify.observability.logging import get_logger

log = get_logger("docify.reconcile")
SINGLETON = "reconciler"


async def reconcile_once(github: GitHubApp | None = None) -> dict[str, int]:
    owner = service.worker_token()
    stats = {"installations": 0, "synced": 0, "indexed": 0, "recovered": 0, "resent": 0, "unblocked": 0}
    async with session_scope() as db:
        if not await service.acquire_singleton(db, SINGLETON, owner, timedelta(minutes=10)):
            log.info("reconcile.skipped_locked")
            return stats
    try:
        to_dispatch: list[uuid.UUID] = []
        await _recover_jobs(stats, to_dispatch)
        await _unblock_budget(stats, to_dispatch)
        async with session_scope() as db:
            stale = await service.stale_queued_ids(db)
        stats["resent"] = len(stale)
        to_dispatch.extend(stale)
        if get_settings().github_configured:
            await _check_github(github or GitHubApp(), stats, to_dispatch)
        await service.dispatch(to_dispatch)
    finally:
        async with session_scope() as db:
            await service.release_singleton(db, SINGLETON, owner)
    log.info("reconcile.done", **stats)
    return stats


async def _recover_jobs(stats: dict[str, int], out: list[uuid.UUID]) -> None:
    """Step 3: expired job leases → dead or back to queued (rule 5a); expired repo leases cleared."""
    async with session_scope() as db:
        for job in await service.expired_running(db):
            if job.attempts >= job.max_attempts:
                await service.finish(db, job, "dead", error={"message": "lease expired; attempts exhausted"})
            else:
                out.append(await service.requeue(db, job, run_after=service.utcnow(),
                                                  error={"message": "lease expired (worker crashed?)"}))
            stats["recovered"] += 1
        await service.clear_expired_repo_leases(db)


async def _unblock_budget(stats: dict[str, int], out: list[uuid.UUID]) -> None:
    s = get_settings()
    async with session_scope() as db:
        if await spent_today(db) >= s.ai_daily_budget_usd:
            return
        jobs = (await db.execute(select(Job).where(Job.status == "blocked_budget").with_for_update(skip_locked=True)
                                 .limit(50))).scalars().all()
        over: dict[uuid.UUID, bool] = {}
        for job in jobs:
            if job.workspace_id is not None:
                if job.workspace_id not in over:
                    over[job.workspace_id] = await spent_this_month(db, job.workspace_id) >= s.ai_ws_monthly_budget_usd
                if over[job.workspace_id]:
                    continue
            job.status = "queued"
            job.run_after = service.utcnow()
            out.append(job.id)
            stats["unblocked"] += 1


async def _check_github(gh: GitHubApp, stats: dict[str, int], out: list[uuid.UUID]) -> None:
    """Steps 1–2: installations' repo lists + HEAD of each ready repo."""
    async with session_scope() as db:
        installations = (await db.execute(select(GithubInstallation.installation_id).where(
            GithubInstallation.deleted_at.is_(None), GithubInstallation.suspended_at.is_(None)))).scalars().all()
        for inst_id in installations:
            out.append((await service.enqueue(db, "installation_sync", workspace_id=None, installation_id=inst_id,
                                              payload={"reason": "reconcile"})).job_id)
            stats["installations"] += 1
        repos = (await db.execute(select(Repository).where(Repository.status == "ready",
                                                           Repository.archived.is_(False)))).scalars().all()
    for repo in repos:
        try:
            client = await gh.for_installation(repo.installation_id)
            meta = await client.get_repo(repo.full_name, repo.github_repo_id)
            branch = meta.get("default_branch") or repo.default_branch
            head = await client.branch_head(meta["full_name"], branch)
        except (GitHubNotFound, JobError) as exc:
            log.info("reconcile.repo_check_failed", repo_id=str(repo.id), error=type(exc).__name__)
            continue
        job_type = None
        if branch != repo.indexed_branch:
            job_type = "repo_index"
        elif head and head != repo.last_processed_sha:
            job_type = "repo_sync"
        if job_type:
            async with session_scope() as db:
                out.append((await service.enqueue(db, job_type, workspace_id=repo.workspace_id, repo_id=repo.id,
                                                  payload={"reason": "reconcile"})).job_id)
            stats["indexed" if job_type == "repo_index" else "synced"] += 1
